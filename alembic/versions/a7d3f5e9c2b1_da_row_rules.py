"""per-member DA row rules (NC-845).

Adds da_row_rule (the column that filters a catalog table, per workspace)
and da_member_row_value (the values each member may see). connector-service
fences ruled tables in the agent's SQL; nothing is written to the
customer's database.

Revision ID: a7d3f5e9c2b1
Revises: 9c4d2e7f1b38
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "a7d3f5e9c2b1"
down_revision = "9c4d2e7f1b38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "da_row_rule",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("da_catalog_table_id", UUID(as_uuid=False),
                  sa.ForeignKey("da_catalog_table.id", ondelete="CASCADE"), nullable=False),
        sa.Column("column_name", sa.String(255), nullable=False),
        sa.Column("parent_rule_id", UUID(as_uuid=False), sa.ForeignKey("da_row_rule.id", ondelete="NO ACTION"),
                  nullable=True),
        sa.Column("parent_column_name", sa.String(255), nullable=True),
        sa.Column("created_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("(parent_rule_id IS NULL) = (parent_column_name IS NULL)",
                           name="ck_da_row_rule_link_complete"),
        sa.CheckConstraint("parent_rule_id <> id", name="ck_da_row_rule_not_self_linked"),
        sa.UniqueConstraint("workspace_id", "da_catalog_table_id", name="ux_da_row_rule_workspace_table"),
    )
    op.create_table(
        "da_member_row_value",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rule_id", UUID(as_uuid=False), sa.ForeignKey("da_row_rule.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("created_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("rule_id", "user_id", "value", name="ux_da_member_row_value"),
    )
    op.create_index("ix_da_member_row_value_user", "da_member_row_value", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_da_member_row_value_user", table_name="da_member_row_value")
    op.drop_table("da_member_row_value")
    op.drop_table("da_row_rule")
