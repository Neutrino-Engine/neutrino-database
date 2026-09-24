"""message_feedback — thumbs up/down (+ optional detail) on assistant replies.

Revision ID: b3e7f1a9c2d4
Revises: a9c1e3f5b7d2
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3e7f1a9c2d4"
down_revision: Union[str, Sequence[str], None] = "a9c1e3f5b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("message.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.String(8), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("expected", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "message_id", "user_id", name="ux_message_feedback_message_user"
        ),
        sa.CheckConstraint(
            "rating IN ('up', 'down')", name="ck_message_feedback_rating"
        ),
        sa.CheckConstraint(
            "score IS NULL OR score BETWEEN 1 AND 5",
            name="ck_message_feedback_score",
        ),
    )
    op.create_index(
        "ix_message_feedback_tenant_created",
        "message_feedback",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_message_feedback_tenant_created", table_name="message_feedback")
    op.drop_table("message_feedback")
