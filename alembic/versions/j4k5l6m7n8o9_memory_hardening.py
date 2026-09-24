"""NC-519 — episodic ledger, reinforcement gating, and bi-temporal validity.

Everything here exists because of one measured result: memory utility is
NON-MONOTONIC. It rises, peaks, then falls below the no-memory baseline as
consolidation continues (arXiv 2605.12978 — Agent Workflow Memory decayed 0.64 →
0.20 on WebShop as examples grew 8 → 128, meeting the no-memory baseline;
GPT-5.4 fell from 100% to 52.6% on ARC-AGI by round 10 of rewriting its own
memory). The cause the authors isolate is not abstraction but MANDATORY
abstraction on every step — episodic-management-only matched their best
configuration.

The original schema stored only the distilled sentence, abstracted every batch,
with no way to re-derive it and no notion of when a fact was true. These columns
address that:

``source_excerpt``
    The verbatim span a memory came from. Makes a memory a claim ABOUT evidence
    rather than a replacement for it, so a bad abstraction is recoverable and a
    consolidation pass can be diffed against the source. This is the property
    Anthropic's Dreams preserves and OpenAI's Dreaming V3 discards by rewriting
    in place.

``observation_count`` + ``status``
    Reinforcement gating. An extractor's confidence score is its own opinion;
    being asserted in two separate turns is evidence. A memory starts as
    ``candidate`` (stored, NOT injected) and is promoted to ``active`` on a
    second observation — the cheapest available defence against the
    overgeneralisation that drives the decay curve. Explicit and manual memories
    are ``active`` immediately, because the user asserted them outright.

    ``proposed`` is the third state and the one that fixes a governance defect
    rather than a quality one: a "correction" that names something in the DA
    catalog is ORG knowledge, not one analyst's preference. "Revenue means net
    of returns" belongs in ``description_version`` as an ``ai_suggested``
    description for admin review, not privatised into N divergent per-user rows
    while the governed, versioned catalog sits unused. Such memories are stored
    ``proposed`` and never injected.

``valid_from`` / ``valid_to``
    Bi-temporal, deliberately separate from ``created_at``: when a fact was true
    versus when we learned it. Zep's central idea. Without it a store holding
    both "works on APAC" and "moved to finance" has no basis to prefer either.

Backfill: existing rows become ``active`` with ``observation_count = 1`` and
``valid_from = created_at``, which is what they effectively already were.

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-08-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "j4k5l6m7n8o9"
down_revision: Union[str, Sequence[str], None] = "i3j4k5l6m7n8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_memory",
        sa.Column(
            "observation_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "user_memory",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
    )
    op.add_column("user_memory", sa.Column("source_excerpt", sa.Text(), nullable=True))
    op.add_column(
        "user_memory", sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.add_column(
        "user_memory", sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True)
    )

    op.create_check_constraint(
        "ck_user_memory_status",
        "user_memory",
        "status IN ('candidate', 'active', 'proposed')",
    )
    op.create_check_constraint(
        "ck_user_memory_observation_count", "user_memory", "observation_count >= 1"
    )
    op.create_check_constraint(
        "ck_user_memory_validity_order",
        "user_memory",
        "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
    )

    op.create_index(
        "ix_user_memory_active",
        "user_memory",
        ["tenant_id", "user_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Existing rows were, in effect, active single-observation memories whose
    # validity started when we learned them.
    op.execute("UPDATE user_memory SET valid_from = created_at WHERE valid_from IS NULL")


def downgrade() -> None:
    op.drop_index("ix_user_memory_active", table_name="user_memory")
    op.drop_constraint("ck_user_memory_validity_order", "user_memory", type_="check")
    op.drop_constraint("ck_user_memory_observation_count", "user_memory", type_="check")
    op.drop_constraint("ck_user_memory_status", "user_memory", type_="check")
    op.drop_column("user_memory", "valid_to")
    op.drop_column("user_memory", "valid_from")
    op.drop_column("user_memory", "source_excerpt")
    op.drop_column("user_memory", "status")
    op.drop_column("user_memory", "observation_count")
