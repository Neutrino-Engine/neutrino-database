"""Agent Studio is on by default for every workspace.

The pillar shipped opt-in: ``workspace.enabled_pillars`` defaulted to ``'{}'``
and nothing added AGENT_STUDIO, so the surface was invisible until an admin
found the capabilities page. Product decision: it is a default, not an
upsell.

Two halves, and both are needed — the server default only reaches rows created
from here on, and the backfill only reaches rows that exist today.

Down leaves the backfilled value alone. Removing a pillar an admin may since
have come to rely on is a worse outcome than a default that outlives the
downgrade, and the column is a list, so the value is not wrong — just no
longer automatic.

Revision ID: e1a5c9d3b7f4
Revises: d9c4e2f6a8b1
"""

from alembic import op

revision = "e1a5c9d3b7f4"
down_revision = "d9c4e2f6a8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE workspace ALTER COLUMN enabled_pillars "
        "SET DEFAULT '{AGENT_STUDIO}'::pillar[]"
    )
    # Only rows that do not already carry it, so a re-run is a no-op and an
    # admin who turned it OFF deliberately... does get it back. That is the
    # cost of a one-shot backfill; there is no "was this ever off on purpose"
    # bit to consult, and the alternative is the pillar never reaching the
    # workspaces that exist today.
    op.execute(
        "UPDATE workspace SET enabled_pillars = "
        "array_append(enabled_pillars, 'AGENT_STUDIO'::pillar) "
        "WHERE NOT ('AGENT_STUDIO'::pillar = ANY(enabled_pillars))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE workspace ALTER COLUMN enabled_pillars SET DEFAULT '{}'::pillar[]")
