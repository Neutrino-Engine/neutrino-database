"""A saved test case carries its own files.

``studio_test_case`` had ``input`` and ``assertions``, so a case whose input
names a document (the TDS Gate template's ``document_path``) could only be run
by attaching the file by hand every time — and "Run all" had no answer at all
about whose file it should use.

A test case is input + files + assertions: the case OWNS its files. ``files``
holds the same inbound descriptors ``app/studio/inbound_files.py`` takes for a
run — ``{"attachment_id": ...}`` or ``{"bucket", "key", "filename"}`` — so a
test run hands the list straight to ``start_team_run(files=...)`` and the agent
still cannot tell how the file arrived.

Revision ID: c8b3a1d5e7f9
Revises: b6f1d4c8e2a7
Create Date: 2026-09-21

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8b3a1d5e7f9"
down_revision: Union[str, Sequence[str], None] = "b6f1d4c8e2a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "studio_test_case",
        sa.Column(
            "files",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("studio_test_case", "files")
