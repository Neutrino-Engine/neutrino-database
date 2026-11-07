"""per-member row ranges for DA row rules (NC-845).

A member may see rows whose ruled column lies in a range, beside the exact
values in da_member_row_value. Either bound may be open.

Revision ID: b4e8c2f6a9d3
Revises: a7d3f5e9c2b1
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "b4e8c2f6a9d3"
down_revision = "a7d3f5e9c2b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "da_member_row_range",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rule_id", UUID(as_uuid=False), sa.ForeignKey("da_row_rule.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("min_value", sa.Text, nullable=True),
        sa.Column("max_value", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("min_value IS NOT NULL OR max_value IS NOT NULL", name="ck_da_member_row_range_bounded"),
    )
    op.create_index("ix_da_member_row_range_user", "da_member_row_range", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_da_member_row_range_user", table_name="da_member_row_range")
    op.drop_table("da_member_row_range")
