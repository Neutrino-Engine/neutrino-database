"""workflow revision and one-off runs

ITOps merge S1/§5 — adds structure only, no backfill:

  * ``workflow_revision`` — an immutable published revision. Publication
    freezes a workflow's draft ``graph`` and its ``input_schema`` here;
    editing the draft never touches a past revision.
  * ``workflow.published_revision_id`` — nullable FK at the currently live
    revision, NULL until first publish. SET NULL rather than CASCADE: losing
    a revision must not delete the workflow. Added as a bare column first,
    then given its FK via a separate ``create_foreign_key`` call, because
    ``workflow_revision`` does not exist yet when ``workflow`` would
    otherwise need it — the two tables point at each other, and Postgres
    will not accept a circular NOT NULL pair.
  * ``workflow_run.workflow_id`` — now nullable: spec S1 lets a one-off run
    exist with no library workflow behind it.
  * ``workflow_run.graph_snapshot`` — the frozen graph a run actually
    executed. Required for a one-off run and kept for every run so history
    survives a draft edit or a republish.

Deliberately does not backfill ``workflow.published_revision_id`` for any
existing workflow, and does not touch triggers — spec §10 requires this
migration to introduce snapshots without executing, approving or exposing
anything. Backfill is a later task.

Revision ID: 107ac584e876
Revises: ca294993fba4
Create Date: 2026-09-09 14:56:11.652226

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = '107ac584e876'
down_revision: Union[str, Sequence[str], None] = 'ca294993fba4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workflow_revision",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("workflow_id", UUID(as_uuid=False), sa.ForeignKey("workflow.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("graph", JSONB(), nullable=False),
        # The published input contract: which values are fixed and which the
        # caller supplies, with defaults. S2's configurable targets and parameters.
        sa.Column("input_schema", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workflow_id", "revision_number", name="uq_workflow_revision_number"),
    )
    op.create_index("ix_workflow_revision_workflow", "workflow_revision", ["workflow_id"])

    # Bare column first — workflow_revision now exists, but the FK is added
    # as its own step, next.
    op.add_column("workflow", sa.Column("published_revision_id", UUID(as_uuid=False), nullable=True))
    op.create_foreign_key(
        "fk_workflow_published_revision",
        "workflow",
        "workflow_revision",
        ["published_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column(
        "workflow_run",
        "workflow_id",
        existing_type=UUID(as_uuid=False),
        nullable=True,
    )
    op.add_column("workflow_run", sa.Column("graph_snapshot", JSONB(), nullable=True))


def downgrade() -> None:
    """Downgrade schema.

    A one-off run has no workflow_id, so it cannot survive the NOT NULL below.
    Its steps cascade with it.
    """
    op.execute("DELETE FROM workflow_run WHERE workflow_id IS NULL")
    op.drop_column("workflow_run", "graph_snapshot")
    op.alter_column(
        "workflow_run",
        "workflow_id",
        existing_type=UUID(as_uuid=False),
        nullable=False,
    )

    op.drop_constraint("fk_workflow_published_revision", "workflow", type_="foreignkey")
    op.drop_column("workflow", "published_revision_id")

    op.drop_index("ix_workflow_revision_workflow", table_name="workflow_revision")
    op.drop_table("workflow_revision")
