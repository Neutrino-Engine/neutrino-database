"""NC-199 TDS Review C6: Studio event triggers can target a workflow.

* studio_event_trigger: team_id nullable; workflow_id FK workflow.id
  (CASCADE) + runs_as JSONB; CHECK exactly one of team_id / workflow_id.
* studio_trigger_event: team_id nullable; dedupe unique becomes
  (trigger_id, item_key).
* studio_run.team_id: FK dropped — a single-agent run (synthetic team, C5)
  stores the agent id there; teams are soft-deleted so the cascade was inert.

Revision ID: d5e9f3a7b1c2
Revises: c4d8e2f6a1b3
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5e9f3a7b1c2"
down_revision: Union[str, Sequence[str], None] = "c4d8e2f6a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("studio_event_trigger", "team_id", nullable=True)
    op.add_column(
        "studio_event_trigger",
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("workflow.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column("studio_event_trigger", sa.Column("runs_as", postgresql.JSONB, nullable=True))
    op.create_check_constraint(
        "ck_studio_event_trigger_target",
        "studio_event_trigger",
        "(team_id IS NULL) <> (workflow_id IS NULL)",
    )

    op.alter_column("studio_trigger_event", "team_id", nullable=True)
    op.drop_constraint("uq_studio_trigger_event_item", "studio_trigger_event", type_="unique")
    op.create_unique_constraint(
        "uq_studio_trigger_event_item", "studio_trigger_event", ["trigger_id", "item_key"]
    )

    op.drop_constraint("studio_run_team_id_fkey", "studio_run", type_="foreignkey")


def downgrade() -> None:
    # Rows only the new shape can hold cannot survive the old one.
    op.execute("DELETE FROM studio_run WHERE team_id NOT IN (SELECT id FROM studio_team)")
    op.create_foreign_key(
        "studio_run_team_id_fkey", "studio_run", "studio_team", ["team_id"], ["id"], ondelete="CASCADE"
    )

    op.execute("DELETE FROM studio_trigger_event WHERE team_id IS NULL")
    op.drop_constraint("uq_studio_trigger_event_item", "studio_trigger_event", type_="unique")
    op.create_unique_constraint(
        "uq_studio_trigger_event_item", "studio_trigger_event", ["team_id", "item_key"]
    )
    op.alter_column("studio_trigger_event", "team_id", nullable=False)

    op.execute("DELETE FROM studio_event_trigger WHERE team_id IS NULL")
    op.drop_constraint("ck_studio_event_trigger_target", "studio_event_trigger", type_="check")
    op.drop_column("studio_event_trigger", "runs_as")
    op.drop_column("studio_event_trigger", "workflow_id")
    op.alter_column("studio_event_trigger", "team_id", nullable=False)
