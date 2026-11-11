"""incident_report: customer-facing incident report versions (NC-877).

One row per report version for a ServiceOps incident ticket. The snapshot hash
makes a version claim idempotent; sent_at marks a version as emailed. Derived
facts only: no report text is stored.

Revision ID: f4b8d2a6c1e9
Revises: e3a7c9d1f5b2
Create Date: 2026-11-11
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f4b8d2a6c1e9"
down_revision = "e3a7c9d1f5b2"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=False)
TS = sa.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "incident_report",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", sa.BigInteger, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("snapshot_hash", sa.Text, nullable=False),
        sa.Column("customer_id", sa.Text, nullable=True),
        sa.Column("severity", sa.String(8), nullable=True),
        sa.Column("group_key", sa.Text, nullable=True),
        sa.Column("reasons", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sent_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "ticket_id", "snapshot_hash", name="uq_incident_report_snapshot"),
        sa.UniqueConstraint("workspace_id", "ticket_id", "version", name="uq_incident_report_version"),
    )
    op.create_index("ix_incident_report_tier_sent", "incident_report", ["workspace_id", "tier", "sent_at"])


def downgrade() -> None:
    op.drop_index("ix_incident_report_tier_sent", table_name="incident_report")
    op.drop_table("incident_report")
