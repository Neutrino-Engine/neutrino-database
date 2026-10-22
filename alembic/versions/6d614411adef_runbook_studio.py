"""Runbook Studio: runbook and runbook_version.

The remote-exec diagnostic scripts, versioned by sha256. The draft owner never
approves their own version. Global tables: no tenant_id.

Revision ID: 6d614411adef
Revises: dbe0ad323d81
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6d614411adef"
down_revision: Union[str, Sequence[str], None] = "dbe0ad323d81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=False)
TS = sa.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "runbook",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("target", sa.String(16), nullable=False),
        sa.Column("check", sa.String(64), nullable=False),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('runbook', 'probe', 'wrapper')", name="ck_runbook_kind"),
    )

    op.create_table(
        "runbook_version",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("runbook_id", UUID, sa.ForeignKey("runbook.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("explanation", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("safety_declared", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("author_user_id", UUID, sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("review_note", sa.Text, nullable=True),
        sa.Column("edited_by", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", TS, server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", TS, nullable=True),
        sa.Column("approved_by", UUID, sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", TS, nullable=True),
        sa.Column("retired_at", TS, nullable=True),
        sa.CheckConstraint("status IN ('draft', 'in_review', 'approved', 'retired')", name="ck_runbook_version_status"),
        sa.UniqueConstraint("runbook_id", "version", name="uq_runbook_version_version"),
    )
    op.create_index("ux_runbook_version_approved", "runbook_version", ["runbook_id"],
                    unique=True, postgresql_where=sa.text("status = 'approved'"))
    op.create_index("ix_runbook_version_sha256", "runbook_version", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_runbook_version_sha256", table_name="runbook_version")
    op.drop_index("ux_runbook_version_approved", table_name="runbook_version")
    op.drop_table("runbook_version")
    op.drop_table("runbook")
