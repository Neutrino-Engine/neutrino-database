"""NC-881 — chat_kind gains canvas_thread (comment threads on a canvas).

Revision ID: a7c3e9f1b5d2
Revises: f4b8d2a6c1e9
"""

from alembic import op

revision: str = "a7c3e9f1b5d2"
down_revision: str | None = "f4b8d2a6c1e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE chat_kind ADD VALUE IF NOT EXISTS 'canvas_thread'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums; the unused label stays.
    pass
