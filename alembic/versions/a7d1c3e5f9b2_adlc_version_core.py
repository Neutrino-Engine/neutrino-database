"""ADLC WS1: version core.

- ``workflow_version``: immutable published snapshots of ``workflow.graph``.
- ``workflow.active_version_id`` / ``studio_agent.active_version_id`` /
  ``studio_team.active_version_id``: the version every real run executes.
- ``lineage_id`` on all three: a stable identity that survives export/import.
- ``content_hash`` / ``change_note`` on the studio version tables.
- ``workflow_run.workflow_version_id`` gains its FK.

Backfill changes no behaviour:
- each studio agent/team points at its newest version, which is what "latest
  published" meant before;
- each workflow that is active, or has an ACTIVE trigger, gets v1 from its
  current graph, which is the graph its triggers ran until today.

Revision ID: a7d1c3e5f9b2
Revises: 1e84bef559a6
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "a7d1c3e5f9b2"
down_revision: Union[str, Sequence[str], None] = "1e84bef559a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_version",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", UUID(as_uuid=False), sa.ForeignKey("workflow.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("graph", JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("published_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workflow_id", "version", name="uq_workflow_version"),
        sa.CheckConstraint("version >= 1", name="ck_workflow_version_positive"),
    )

    for table, version_table, fk in (
        ("workflow", "workflow_version", "fk_workflow_active_version"),
        ("studio_agent", "studio_agent_version", "fk_studio_agent_active_version"),
        ("studio_team", "studio_team_version", "fk_studio_team_active_version"),
    ):
        op.add_column(table, sa.Column("active_version_id", UUID(as_uuid=False), nullable=True))
        op.create_foreign_key(fk, table, version_table, ["active_version_id"], ["id"], ondelete="SET NULL")
        # Existing rows: lineage = own id. New rows: the server default.
        op.add_column(table, sa.Column("lineage_id", UUID(as_uuid=False), nullable=True))
        op.execute(f"UPDATE {table} SET lineage_id = id")
        op.alter_column(table, "lineage_id", nullable=False, server_default=sa.text("gen_random_uuid()"))

    for version_table in ("studio_agent_version", "studio_team_version"):
        op.add_column(version_table, sa.Column("content_hash", sa.String(64), nullable=True))
        op.add_column(version_table, sa.Column("change_note", sa.Text(), nullable=True))

    # A dangling id (from before the table existed) would fail the FK.
    op.execute("UPDATE workflow_run SET workflow_version_id = NULL WHERE workflow_version_id IS NOT NULL")
    op.create_foreign_key(
        "fk_workflow_run_version", "workflow_run", "workflow_version",
        ["workflow_version_id"], ["id"], ondelete="SET NULL",
    )

    # ── backfill ────────────────────────────────────────────────────────
    for kind in ("agent", "team"):
        op.execute(f"""
            UPDATE studio_{kind} s SET active_version_id = v.id
            FROM (
                SELECT DISTINCT ON ({kind}_id) id, {kind}_id
                FROM studio_{kind}_version ORDER BY {kind}_id, version DESC
            ) v
            WHERE v.{kind}_id = s.id
        """)
        op.execute(f"""
            UPDATE studio_{kind}_version
            SET content_hash = encode(sha256(convert_to(config::text, 'UTF8')), 'hex')
        """)

    op.execute("""
        INSERT INTO workflow_version
            (id, tenant_id, workspace_id, workflow_id, version, graph, content_hash,
             change_note, published_by)
        SELECT gen_random_uuid(), w.tenant_id, w.workspace_id, w.id, 1, w.graph,
               encode(sha256(convert_to(w.graph::text, 'UTF8')), 'hex'),
               'Backfilled from the live graph (ADLC WS1)', w.created_by
        FROM workflow w
        WHERE w.status = 'active'
           OR EXISTS (
               SELECT 1 FROM workflow_trigger t
               WHERE t.workflow_id = w.id AND t.status = 'active'
           )
    """)
    op.execute("""
        UPDATE workflow w SET active_version_id = v.id
        FROM workflow_version v WHERE v.workflow_id = w.id
    """)


def downgrade() -> None:
    op.drop_constraint("fk_workflow_run_version", "workflow_run", type_="foreignkey")
    for version_table in ("studio_agent_version", "studio_team_version"):
        op.drop_column(version_table, "change_note")
        op.drop_column(version_table, "content_hash")
    for table, fk in (
        ("workflow", "fk_workflow_active_version"),
        ("studio_agent", "fk_studio_agent_active_version"),
        ("studio_team", "fk_studio_team_active_version"),
    ):
        op.drop_constraint(fk, table, type_="foreignkey")
        op.drop_column(table, "active_version_id")
        op.drop_column(table, "lineage_id")
    op.drop_table("workflow_version")
