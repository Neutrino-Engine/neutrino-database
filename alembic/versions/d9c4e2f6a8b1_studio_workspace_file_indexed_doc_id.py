"""A Studio-only run can record what it indexed.

``studio_workspace_file`` CHECKed ``NOT indexed OR promoted_artifact_id IS NOT
NULL``, which tied the truth about the knowledge index to a CHAT artefact. A
run started from the Studio has no chat, so nowhere to hang an artefact — and
promotion with ``index=true`` genuinely chunked, embedded and indexed the
document into Knowledge Studio, then had to leave ``indexed`` false. The fact
survived only in the HTTP response and the audit row; the manifest lied.

The artefact was never the right witness. It is a chat convenience, not
evidence that anything reached the index: a promotion can create an artefact
and have ingestion refuse the document in the same call. What the flag really
needs is the document itself, so the invariant becomes

    NOT indexed OR indexed_doc_id IS NOT NULL

— ``indexed`` may only be true when the row can say WHAT was indexed. That
refuses the nonsense case (a row claiming the index holds something it cannot
name) and admits the case the old CHECK refused (a Studio-only run that really
did index). It stays one-directional on purpose: ``indexed_doc_id`` without
``indexed`` is the honest record of an attempt ES answered for but did not
finish (``status="partial"`` with zero chunks), and forbidding it would make
that state unrepresentable.

``indexed_doc_id`` is plain text with no FK: the document lives in
Elasticsearch. It is the ``doc_id`` ES-Ingestion answers ``/documents/create``
with, which is ``uuid5(run_id + path)`` — stable across re-promotion of the
same file, so the column upserts the same value instead of drifting.

No backfill: nobody recorded which document an already-``indexed`` row
produced, and inventing the uuid5 here would assert something this migration
cannot verify. So such rows are cleared to ``indexed=false`` before the CHECK
goes on — an unsubstantiated flag is exactly the lie being removed, and
promotion only shipped in this branch, so in practice there are none.

Revision ID: d9c4e2f6a8b1
Revises: c8b3a1d5e7f9
Create Date: 2026-09-21

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9c4e2f6a8b1"
down_revision: Union[str, Sequence[str], None] = "c8b3a1d5e7f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "studio_workspace_file",
        sa.Column("indexed_doc_id", sa.Text(), nullable=True),
    )
    op.drop_constraint(
        "ck_studio_workspace_file_indexed_promoted",
        "studio_workspace_file",
        type_="check",
    )
    # Nothing can name the document behind a pre-existing ``indexed`` row, and
    # a flag that cannot be substantiated is the lie this migration removes.
    op.execute(
        "UPDATE studio_workspace_file SET indexed = false "
        "WHERE indexed AND indexed_doc_id IS NULL"
    )
    op.create_check_constraint(
        "ck_studio_workspace_file_indexed_doc",
        "studio_workspace_file",
        "NOT indexed OR indexed_doc_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_studio_workspace_file_indexed_doc",
        "studio_workspace_file",
        type_="check",
    )
    # The old CHECK wants an artefact behind every ``indexed`` row; a
    # Studio-only run has none, so those rows lose the flag on the way back.
    op.execute(
        "UPDATE studio_workspace_file SET indexed = false "
        "WHERE indexed AND promoted_artifact_id IS NULL"
    )
    op.create_check_constraint(
        "ck_studio_workspace_file_indexed_promoted",
        "studio_workspace_file",
        "NOT indexed OR promoted_artifact_id IS NOT NULL",
    )
    op.drop_column("studio_workspace_file", "indexed_doc_id")
