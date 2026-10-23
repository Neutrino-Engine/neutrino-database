"""workflow test cases + gate runs (NC-797 ADLC close-out C1).

``workflow_test_case`` holds a trigger payload and expectations on step outputs
and agent-node tool calls; ``workflow_gate_run`` holds one execution of a
version's cases (sandboxed, shadow mechanics). New tables only: nothing
existing changes, so no backfill.

Revision ID: c1e7a3d9f2b4
Revises: 7e3b9c1d5a20
Create Date: 2026-10-23
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "c1e7a3d9f2b4"
down_revision = "7e3b9c1d5a20"
branch_labels = None
depends_on = None


def _uuid(name, fk=None, ondelete=None, nullable=True, **kw):
    args = [sa.ForeignKey(fk, ondelete=ondelete)] if fk else []
    return sa.Column(name, UUID(as_uuid=False), *args, nullable=nullable, **kw)


def upgrade() -> None:
    op.create_table(
        "workflow_test_case",
        _uuid("id", nullable=False, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _uuid("tenant_id", "tenant.id", "CASCADE", nullable=False),
        _uuid("workspace_id", "workspace.id", "CASCADE", nullable=False),
        _uuid("workflow_id", "workflow.id", "CASCADE", nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("input", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("expectations", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("kind", sa.String(16), nullable=False, server_default=sa.text("'normal'")),
        _uuid("created_by", "user.id", "SET NULL"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('normal','injection')", name="ck_workflow_test_case_kind"),
    )
    op.create_index("ix_workflow_test_case_workflow", "workflow_test_case", ["workflow_id"])

    op.create_table(
        "workflow_gate_run",
        _uuid("id", nullable=False, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _uuid("tenant_id", "tenant.id", "CASCADE", nullable=False),
        _uuid("workspace_id", "workspace.id", "CASCADE", nullable=False),
        _uuid("workflow_id", "workflow.id", "CASCADE", nullable=False),
        _uuid("version_id", "workflow_version.id", "CASCADE", nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'running'")),
        sa.Column("results", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        _uuid("created_by", "user.id", "SET NULL"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('running','passed','failed','error')", name="ck_workflow_gate_run_status"),
    )
    op.create_index("ix_workflow_gate_run_version", "workflow_gate_run", ["version_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_gate_run_version", table_name="workflow_gate_run")
    op.drop_table("workflow_gate_run")
    op.drop_index("ix_workflow_test_case_workflow", table_name="workflow_test_case")
    op.drop_table("workflow_test_case")
