"""WF-VS2.1c — workflow definition schema.

Schema-shape tests for the ``workflow`` table — the workspace-scoped store of
workflow definitions the Workflow Execution pillar's GenericGraphWorkflow
interprets. The graph (nodes + edges) lives in the ``graph`` JSONB column;
Temporal owns *execution* state (event histories), this table owns the
*definition*.

Locked semantics:
  * Workspace-scoped: every workflow belongs to exactly one workspace
    (workspace_id NOT NULL), under a tenant (tenant_id NOT NULL). Both cascade.
  * ``status`` lifecycle: draft → active → disabled → archived; default draft.
  * ``created_by`` is metadata, not ownership — a workflow outlives its author,
    so the FK is SET NULL + nullable (deleting the user nulls it, keeps the row).

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


class TestWorkflowColumns:
    @pytest.mark.asyncio
    async def test_required_columns_present(self, test_engine):
        cols = await _columns(test_engine, "workflow")
        expected = {
            "id",
            "tenant_id",
            "workspace_id",
            "name",
            "description",
            "graph",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        }
        assert expected <= set(cols), f"missing: {expected - set(cols)}"

    @pytest.mark.asyncio
    async def test_scoping_columns_not_null(self, test_engine):
        cols = await _columns(test_engine, "workflow")
        assert cols["tenant_id"]["nullable"] is False
        assert cols["workspace_id"]["nullable"] is False
        assert cols["name"]["nullable"] is False
        assert cols["graph"]["nullable"] is False

    @pytest.mark.asyncio
    async def test_description_and_created_by_nullable(self, test_engine):
        cols = await _columns(test_engine, "workflow")
        assert cols["description"]["nullable"] is True
        # created_by is metadata, not ownership — nulled on user delete.
        assert cols["created_by"]["nullable"] is True

    @pytest.mark.asyncio
    async def test_graph_is_jsonb(self, test_engine):
        cols = await _columns(test_engine, "workflow")
        assert "JSON" in cols["graph"]["type"].__class__.__name__.upper()


class TestWorkflowStatusEnum:
    @pytest.mark.asyncio
    async def test_status_enum_values(self, test_engine):
        assert await _enum_values(test_engine, "workflow_status") == [
            "draft",
            "active",
            "disabled",
            "archived",
        ]


class TestWorkflowForeignKeys:
    @pytest.mark.asyncio
    async def test_tenant_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "workflow")
        fk = _fk_to(fks, "tenant", "tenant_id")
        assert fk is not None and _ondelete(fk) == "CASCADE"

    @pytest.mark.asyncio
    async def test_workspace_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "workflow")
        fk = _fk_to(fks, "workspace", "workspace_id")
        assert fk is not None and _ondelete(fk) == "CASCADE"

    @pytest.mark.asyncio
    async def test_created_by_fk_set_null(self, test_engine):
        fks = await _foreign_keys(test_engine, "workflow")
        fk = _fk_to(fks, "user", "created_by")
        assert fk is not None and _ondelete(fk) == "SET NULL"


class TestWorkflowIndexes:
    @pytest.mark.asyncio
    async def test_tenant_workspace_index(self, test_engine):
        indexes = await _indexes(test_engine, "workflow")
        cols = [tuple(ix["column_names"]) for ix in indexes]
        assert ("tenant_id", "workspace_id") in cols


async def test_workflow_show_in_chat_defaults_true(test_engine) -> None:
    """NC-920 — show_in_chat lists the workflow in the chat menus; existing
    rows and new ones default to listed."""
    cols = await _columns(test_engine, "workflow")
    assert "show_in_chat" in cols
    assert cols["show_in_chat"]["nullable"] is False
    assert "true" in str(cols["show_in_chat"]["default"]).lower()
