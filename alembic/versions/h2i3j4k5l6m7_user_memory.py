"""NC-519 — user_memory + user_memory_settings (long-term agent memory).

NC-416 gave chat an *intra*-conversation context window (100k, compaction at
80%). It does nothing across conversations, and its summarizer is explicitly
told to discard tool observations — so the detail a memory layer wants to keep
is exactly what compaction throws away. These two tables are the cross-chat
half.

``user_memory`` is the SOURCE OF TRUTH. A mirror doc lands in the per-tenant
Elasticsearch index ``memories_tenant_{tenant}`` purely for hybrid retrieval
(BM25 + kNN) and is rebuildable from these rows, so an ES outage degrades
recall and never correctness. Nothing here depends on pgvector.

Keyed on ``user_id`` (the internal JWT's ``user_id``), NOT ``member.id``.
Document ACLs are member-keyed because the file-permission store keys by member
(NC-131), but memory is ours end to end and agent-platform already holds
user_id — keying on it avoids a connector-service round-trip on every turn.

No new PG enum types, deliberately, unlike ``chat_artifact_kind``. ``kind``,
``origin`` and ``scope`` are all expected to GROW (procedural memories,
workspace-shared scope); extending a CHECK is a one-line migration, whereas
ALTER TYPE ... ADD VALUE cannot be rolled back.

ondelete posture:
  * tenant_id         NOT NULL, CASCADE  — row is tenant data
  * user_id           NOT NULL, CASCADE  — GDPR erasure rides this FK
  * workspace_id      nullable, CASCADE  — NULL reserved for cross-workspace
  * source_chat_id    nullable, SET NULL — a conclusion outlives its chat
  * source_message_id nullable, SET NULL — ditto
  * superseded_by     self-FK,  SET NULL — a retired row survives its successor

``user_memory_settings`` is the platform's first user-preferences table (the
Preferences tab writes localStorage only today). Every boolean defaults
fail-safe — ``enabled`` FALSE — so the feature stays dark per user even after
the service-level flag is on. Kept narrow on purpose; it is not a general
user-settings bag.

Pre-production feature, shipped behind a flag: no rows to backfill.

Revision ID: h2i3j4k5l6m7
Revises: c8e4f1a9d7b3
Create Date: 2026-08-20

Re-chained onto NC-500's ``c8e4f1a9d7b3`` rather than ``g1h2i3j4k5l6``. Both
originally chained off the same parent, which left alembic with two heads once
the branches merged — and ``make migrate`` runs ``alembic upgrade head``
(singular), which refuses to run at all with a fork. Nothing conflicted in git,
so the PR read as mergeable while deploy-time migrations would have failed.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, Sequence[str], None] = "c8e4f1a9d7b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_memory",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=False),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # CASCADE: a deleted user's memories must not outlive them.
        sa.Column(
            "user_id",
            UUID(as_uuid=False),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Nullable, unlike chat.workspace_id (X-CHAT-WS-1). v1 always writes it
        # set so memory learned in one workspace can't surface in another; NULL
        # is reserved for a "follows the user" scope we haven't committed to.
        sa.Column(
            "workspace_id",
            UUID(as_uuid=False),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default=sa.text("'user'")),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        # sha256 of normalized content — lets the extractor short-circuit an
        # exact repeat to NOOP without spending an LLM reconciliation call.
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column(
            "source_chat_id",
            UUID(as_uuid=False),
            sa.ForeignKey("chat.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_message_id",
            UUID(as_uuid=False),
            sa.ForeignKey("message.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Reconciliation lineage: an UPDATE inserts the new row and points the
        # old one here before soft-deleting it.
        sa.Column(
            "superseded_by",
            UUID(as_uuid=False),
            sa.ForeignKey("user_memory.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("scope IN ('user', 'workspace', 'tenant')", name="ck_user_memory_scope"),
        sa.CheckConstraint("kind IN ('fact', 'preference', 'correction')", name="ck_user_memory_kind"),
        sa.CheckConstraint("origin IN ('auto', 'explicit', 'manual')", name="ck_user_memory_origin"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_user_memory_confidence_range"),
        sa.CheckConstraint("length(content) > 0", name="ck_user_memory_content_not_blank"),
        sa.CheckConstraint(
            "superseded_by IS NULL OR superseded_by <> id",
            name="ck_user_memory_no_self_supersede",
        ),
    )

    # The hot path: WHERE tenant_id AND user_id AND deleted_at IS NULL.
    op.create_index(
        "ix_user_memory_tenant_user",
        "user_memory",
        ["tenant_id", "user_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Exact-duplicate guard, per user. Partial on deleted_at so re-learning
    # something the user deleted earlier is allowed.
    op.create_index(
        "ix_user_memory_dedupe",
        "user_memory",
        ["tenant_id", "user_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_user_memory_source_chat", "user_memory", ["source_chat_id"])

    op.create_table(
        "user_memory_settings",
        sa.Column(
            "user_id",
            UUID(as_uuid=False),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=False),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Fail-safe: memory is off until the user opts in.
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("capture_facts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("capture_preferences", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("capture_corrections", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("user_memory_settings")
    op.drop_index("ix_user_memory_source_chat", table_name="user_memory")
    op.drop_index("ix_user_memory_dedupe", table_name="user_memory")
    op.drop_index("ix_user_memory_tenant_user", table_name="user_memory")
    op.drop_table("user_memory")
