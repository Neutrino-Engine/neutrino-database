"""NC-760: retry a failed workflow run from the failed step.

Adds ``workflow_run.failed_step_id`` (the node that broke the run) and ``workflow_run.retry_of`` (the run a
retry was started from). Both nullable; existing rows are untouched.

Revision ID: 1e84bef559a6
Revises: dbe0ad323d81
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "1e84bef559a6"
down_revision: Union[str, Sequence[str], None] = "dbe0ad323d81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflow_run", sa.Column("failed_step_id", sa.Text(), nullable=True))
    op.add_column(
        "workflow_run",
        sa.Column(
            "retry_of",
            UUID(as_uuid=False),
            sa.ForeignKey("workflow_run.id", ondelete="SET NULL", name="fk_workflow_run_retry_of"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_constraint("fk_workflow_run_retry_of", "workflow_run", type_="foreignkey")
    op.drop_column("workflow_run", "retry_of")
    op.drop_column("workflow_run", "failed_step_id")
