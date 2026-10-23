"""erasure_request table + per-tenant retention columns (NC-795 G-21, G-44).

* tenant.retention_{chat,file,document,trace,run_event}_days: nullable INT,
  NULL = no tenant-specific period. CHECK > 0.
* erasure_request: one row per user / workspace / tenant erasure, driven by
  the gateway retention runner. ``steps`` holds per-service progress so a
  failed run resumes. At most one open (pending/running) request per target.

Revision ID: b5d2e8f1a9c3
Revises: b4d2e6f8a1c3
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "b5d2e8f1a9c3"
down_revision = "b4d2e6f8a1c3"
branch_labels = None
depends_on = None

_RETENTION = (
    "retention_chat_days",
    "retention_file_days",
    "retention_document_days",
    "retention_trace_days",
    "retention_run_event_days",
)


def upgrade() -> None:
    for name in _RETENTION:
        op.add_column("tenant", sa.Column(name, sa.Integer, nullable=True))
    op.create_check_constraint(
        "ck_tenant_retention_positive",
        "tenant",
        " AND ".join(f"COALESCE({n}, 1) > 0" for n in _RETENTION),
    )

    op.create_table(
        "erasure_request",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=False),
                  sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.Text, nullable=False),
        sa.Column("target_id", UUID(as_uuid=False), nullable=False),
        sa.Column("requested_by", UUID(as_uuid=False),
                  sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("not_before", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("steps", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("scope IN ('user', 'workspace', 'tenant')",
                           name="ck_erasure_request_scope"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_erasure_request_status",
        ),
    )
    op.create_index("ix_erasure_request_due", "erasure_request", ["status", "not_before"])
    op.create_index(
        "ux_erasure_request_open_target", "erasure_request", ["scope", "target_id"],
        unique=True, postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("ux_erasure_request_open_target", table_name="erasure_request")
    op.drop_index("ix_erasure_request_due", table_name="erasure_request")
    op.drop_table("erasure_request")
    op.drop_constraint("ck_tenant_retention_positive", "tenant", type_="check")
    for name in reversed(_RETENTION):
        op.drop_column("tenant", name)
