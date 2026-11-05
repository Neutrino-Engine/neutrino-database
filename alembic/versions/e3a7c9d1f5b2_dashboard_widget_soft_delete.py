"""dashboard_widget soft delete (NC-789).

Widget deletes were hard deletes, so a removed widget could never come back —
which is why the canvas chat was never given a remove tool: "just remove it and
undo" is not an undo when the row is gone. ``deleted_at`` / ``deleted_by`` make
a delete reversible. A removed widget keeps its row, its query and its last
position, so restoring it puts the same chart back on the same board.

Every read of live widgets filters ``deleted_at IS NULL`` app-side. No new
index: restore and the recently-removed list read deleted rows by
``dashboard_id``, which ``ix_dashboard_widget_dashboard`` already serves.

``deleted_by`` is SET NULL on user deletion, matching ``dashboard.owner_id`` /
``created_by``: keep the row, lose attribution.

Revision ID: e3a7c9d1f5b2
Revises: 9c4d2e7f1b38
Create Date: 2026-11-02
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

revision = "e3a7c9d1f5b2"
down_revision = "9c4d2e7f1b38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dashboard_widget",
        sa.Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "dashboard_widget",
        sa.Column(
            "deleted_by",
            UUID(as_uuid=False),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Soft-deleted rows would reappear as live widgets once the column is gone,
    # so they are dropped first: a downgrade restores the hard-delete world.
    op.execute("DELETE FROM dashboard_widget WHERE deleted_at IS NOT NULL")
    op.drop_column("dashboard_widget", "deleted_by")
    op.drop_column("dashboard_widget", "deleted_at")
