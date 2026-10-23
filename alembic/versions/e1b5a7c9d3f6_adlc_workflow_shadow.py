"""ADLC: workflow shadow runs (D31 for workflows).

``workflow_run.is_shadow`` / ``shadow_of_run_id``. No backfill: every
existing run is a real run.

Revision ID: e1b5a7c9d3f6
Revises: d0a4f6b8c2e5
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "e1b5a7c9d3f6"
down_revision: Union[str, Sequence[str], None] = "d0a4f6b8c2e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflow_run", sa.Column("is_shadow", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column(
        "workflow_run",
        sa.Column("shadow_of_run_id", UUID(as_uuid=False),
                  sa.ForeignKey("workflow_run.id", ondelete="SET NULL", name="fk_workflow_run_shadow_of"),
                  nullable=True),
    )


def downgrade() -> None:
    op.drop_constraint("fk_workflow_run_shadow_of", "workflow_run", type_="foreignkey")
    op.drop_column("workflow_run", "shadow_of_run_id")
    op.drop_column("workflow_run", "is_shadow")
