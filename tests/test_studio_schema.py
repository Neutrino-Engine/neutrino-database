"""
Agent Studio — ``studio_*`` tables, ``chat_artifact.run_id``, team-scoped memory.

plans/AGENT-STUDIO-PLAN.md. Locked design points these tests pin:

  * Statuses are String + CHECK (the user_memory rationale), so an unknown
    status is rejected by Postgres, not by convention.
  * A run pins its team config and every task pins its agent config, so replay
    never reads a live draft.
  * ``studio_trigger_event`` dedupes on (team_id, item_key): the second
    sighting of an item is a constraint violation the poller treats as no-op.
  * ``studio_approval.outcome`` is NULL while pending and otherwise one of the
    four fail-closed outcomes.
  * ``user_memory.scope='team'`` requires ``team_id``; the team FK CASCADEs.
  * ``chat_artifact.run_id`` is SET NULL: the artifact outlives the run.
  * ``studio_run_event`` is Agent Studio's own log, not the legacy
    ``run_events`` (whose ``run_id`` is String(26) against the old ``runs``
    table). ``seq`` is the SSE cursor and is unique per run, so a reconnecting
    console resumes exactly once from its Last-Event-ID.
  * The shared pydantic contracts refuse the failure modes the harness relies
    on never seeing: a completed Envelope without output, a schema_invalid
    Envelope without raw_text, a Plan with a cycle, a ToolResult that is both
    ok and an error.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError

from neutrino_database.models.base import metadata
from neutrino_database.models.enums import AllowedModuleEnum
from neutrino_database.models.studio_schemas import (
    AgentConfig,
    Envelope,
    Limits,
    Plan,
    PlanTask,
    TeamConfig,
    ToolError,
    ToolResult,
)
from neutrino_database.models.tables import (
    STUDIO_RUN_STATUSES,
    STUDIO_TASK_STATUSES,
    chat,
    chat_artifact,
    studio_agent,
    studio_agent_task,
    studio_agent_version,
    studio_approval,
    studio_event_trigger,
    studio_run,
    studio_run_event,
    studio_team,
    studio_team_version,
    studio_test_case,
    studio_trigger_event,
    studio_workspace_file,
    tenant,
    user as user_table,
    user_memory,
    workspace,
)

STUDIO_TABLES = {
    "studio_agent", "studio_agent_version", "studio_team", "studio_team_version",
    "studio_api_key", "studio_event_trigger", "studio_schedule", "studio_run",
    "studio_agent_task", "studio_approval", "studio_trigger_event",
    "studio_test_case", "studio_workspace_file", "studio_run_event",
}


async def _seed(conn):
    tenant_id, workspace_id, user_id = (str(uuid.uuid4()) for _ in range(3))
    await conn.execute(insert(tenant).values(id=tenant_id, name="studio-tenant", org_external_id=f"studio-{uuid.uuid4()}"))
    await conn.execute(insert(workspace).values(id=workspace_id, tenant_id=tenant_id, name="studio-ws"))
    await conn.execute(insert(user_table).values(id=user_id, tenant_id=tenant_id, email=f"studio-{uuid.uuid4()}@test.local"))
    return tenant_id, workspace_id, user_id


async def _seed_team_run(conn, tenant_id, workspace_id, user_id):
    agent_id, team_id, run_id = (str(uuid.uuid4()) for _ in range(3))
    await conn.execute(insert(studio_agent).values(id=agent_id, tenant_id=tenant_id, workspace_id=workspace_id, name="Extractor", created_by=user_id))
    await conn.execute(insert(studio_team).values(id=team_id, tenant_id=tenant_id, workspace_id=workspace_id, name="TDS Gate", created_by=user_id))
    await conn.execute(insert(studio_run).values(
        id=run_id, tenant_id=tenant_id, workspace_id=workspace_id, team_id=team_id,
        team_config={"orchestrator": {"model": "x"}}, trigger_kind="studio", trigger_actor_id=user_id,
        workspace_prefix=f"agent-runs/{tenant_id}/{run_id}/",
    ))
    return agent_id, team_id, run_id


def test_all_studio_tables_registered_and_module_enum():
    names = {t.name for t in metadata.sorted_tables}
    assert STUDIO_TABLES <= names
    assert AllowedModuleEnum.AGENT_STUDIO.value == "Agent Studio"
    assert "run_id" in chat_artifact.c
    assert {"team_id", "agent_id"} <= set(user_memory.c.keys())


@pytest.mark.asyncio
async def test_run_and_task_status_checks(test_engine):
    async with test_engine.begin() as conn:
        tenant_id, workspace_id, user_id = await _seed(conn)
    try:
        async with test_engine.begin() as conn:
            agent_id, team_id, run_id = await _seed_team_run(conn, tenant_id, workspace_id, user_id)
        for bad in ({"status": "done"}, {"trigger_kind": "cron"}):
            async with test_engine.begin() as conn:
                with pytest.raises(IntegrityError):
                    await conn.execute(insert(studio_run).values(
                        id=str(uuid.uuid4()), tenant_id=tenant_id, workspace_id=workspace_id, team_id=team_id,
                        team_config={}, workspace_prefix="p/", **{"trigger_kind": "studio", **bad},
                    ))
        async with test_engine.begin() as conn:
            for status in STUDIO_TASK_STATUSES:
                await conn.execute(insert(studio_agent_task).values(
                    id=str(uuid.uuid4()), tenant_id=tenant_id, run_id=run_id, agent_id=agent_id,
                    agent_config={"charter": "x"}, alias=f"a-{status}", status=status,
                ))
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await conn.execute(insert(studio_agent_task).values(
                        id=str(uuid.uuid4()), tenant_id=tenant_id, run_id=run_id, agent_config={}, alias="bad", status="finished",
                    ))
        assert "completed" in STUDIO_RUN_STATUSES
    finally:
        async with test_engine.begin() as conn:
            await conn.execute(delete(tenant).where(tenant.c.id == tenant_id))


@pytest.mark.asyncio
async def test_trigger_event_dedupe_and_approval_outcome(test_engine):
    async with test_engine.begin() as conn:
        tenant_id, workspace_id, user_id = await _seed(conn)
    try:
        async with test_engine.begin() as conn:
            agent_id, team_id, run_id = await _seed_team_run(conn, tenant_id, workspace_id, user_id)
            trigger_id = str(uuid.uuid4())
            await conn.execute(insert(studio_event_trigger).values(id=trigger_id, tenant_id=tenant_id, team_id=team_id, name="sp", source="poll"))
            await conn.execute(insert(studio_trigger_event).values(id=str(uuid.uuid4()), tenant_id=tenant_id, team_id=team_id, trigger_id=trigger_id, source="poll", item_key="drive-item-1"))
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await conn.execute(insert(studio_trigger_event).values(id=str(uuid.uuid4()), tenant_id=tenant_id, team_id=team_id, trigger_id=trigger_id, source="poll", item_key="drive-item-1"))
            # pending approval: outcome NULL is allowed; an invented outcome is not
            await conn.execute(insert(studio_approval).values(
                id=str(uuid.uuid4()), tenant_id=tenant_id, run_id=run_id, action={"action": "send"}, payload_hash="0" * 64,
                expires_at=sa.func.now(),
            ))
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await conn.execute(insert(studio_approval).values(
                        id=str(uuid.uuid4()), tenant_id=tenant_id, run_id=run_id, action={}, payload_hash="0" * 64,
                        expires_at=sa.func.now(), outcome="approved",
                    ))
    finally:
        async with test_engine.begin() as conn:
            await conn.execute(delete(tenant).where(tenant.c.id == tenant_id))


@pytest.mark.asyncio
async def test_team_memory_scope_and_artifact_run_link(test_engine):
    async with test_engine.begin() as conn:
        tenant_id, workspace_id, user_id = await _seed(conn)
    try:
        async with test_engine.begin() as conn:
            agent_id, team_id, run_id = await _seed_team_run(conn, tenant_id, workspace_id, user_id)
            base = dict(tenant_id=tenant_id, user_id=user_id, workspace_id=workspace_id, kind="fact", origin="explicit", content="viscosity is on page 3")
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await conn.execute(insert(user_memory).values(id=str(uuid.uuid4()), scope="team", content_hash="a" * 64, **base))
            mem_id = str(uuid.uuid4())
            await conn.execute(insert(user_memory).values(id=mem_id, scope="team", team_id=team_id, agent_id=agent_id, content_hash="b" * 64, **base))
            # deleting the team cascades its memories
            await conn.execute(delete(studio_team).where(studio_team.c.id == team_id))
            assert (await conn.execute(select(user_memory.c.id).where(user_memory.c.id == mem_id))).first() is None

            # chat_artifact.run_id survives run deletion as NULL
            chat_id = str(uuid.uuid4())
            await conn.execute(insert(chat).values(id=chat_id, tenant_id=tenant_id, workspace_id=workspace_id, created_by=user_id, title="c"))
            team_id2 = str(uuid.uuid4()); run_id2 = str(uuid.uuid4())
            await conn.execute(insert(studio_team).values(id=team_id2, tenant_id=tenant_id, workspace_id=workspace_id, name="T2"))
            await conn.execute(insert(studio_run).values(id=run_id2, tenant_id=tenant_id, workspace_id=workspace_id, team_id=team_id2, team_config={}, trigger_kind="chat", workspace_prefix="p/"))
            art_id = str(uuid.uuid4())
            await conn.execute(insert(chat_artifact).values(id=art_id, tenant_id=tenant_id, workspace_id=workspace_id, chat_id=chat_id, kind="doc", content={"html": ""}, run_id=run_id2))
            await conn.execute(delete(studio_run).where(studio_run.c.id == run_id2))
            row = (await conn.execute(select(chat_artifact.c.run_id).where(chat_artifact.c.id == art_id))).first()
            assert row is not None and row[0] is None
    finally:
        async with test_engine.begin() as conn:
            await conn.execute(delete(tenant).where(tenant.c.id == tenant_id))


@pytest.mark.asyncio
async def test_run_event_seq_is_a_unique_cursor(test_engine):
    async with test_engine.begin() as conn:
        tenant_id, workspace_id, user_id = await _seed(conn)
    try:
        async with test_engine.begin() as conn:
            agent_id, team_id, run_id = await _seed_team_run(conn, tenant_id, workspace_id, user_id)
            for seq, kind in enumerate(("run_status", "plan_updated", "task_started")):
                await conn.execute(insert(studio_run_event).values(
                    id=str(uuid.uuid4()), tenant_id=tenant_id, run_id=run_id, seq=seq,
                    type=kind, payload={"status": "planning"},
                ))
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await conn.execute(insert(studio_run_event).values(
                        id=str(uuid.uuid4()), tenant_id=tenant_id, run_id=run_id, seq=0, type="dup",
                    ))
            with pytest.raises(IntegrityError):
                async with conn.begin_nested():
                    await conn.execute(insert(studio_run_event).values(
                        id=str(uuid.uuid4()), tenant_id=tenant_id, run_id=run_id, seq=-1, type="neg",
                    ))
            # replay from a cursor is the only read path
            rows = (await conn.execute(
                select(studio_run_event.c.seq)
                .where(studio_run_event.c.run_id == run_id, studio_run_event.c.seq > 0)
                .order_by(studio_run_event.c.seq)
            )).fetchall()
            assert [r[0] for r in rows] == [1, 2]
            # events die with the run
            await conn.execute(delete(studio_run).where(studio_run.c.id == run_id))
            assert (await conn.execute(select(studio_run_event.c.id).where(studio_run_event.c.run_id == run_id))).first() is None
    finally:
        async with test_engine.begin() as conn:
            await conn.execute(delete(tenant).where(tenant.c.id == tenant_id))


@pytest.mark.asyncio
async def test_a_test_case_carries_its_own_files(test_engine):
    """A case is input + files + assertions — the case owns its files, so
    "Run all" never needs a file attached by hand."""
    async with test_engine.begin() as conn:
        tenant_id, workspace_id, user_id = await _seed(conn)
    try:
        async with test_engine.begin() as conn:
            _, team_id, _ = await _seed_team_run(conn, tenant_id, workspace_id, user_id)
            bare, carrying = str(uuid.uuid4()), str(uuid.uuid4())
            await conn.execute(insert(studio_test_case).values(
                id=bare, tenant_id=tenant_id, subject_kind="team", subject_id=team_id,
                name="no files", input={}, assertions=[],
            ))
            locator = {"bucket": "neutrino-studio", "key": "template-fixtures/tds_gate/tds_s355_pass.txt",
                       "filename": "tds_s355_pass.txt"}
            await conn.execute(insert(studio_test_case).values(
                id=carrying, tenant_id=tenant_id, subject_kind="team", subject_id=team_id,
                name="compliant plate", input={"document_path": "files/tds_s355_pass.txt"},
                files=[locator], assertions=[],
            ))
            rows = dict((str(r[0]), r[1]) for r in (await conn.execute(
                select(studio_test_case.c.id, studio_test_case.c.files)
                .where(studio_test_case.c.subject_id == team_id)
            )).fetchall())
            # The default is an empty list, never NULL: every case has a files array.
            assert rows[bare] == []
            assert rows[carrying] == [locator]
    finally:
        async with test_engine.begin() as conn:
            await conn.execute(delete(tenant).where(tenant.c.id == tenant_id))


@pytest.mark.asyncio
async def test_a_studio_only_run_can_record_what_it_indexed(test_engine):
    """``indexed`` needs a document id, not a chat artefact.

    A run started from the Studio has no chat and so no artefact to hang the
    flag off, but it indexes for real — the CHECK asks what was indexed, not
    where the chat can open it, so that run can now tell the truth. The
    nonsense it still refuses is a row claiming the index holds something it
    cannot name.
    """
    async with test_engine.begin() as conn:
        tenant_id, workspace_id, user_id = await _seed(conn)
    try:
        async with test_engine.begin() as conn:
            _, _, run_id = await _seed_team_run(conn, tenant_id, workspace_id, user_id)
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"neutrino:studio-run:{run_id}:out.md"))
            # No chat, no artefact, and still indexed — the gap this closes.
            await conn.execute(insert(studio_workspace_file).values(
                id=str(uuid.uuid4()), tenant_id=tenant_id, run_id=run_id,
                path="out.md", size_bytes=12, indexed=True, indexed_doc_id=doc_id,
            ))
            # An attempt ES answered for but did not finish: a doc id with the
            # flag still false stays representable.
            await conn.execute(insert(studio_workspace_file).values(
                id=str(uuid.uuid4()), tenant_id=tenant_id, run_id=run_id,
                path="partial.md", size_bytes=3, indexed=False, indexed_doc_id=doc_id,
            ))
            rows = dict((r[0], (r[1], r[2])) for r in (await conn.execute(
                select(
                    studio_workspace_file.c.path,
                    studio_workspace_file.c.indexed,
                    studio_workspace_file.c.indexed_doc_id,
                ).where(studio_workspace_file.c.run_id == run_id)
            )).fetchall())
            assert rows["out.md"] == (True, doc_id)
            assert rows["partial.md"] == (False, doc_id)
            assert studio_workspace_file.c.indexed_doc_id.nullable

        async with test_engine.begin() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(insert(studio_workspace_file).values(
                    id=str(uuid.uuid4()), tenant_id=tenant_id, run_id=run_id,
                    path="liar.md", size_bytes=1, indexed=True,
                ))
    finally:
        async with test_engine.begin() as conn:
            await conn.execute(delete(tenant).where(tenant.c.id == tenant_id))


def test_max_questions_is_a_per_agent_limit():
    """The harness reads ``limits.max_questions``; ``extra="forbid"`` meant a
    builder who set it was rejected outright."""
    assert Limits().max_questions == 3
    assert Limits(max_questions=7).max_questions == 7
    # 0 is a real setting: an agent that may never stop to ask.
    assert Limits(max_questions=0).max_questions == 0
    for bad in (-1, 21):
        with pytest.raises(ValidationError):
            Limits(max_questions=bad)
    cfg = AgentConfig(
        charter="c", model="m", output_schema={"type": "object"},
        limits={"max_questions": 1},
    )
    assert cfg.limits.max_questions == 1


def test_shared_contracts_refuse_partial_success():
    with pytest.raises(ValidationError):
        Envelope(status="completed")  # no output
    with pytest.raises(ValidationError):
        Envelope(status="schema_invalid")  # no raw_text
    env = Envelope(status="error", exit_reason="budget", diagnostic="x")
    assert not env.completed
    with pytest.raises(ValidationError):
        ToolResult(ok=True, error=ToolError(code="timeout", message="m"))
    with pytest.raises(ValidationError):
        ToolResult(ok=False)
    with pytest.raises(ValidationError):
        Plan(tasks=[PlanTask(alias="a", objective="o", depends_on=["b"]), PlanTask(alias="b", objective="o", depends_on=["a"])])
    Plan(tasks=[PlanTask(alias="a", objective="o"), PlanTask(alias="b", objective="o", depends_on=["a"])])
    with pytest.raises(ValidationError):
        AgentConfig(charter="c", model="m", output_schema={"type": "string"})
    with pytest.raises(ValidationError):
        AgentConfig(charter="c", model="m", output_schema={"type": "object"}, builtin_tools=["run_python"])
    agent_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        TeamConfig(
            orchestrator={"model": "m"}, output_schema={"type": "object"},
            roster=[{"alias": "x", "agent_id": agent_id}],
            guardrails={"required_aliases": ["nope"]},
        )
    with pytest.raises(ValidationError):
        TeamConfig(orchestrator={"model": "m"}, output_schema={"type": "object"},
                   roster=[{"alias": "x", "agent_id": agent_id}], runs_as={"kind": "service"})
