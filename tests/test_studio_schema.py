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
    studio_team,
    studio_team_version,
    studio_trigger_event,
    tenant,
    user as user_table,
    user_memory,
    workspace,
)

STUDIO_TABLES = {
    "studio_agent", "studio_agent_version", "studio_team", "studio_team_version",
    "studio_api_key", "studio_event_trigger", "studio_schedule", "studio_run",
    "studio_agent_task", "studio_approval", "studio_trigger_event",
    "studio_test_case", "studio_workspace_file",
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
