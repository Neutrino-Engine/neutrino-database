"""NC-691: dashboard_share + private-by-default dashboards.

Revision ID: a9c1e3f5b7d2
Revises: f2b8d4a6c0e3

* Creates ``dashboard_share`` — the members a ``restricted`` dashboard is
  shared with.
* Flips ``dashboard.visibility``'s server default from 'workspace_members' to
  'restricted'. Existing rows are NOT touched: every dashboard made before this
  keeps 'workspace_members', i.e. stays published to its workspace.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9c1e3f5b7d2"
down_revision: Union[str, Sequence[str], None] = "f2b8d4a6c0e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_share",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "dashboard_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("dashboard.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "dashboard_id", "user_id", name="ux_dashboard_share_dashboard_user"
        ),
    )
    op.create_index("ix_dashboard_share_user", "dashboard_share", ["user_id"])
    op.alter_column(
        "dashboard", "visibility", server_default=sa.text("'restricted'")
    )


def downgrade() -> None:
    op.alter_column(
        "dashboard", "visibility", server_default=sa.text("'workspace_members'")
    )
    op.drop_index("ix_dashboard_share_user", table_name="dashboard_share")
    op.drop_table("dashboard_share")
