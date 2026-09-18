"""dashboard.pinned — keep a board at the top of the switcher.

The sidebar rail lists dashboards the way it lists chats, and chats have had
rename / pin / delete on every row for a long time. Pin was the only one of the
three with nowhere to go: `chat.pinned` exists, `dashboard` had no equivalent.

Deliberately a column and not client state. The obvious shortcut is
localStorage — it needs no migration and looks identical on the machine you
tried it on. The immediately preceding work in this feature shipped exactly that
shortcut for the "On <dashboard>" chip, and it came back as a bug report the
first time the page was refreshed. A pin the user sets is a preference about
their workspace, not a fact about one browser.

Mirrors `chat.pinned` exactly — NOT NULL, server_default false — so the two
rails sort by the same rule and an existing row needs no backfill.

Revision ID: c9f4a2e6b1d8
Revises: b8d3f5a1c7e9
Create Date: 2026-08-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c9f4a2e6b1d8"
down_revision: Union[str, Sequence[str], None] = "b8d3f5a1c7e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dashboard",
        sa.Column(
            "pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("dashboard", "pinned")
