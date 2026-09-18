"""workspace_authz_store

Revision ID: 470445259496
Revises: c9f4a2e6b1d8
Create Date: 2026-08-26 00:36:41.736415

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "470445259496"
down_revision: Union[str, Sequence[str], None] = "c9f4a2e6b1d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_authz_store",
        sa.Column("workspace_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("store_id", sa.String(length=64), nullable=True),
        sa.Column("model_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspace.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("workspace_authz_store")
