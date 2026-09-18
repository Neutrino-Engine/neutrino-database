"""NC-519 — make per-user memory opt-OUT rather than opt-in.

``user_memory_settings.enabled`` shipped with ``server_default false`` so the
feature stayed dark per user even after an operator enabled it for the
environment. That is being reversed by product decision: within a deployment
where ``unified_memory_enabled`` is on, every user should capture memory without
having to find a settings page first.

What still gates capture after this:

  * ``unified_memory_enabled`` (agent-platform setting, default False) — the
    environment-level switch. Nothing is captured anywhere until it is on.
  * ``user_memory_settings.enabled = false`` — an explicit per-user opt-OUT.
  * ``chat.incognito`` — never captured, never injected, unchanged.

Existing rows are backfilled to TRUE. Only rows that already say ``false`` would
be affected, and at the time of writing the table is empty in every environment
(the feature has never been enabled anywhere), so there is no user who has
deliberately opted out for this to override. If that stops being true before
this ships, drop the UPDATE and let existing rows keep their value — silently
re-enabling someone who turned it off would be the one genuinely bad outcome
here.

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-08-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "i3j4k5l6m7n8"
down_revision: Union[str, Sequence[str], None] = "h2i3j4k5l6m7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "user_memory_settings",
        "enabled",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.text("true"),
    )
    # See the module docstring: safe only while no user has deliberately opted
    # out. Guarded to the false rows so the statement is explicit about what it
    # touches rather than rewriting the whole table.
    op.execute(
        "UPDATE user_memory_settings SET enabled = true WHERE enabled = false"
    )


def downgrade() -> None:
    op.alter_column(
        "user_memory_settings",
        "enabled",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.text("false"),
    )
