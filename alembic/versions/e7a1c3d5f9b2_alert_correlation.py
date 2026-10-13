"""Alert correlation state: episodes, fingerprints, occurrences, silences.

Alertmanager-style dedup and grouping for monitoring alerts from any source.
Derived facts only: no alert subject, body or message is stored.

Revision ID: e7a1c3d5f9b2
Revises: d5e9f3a7b1c2
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7a1c3d5f9b2"
down_revision: Union[str, Sequence[str], None] = "d5e9f3a7b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=False)
TS = sa.TIMESTAMP(timezone=True)


def _scope() -> list[sa.Column]:
    return [
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "alert_episode",
        sa.Column("id", UUID, primary_key=True),
        *_scope(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_key", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'open'")),
        sa.Column("opened_at", TS, nullable=False),
        sa.Column("last_event_at", TS, nullable=False),
        sa.Column("closed_at", TS, nullable=True),
        sa.Column("severity", sa.SmallInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("fingerprints", postgresql.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("firing", postgresql.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("hosts", postgresql.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("alerts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("reopened", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('open', 'resolved')", name="ck_alert_episode_status"),
    )
    op.create_index("ix_alert_episode_group", "alert_episode",
                    ["workspace_id", "group_key", sa.text("last_event_at DESC")])
    op.create_index("ix_alert_episode_status", "alert_episode",
                    ["workspace_id", "status", sa.text("last_event_at DESC")])

    op.create_table(
        "alert_fingerprint",
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspace.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("fingerprint", sa.Text, primary_key=True),
        *_scope(),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("since", TS, nullable=True),
        sa.Column("last_seen", TS, nullable=True),
        sa.Column("episode_id", UUID, sa.ForeignKey("alert_episode.id", ondelete="SET NULL"), nullable=True),
        sa.Column("host", sa.Text, nullable=True),
        sa.Column("open_event", postgresql.JSONB, nullable=True),
        sa.Column("changes", postgresql.ARRAY(TS), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("flapping", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("fired", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('firing', 'resolved')", name="ck_alert_fingerprint_status"),
    )
    op.create_index("ix_alert_fingerprint_firing_host", "alert_fingerprint", ["workspace_id", "host"],
                    postgresql_where=sa.text("status = 'firing'"))

    op.create_table(
        "alert_occurrence",
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspace.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source", sa.String(32), primary_key=True),
        sa.Column("external_id", sa.Text, primary_key=True),
        *_scope(),
        sa.Column("fingerprint", sa.Text, nullable=False),
        sa.Column("episode_id", UUID, sa.ForeignKey("alert_episode.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("at", TS, nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_alert_occurrence_at", "alert_occurrence", ["workspace_id", "at"])

    op.create_table(
        "alert_silence",
        sa.Column("id", UUID, primary_key=True),
        *_scope(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("matchers", postgresql.JSONB, nullable=False),
        sa.Column("starts_at", TS, nullable=False),
        sa.Column("ends_at", TS, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_by", UUID, sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_alert_silence_window"),
    )
    op.create_index("ix_alert_silence_active", "alert_silence", ["workspace_id", "ends_at"])


def downgrade() -> None:
    op.drop_table("alert_silence")
    op.drop_table("alert_occurrence")
    op.drop_table("alert_fingerprint")
    op.drop_table("alert_episode")
