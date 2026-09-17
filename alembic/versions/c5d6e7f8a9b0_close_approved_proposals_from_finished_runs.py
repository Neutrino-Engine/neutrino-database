"""Close approved proposals whose run already finished.

Rows approved before ``close_proposal`` existed stay ``approved`` for ever, so
they hold the open-digest slot and every later request for the same graph and
inputs is deduplicated onto a three-day-old decision. Set each one from its
run: ``succeeded`` when the run succeeded, ``failed`` for failed or cancelled.
``create_proposal`` now performs the same sweep per digest before it reads, so
this runs once over the backlog.

The downgrade is a no-op: the previous status is not recoverable and was wrong.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE execution_proposal p
        SET status = (CASE r.status::text WHEN 'succeeded' THEN 'succeeded' ELSE 'failed' END)::execution_proposal_status
        FROM workflow_run r
        WHERE p.run_id = r.id
          AND p.status = 'approved'
          AND r.status IN ('succeeded', 'failed', 'cancelled')
        """
    )


def downgrade() -> None:
    pass
