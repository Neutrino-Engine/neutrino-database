"""NC-570 — workspace_da_suggested_question, the stored starter-question pool.

The chat empty state composed its DA cards from three string templates on the
request path. NC-567 made those cards honest: nothing reaches a sentence
without a business name and a statistical profile behind it. It could not make
them sound like questions a senior, non technical reader asks, because a
template does not write prose, it fills slots.

Generation therefore moves off the request path and into the enrichment run,
where a language model writes each sentence against the same evidence the
templates read. This table is where the result is stored, so the chat home
screen goes back to being a read.

One row is one question, carrying the catalog identity behind it:

  * da_catalog_table_id / da_catalog_schema_id — the question's source. The
    NC-568 permission filter walks column -> table -> schema, so it needs the
    schema as well as the table.
  * da_catalog_column_ids — every column the sentence names. NOT NULL: the
    filter fails closed, so a question recording no column can never be shown
    to a member who is subject to column grants.

``shape`` is load bearing, not decoration. It is the question's kind — trend,
breakdown, total, ranking — it carries the icon the client renders, and the
serve boundary groups the pool by it so one screen shows four kinds of
question rather than one sentence repeated four times.

``origin`` follows the ``description_origin`` house style on the
workspace_curation_da_* overlays: a short string with a CHECK, not a native
enum, so a new value is a constraint change rather than a type migration.

Foreign keys cascade. A removed connection, schema or table takes its
questions with it — a question about a table that no longer exists is exactly
the "names something that isn't there" failure the feature exists to remove.
``generated_by_run_id`` is provenance only, so it is SET NULL: pruning old
enrichment runs must never delete the pool.

Pre-production for this table: no rows to backfill.

Revision ID: e1a3c5d7f9b2
Revises: c9f4a2e6b1d8
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "e1a3c5d7f9b2"
down_revision: Union[str, Sequence[str], None] = "c9f4a2e6b1d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_da_suggested_question",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=False),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=False),
            sa.ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # The DA connection is an ``integration`` row. The column keeps the DA
        # domain name the rest of the catalog uses (see da_catalog_schema).
        sa.Column(
            "da_connection_id",
            UUID(as_uuid=False),
            sa.ForeignKey("integration.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "da_catalog_schema_id",
            UUID(as_uuid=False),
            sa.ForeignKey("da_catalog_schema.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "da_catalog_table_id",
            UUID(as_uuid=False),
            sa.ForeignKey("da_catalog_table.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # JSONB list[str] of da_catalog_column.id. A list and not a join
        # table: the value is read whole, never queried by element, and it is
        # rewritten with its question rather than edited.
        sa.Column("da_catalog_column_ids", JSONB, nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("shape", sa.String(32), nullable=False),
        sa.Column(
            "origin",
            sa.String(8),
            nullable=False,
            server_default=sa.text("'ai'"),
        ),
        sa.Column(
            "generated_by_run_id",
            UUID(as_uuid=False),
            sa.ForeignKey("da_enrichment_run.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "origin IN ('template', 'ai')",
            name="ck_wdsq_origin",
        ),
    )
    # The serve path's only lookup: this workspace's pool, narrowed to the
    # connections it may currently query.
    op.create_index(
        "ix_wdsq_workspace_connection",
        "workspace_da_suggested_question",
        ["workspace_id", "da_connection_id"],
    )
    # The write path's lookup: delete then insert per table.
    op.create_index(
        "ix_wdsq_table",
        "workspace_da_suggested_question",
        ["da_catalog_table_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_wdsq_table", table_name="workspace_da_suggested_question")
    op.drop_index(
        "ix_wdsq_workspace_connection",
        table_name="workspace_da_suggested_question",
    )
    op.drop_table("workspace_da_suggested_question")
