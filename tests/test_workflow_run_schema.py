"""WF-M1 — workflow run + run-step schema (governance-grade run record).

Schema-shape tests for the two tables that make a workflow *runnable and
auditable*: ``workflow_run`` (one row per execution) and ``workflow_run_step``
(one row per node per execution). Together they answer, for every run: who
triggered it, when, how long it took end-to-end, and — per node — its input,
output, status, attempt count, and time taken.

Locked semantics (see product-feature-roadmap/workflow-execution/implementation.md §2):
  * ``workflow_run`` is workspace+tenant-scoped (both NOT NULL, cascade) and
    references its ``workflow`` (cascade). ``workflow_version_id`` /
    ``trigger_id`` are plain nullable UUIDs for now — no FK, because the
    version/trigger tables land in M6/M4; the columns exist so those slices add
    only the constraint, not a column.
  * ``actor_user_id`` is who triggered THIS run — nullable + SET NULL (cron /
    anonymous webhook have no actor). ``audit_principal_user_id`` is always set
    (author for cron, actor otherwise) and is RESTRICT, not SET NULL: the audit
    chain must never lose its principal (users are anonymised, not hard-deleted).
  * Full node input/output live in ``workflow_run_step`` (redactable per
    pii_fields in M8) — this is the record of truth; audit_log only references it.
  * ``attempts`` exposes Temporal retry count per step.

Pins the schema shape: fails before the tables.py change lands, passes after.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa


async def _columns(test_engine, table_name: str) -> dict:
    async with test_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: {
                c["name"]: c for c in sa.inspect(sync_conn).get_columns(table_name)
            }
        )


async def _indexes(test_engine, table_name: str) -> list[dict]:
    async with test_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).get_indexes(table_name)
        )


async def _foreign_keys(test_engine, table_name: str) -> list[dict]:
    async with test_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).get_foreign_keys(table_name)
        )


async def _enum_values(test_engine, enum_name: str) -> list[str]:
    async with test_engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                """
                SELECT e.enumlabel
                FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = :name
                ORDER BY e.enumsortorder
                """
            ),
            {"name": enum_name},
        )
        return [row[0] for row in result.fetchall()]


def _ondelete(fk: dict) -> str | None:
    return (fk.get("options") or {}).get("ondelete")


def _fk_to(fks: list[dict], referred_table: str, column: str) -> dict | None:
    for fk in fks:
        if fk["referred_table"] == referred_table and column in fk["constrained_columns"]:
            return fk
    return None


# ---------------------------------------------------------------------------
# workflow_run
# ---------------------------------------------------------------------------


class TestWorkflowRunColumns:
    @pytest.mark.asyncio
    async def test_required_columns_present(self, test_engine):
        cols = await _columns(test_engine, "workflow_run")
        expected = {
            "id",
            "tenant_id",
            "workspace_id",
            "workflow_id",
            "workflow_version_id",
            "trigger_id",
            "status",
            "actor_user_id",
            "actor_kind",
            "audit_principal_user_id",
            "temporal_run_id",
            "trigger_payload",
            "error_message",
            "created_at",
            "started_at",
            "finished_at",
        }
        assert expected <= set(cols), f"missing: {expected - set(cols)}"

    @pytest.mark.asyncio
    async def test_scoping_and_principal_not_null(self, test_engine):
        cols = await _columns(test_engine, "workflow_run")
        assert cols["tenant_id"]["nullable"] is False
        assert cols["workspace_id"]["nullable"] is False
        assert cols["workflow_id"]["nullable"] is False
        assert cols["actor_kind"]["nullable"] is False
        # The audit principal is always known — never nulled.
        assert cols["audit_principal_user_id"]["nullable"] is False

    @pytest.mark.asyncio
    async def test_actor_and_lifecycle_timestamps_nullable(self, test_engine):
        cols = await _columns(test_engine, "workflow_run")
        # No actor for cron / anonymous webhook.
        assert cols["actor_user_id"]["nullable"] is True
        # Set as the run progresses; null until then.
        assert cols["started_at"]["nullable"] is True
        assert cols["finished_at"]["nullable"] is True
        assert cols["temporal_run_id"]["nullable"] is True
        # Version / trigger FKs land in M6 / M4 — columns nullable for now.
        assert cols["workflow_version_id"]["nullable"] is True
        assert cols["trigger_id"]["nullable"] is True

    @pytest.mark.asyncio
    async def test_created_at_not_null(self, test_engine):
        cols = await _columns(test_engine, "workflow_run")
        assert cols["created_at"]["nullable"] is False

    @pytest.mark.asyncio
    async def test_trigger_payload_is_jsonb(self, test_engine):
        cols = await _columns(test_engine, "workflow_run")
        assert "JSON" in cols["trigger_payload"]["type"].__class__.__name__.upper()


class TestWorkflowRunEnums:
    @pytest.mark.asyncio
    async def test_run_status_enum_values(self, test_engine):
        assert await _enum_values(test_engine, "workflow_run_status") == [
            "queued",
            "running",
            "succeeded",
            "failed",
            "cancelled",
        ]

    @pytest.mark.asyncio
    async def test_actor_kind_enum_values(self, test_engine):
        assert await _enum_values(test_engine, "workflow_actor_kind") == [
            "user",
            "cron",
            "event",
            "webhook_auth",
            "webhook_anon",
            "fan_out_member",
        ]


class TestWorkflowRunForeignKeys:
    @pytest.mark.asyncio
    async def test_tenant_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "workflow_run")
        fk = _fk_to(fks, "tenant", "tenant_id")
        assert fk is not None and _ondelete(fk) == "CASCADE"

    @pytest.mark.asyncio
    async def test_workspace_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "workflow_run")
        fk = _fk_to(fks, "workspace", "workspace_id")
        assert fk is not None and _ondelete(fk) == "CASCADE"

    @pytest.mark.asyncio
    async def test_workflow_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "workflow_run")
        fk = _fk_to(fks, "workflow", "workflow_id")
        assert fk is not None and _ondelete(fk) == "CASCADE"

    @pytest.mark.asyncio
    async def test_actor_fk_set_null(self, test_engine):
        fks = await _foreign_keys(test_engine, "workflow_run")
        fk = _fk_to(fks, "user", "actor_user_id")
        assert fk is not None and _ondelete(fk) == "SET NULL"

    @pytest.mark.asyncio
    async def test_audit_principal_fk_restrict(self, test_engine):
        fks = await _foreign_keys(test_engine, "workflow_run")
        fk = _fk_to(fks, "user", "audit_principal_user_id")
        assert fk is not None and _ondelete(fk) == "RESTRICT"


class TestWorkflowRunIndexes:
    @pytest.mark.asyncio
    async def test_workflow_created_index(self, test_engine):
        indexes = await _indexes(test_engine, "workflow_run")
        cols = [tuple(ix["column_names"]) for ix in indexes]
        # The run-history list path: runs of a workflow, newest first.
        assert ("workflow_id", "created_at") in cols

    @pytest.mark.asyncio
    async def test_tenant_workspace_index(self, test_engine):
        indexes = await _indexes(test_engine, "workflow_run")
        cols = [tuple(ix["column_names"]) for ix in indexes]
        assert ("tenant_id", "workspace_id") in cols


# ---------------------------------------------------------------------------
# workflow_run_step
# ---------------------------------------------------------------------------


class TestWorkflowRunStepColumns:
    @pytest.mark.asyncio
    async def test_required_columns_present(self, test_engine):
        cols = await _columns(test_engine, "workflow_run_step")
        expected = {
            "id",
            "run_id",
            "step_id",
            "node_kind",
            "status",
            "input_json",
            "output_json",
            "attempts",
            "pii_classification",
            "error_message",
            "created_at",
            "started_at",
            "finished_at",
        }
        assert expected <= set(cols), f"missing: {expected - set(cols)}"

    @pytest.mark.asyncio
    async def test_identity_columns_not_null(self, test_engine):
        cols = await _columns(test_engine, "workflow_run_step")
        assert cols["run_id"]["nullable"] is False
        assert cols["step_id"]["nullable"] is False
        assert cols["node_kind"]["nullable"] is False
        assert cols["status"]["nullable"] is False
        assert cols["attempts"]["nullable"] is False
        assert cols["created_at"]["nullable"] is False

    @pytest.mark.asyncio
    async def test_io_and_timing_nullable(self, test_engine):
        cols = await _columns(test_engine, "workflow_run_step")
        assert cols["input_json"]["nullable"] is True
        assert cols["output_json"]["nullable"] is True
        assert cols["started_at"]["nullable"] is True
        assert cols["finished_at"]["nullable"] is True

    @pytest.mark.asyncio
    async def test_io_columns_are_jsonb(self, test_engine):
        cols = await _columns(test_engine, "workflow_run_step")
        assert "JSON" in cols["input_json"]["type"].__class__.__name__.upper()
        assert "JSON" in cols["output_json"]["type"].__class__.__name__.upper()


class TestWorkflowRunStepEnum:
    @pytest.mark.asyncio
    async def test_step_status_enum_values(self, test_engine):
        # Compared against pg_enum sort order, so a new label belongs where its
        # migration placed it. 'expired' (NC-257) was added AFTER 'skipped': an
        # unanswered human wait, which is neither a failure (nothing
        # malfunctioned) nor a success (nobody decided).
        assert await _enum_values(test_engine, "workflow_run_step_status") == [
            "pending",
            "running",
            "succeeded",
            "failed",
            "skipped",
            "expired",
        ]


class TestWorkflowRunStepForeignKeys:
    @pytest.mark.asyncio
    async def test_run_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "workflow_run_step")
        fk = _fk_to(fks, "workflow_run", "run_id")
        assert fk is not None and _ondelete(fk) == "CASCADE"


class TestWorkflowRunStepIndexes:
    @pytest.mark.asyncio
    async def test_run_index(self, test_engine):
        indexes = await _indexes(test_engine, "workflow_run_step")
        cols = [tuple(ix["column_names"]) for ix in indexes]
        # Steps of a run — the per-run inspector path.
        assert ("run_id",) in cols
