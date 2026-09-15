"""Remediation hardening: proposal terminal states and one open proposal per digest.

``execution_proposal_status`` gains ``succeeded`` and ``failed`` so an approved
proposal can close from its run's postcheck instead of reading ``approved``
forever. A partial unique index on ``(workspace_id, digest)`` over pending and
approved rows makes deduplication a constraint: a repeated request for the same
graph and inputs attaches to the open card.

``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction on PostgreSQL below
12 and cannot be rolled back on any version, so the downgrade drops only the
index. Existing duplicates are collapsed first: the newest row of each open
digest is kept and the rest are marked ``cancelled`` (nobody said no).

Revision ID: b4c5d6e7f8a9
Revises: 3a7b9c1d2e4f
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "3a7b9c1d2e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE execution_proposal_status ADD VALUE IF NOT EXISTS 'succeeded'")
    op.execute("ALTER TYPE execution_proposal_status ADD VALUE IF NOT EXISTS 'failed'")
    op.execute(
        """
        UPDATE execution_proposal p
        SET status = 'cancelled'
        WHERE p.status IN ('pending', 'approved')
          AND EXISTS (
            SELECT 1 FROM execution_proposal q
            WHERE q.workspace_id = p.workspace_id
              AND q.digest = p.digest
              AND q.status IN ('pending', 'approved')
              AND (q.created_at, q.id) > (p.created_at, p.id)
          )
        """
    )
    op.create_index(
        "uq_execution_proposal_open_digest",
        "execution_proposal",
        ["workspace_id", "digest"],
        unique=True,
        postgresql_where="status IN ('pending', 'approved')",
    )


def downgrade() -> None:
    op.drop_index("uq_execution_proposal_open_digest", table_name="execution_proposal")
