"""A workflow_run has a graph: its library workflow or its own graph_snapshot.

107ac584e876 made ``workflow_id`` nullable for one-off runs and documented
``graph_snapshot`` as required for them, but nothing enforced it. This is a
separate migration because 107ac584e876 has already run on live databases.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_workflow_run_has_graph",
        "workflow_run",
        "workflow_id IS NOT NULL OR graph_snapshot IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_workflow_run_has_graph", "workflow_run", type_="check")
