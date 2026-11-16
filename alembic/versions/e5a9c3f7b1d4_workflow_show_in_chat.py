"""NC-920 — workflow.show_in_chat: list the workflow in the chat `/` and `@` menus.

Existing rows keep true, so every deployment lists what it lists today.

Revision ID: e5a9c3f7b1d4
Revises: a7c3e9f1b5d2
"""

import sqlalchemy as sa
from alembic import op

revision: str = "e5a9c3f7b1d4"
down_revision: str | None = "a7c3e9f1b5d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflow", sa.Column("show_in_chat", sa.Boolean(), nullable=False, server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("workflow", "show_in_chat")
