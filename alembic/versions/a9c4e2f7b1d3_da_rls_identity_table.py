"""Identity-table row filtering (NC-864 phase 2).

Adds the mode, identity source and multiple-match policy to
integration_da_config, plus per-table status and shared-email approvals.

Revision ID: a9c4e2f7b1d3
Revises: f1a6d2c8b4e7
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "a9c4e2f7b1d3"
down_revision = "f1a6d2c8b4e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("integration_da_config", sa.Column(
        "row_scope_mode", sa.String(20), nullable=False, server_default=sa.text("'native'")))
    op.add_column("integration_da_config", sa.Column("identity_source", JSONB, nullable=True))
    op.add_column("integration_da_config", sa.Column(
        "multi_match_policy", sa.String(20), nullable=False,
        server_default=sa.text("'require_approval'")))
    op.create_check_constraint(
        "ck_integration_da_config_row_scope_mode", "integration_da_config",
        "row_scope_mode IN ('native', 'identity_table')")
    op.create_check_constraint(
        "ck_integration_da_config_multi_match_policy", "integration_da_config",
        "multi_match_policy IN ('deny', 'require_approval', 'allow_all')")

    op.create_table(
        "da_rls_table_status",
        sa.Column("integration_id", UUID(as_uuid=False),
                  sa.ForeignKey("integration.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("schema_name", sa.String(255), primary_key=True),
        sa.Column("table_name", sa.String(255), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("path", JSONB, nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=False),
                  sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('protected', 'reference', 'blocked')",
                           name="ck_da_rls_table_status_status"),
    )
    op.create_table(
        "da_rls_identity_approval",
        sa.Column("integration_id", UUID(as_uuid=False),
                  sa.ForeignKey("integration.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("login_email", sa.String(320), primary_key=True),
        sa.Column("approved_keys", JSONB, nullable=False),
        sa.Column("approved_by", UUID(as_uuid=False),
                  sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("da_rls_identity_approval")
    op.drop_table("da_rls_table_status")
    op.drop_constraint("ck_integration_da_config_multi_match_policy", "integration_da_config")
    op.drop_constraint("ck_integration_da_config_row_scope_mode", "integration_da_config")
    op.drop_column("integration_da_config", "multi_match_policy")
    op.drop_column("integration_da_config", "identity_source")
    op.drop_column("integration_da_config", "row_scope_mode")
