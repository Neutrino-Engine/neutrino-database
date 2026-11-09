"""da_member_identity (NC-864).

The warehouse identity a member acts as on a row-scoped connection. No row
means the member acts as their own email.

Revision ID: f1a6d2c8b4e7
Revises: c3e8a1f4d7b6
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "f1a6d2c8b4e7"
down_revision = "c3e8a1f4d7b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "da_member_identity",
        sa.Column("integration_id", UUID(as_uuid=False),
                  sa.ForeignKey("integration.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False),
                  sa.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("identity", sa.String(320), nullable=False),
        sa.Column("set_by", UUID(as_uuid=False),
                  sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_da_member_identity_user_id", "da_member_identity", ["user_id"])


def downgrade() -> None:
    op.drop_table("da_member_identity")
