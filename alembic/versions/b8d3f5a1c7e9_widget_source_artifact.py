"""dashboard_widget.source_artifact_id — which chat chart a widget came from.

Pin-to-dashboard promotes a chat_artifact chart into a widget, and the product
shows that link in BOTH directions: the chat card says "On <dashboard>", the
widget says "from chat". Neither worked, because nothing durable recorded the
pairing.

`created_by_message_id` was the obvious candidate and it cannot do the job.
Native da_chart artifacts are persisted BEFORE the assistant message is
finalized — `_persist_envelope_chart_artifacts` passes `message_id=None` on
purpose, so the new artifact_id can ride the message envelope — which leaves
`chat_artifact.message_id` NULL, and therefore the widget's
`created_by_message_id` NULL too. Even with that fixed, a message can produce
several charts, so a message id cannot say WHICH chart a widget came from.

So the widget points at the artifact directly. ON DELETE SET NULL, matching how
`created_by_message_id` treats a compliance-purged message: the widget must
outlive its provenance, because the query it runs is its own.

The index supports the reverse lookup — "which dashboards hold this chart?" —
which is what the chat card asks on render. Partial, since the column is NULL
for every widget the build agent proposed.

Revision ID: b8d3f5a1c7e9
Revises: d4b7e1c8a5f2
Create Date: 2026-08-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "b8d3f5a1c7e9"
down_revision: Union[str, Sequence[str], None] = "j4k5l6m7n8o9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dashboard_widget",
        sa.Column(
            "source_artifact_id",
            UUID(as_uuid=False),
            sa.ForeignKey("chat_artifact.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_dashboard_widget_source_artifact",
        "dashboard_widget",
        ["source_artifact_id"],
        unique=False,
        postgresql_where=sa.text("source_artifact_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dashboard_widget_source_artifact", table_name="dashboard_widget"
    )
    op.drop_column("dashboard_widget", "source_artifact_id")
