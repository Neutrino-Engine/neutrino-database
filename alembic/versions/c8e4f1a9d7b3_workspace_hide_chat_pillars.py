"""add workspace.hide_chat_pillars (Unified-only chat surface)

NC-500. The chat sidebar has always rendered its four-row Pillars picker —
Unified, Knowledge Studio, Data Studio, Dynamic Workflows — for every
workspace, so every member is asked which engine should answer before they
have asked anything. For the executive audience the answer is always "just
answer me", and Unified already spans all three pillars (``pillar_mode=AUTO``
→ the UnifiedChatAgent), so the picker only exposes plumbing we configure on
the customer's behalf.

This column is a *presentation* switch, deliberately separate from
``workspace.enabled_pillars``:

  * ``enabled_pillars``   — what the workspace is allowed to do. Turning a
    pillar off here removes the capability (and realigns
    ``orchestrator_config.router_mode``).
  * ``hide_chat_pillars`` — whether the chat page offers a choice among the
    capabilities it already has. Nothing is revoked; the picker is simply
    not drawn and chat runs Unified.

Conflating the two would mean disabling Data Studio to tidy the chat UI,
which would strip a pillar we intentionally set up.

Default is ``true``, and existing rows inherit it: every workspace becomes
Unified-only on deploy until an admin turns the picker back on from
Workspace settings → Capabilities & Routing. That is intentional (the
CXO path is the default path), and it is the one behavioural change in
this migration worth a release note.

Chats already stamped with a pillar are untouched — ``chat.pillar`` still
drives routing on reopen, so history keeps reporting which data actually
grounded those answers.

Revision ID: c8e4f1a9d7b3
Revises: g1h2i3j4k5l6
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8e4f1a9d7b3"
down_revision: Union[str, Sequence[str], None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default stays on the column (not dropped post-backfill): the
    # gateway's workspace auto-create in login_flow.py inserts without this
    # column, and a new workspace must land Unified-only like every other.
    op.add_column(
        "workspace",
        sa.Column(
            "hide_chat_pillars",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("workspace", "hide_chat_pillars")
