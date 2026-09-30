"""NC-694: message drafts — parent_message_id on message, active leaf on chat.

Revision ID: c4d8e2f6a1b3
Revises: b3e7f1a9c2d4
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4d8e2f6a1b3"
down_revision: Union[str, Sequence[str], None] = "b3e7f1a9c2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "message",
        sa.Column(
            "parent_message_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("message.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_message_parent_message_id", "message", ["parent_message_id"])
    op.add_column(
        "chat",
        sa.Column("active_leaf_message_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    # Every existing chat is one straight line: each live message's parent is
    # the live message before it, and the newest one is the active leaf.
    # SYSTEM rows (the chat seed, compaction summaries written mid-run) stay out
    # of the chain, so an answer always hangs off the question it answers.
    op.execute(
        """
        UPDATE message m SET parent_message_id = p.prev
        FROM (
            SELECT id, LAG(id) OVER (PARTITION BY chat_id ORDER BY created_at, id) AS prev
            FROM message WHERE deleted_at IS NULL AND role <> 'SYSTEM'
        ) p
        WHERE m.id = p.id AND p.prev IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE chat c SET active_leaf_message_id = l.id
        FROM (
            SELECT DISTINCT ON (chat_id) chat_id, id
            FROM message WHERE deleted_at IS NULL AND role <> 'SYSTEM'
            ORDER BY chat_id, created_at DESC, id DESC
        ) l
        WHERE c.id = l.chat_id
        """
    )


def downgrade() -> None:
    op.drop_column("chat", "active_leaf_message_id")
    op.drop_index("ix_message_parent_message_id", table_name="message")
    op.drop_column("message", "parent_message_id")
