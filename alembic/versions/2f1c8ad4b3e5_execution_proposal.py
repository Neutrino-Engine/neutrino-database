"""execution_proposal — the unit of approval for an agent-proposed run.

ITOps merge S4/§4.1 — adds structure only, nothing executes:

  * ``execution_proposal_status`` — pending | approved | rejected | cancelled |
    expired. ``expired`` is its own terminal value because a timeout must never
    read as an approval, and ``cancelled`` is separate from ``rejected``
    because nobody said no.
  * ``execution_proposal`` — one row per agent-proposed execution awaiting a
    human decision. It freezes the exact ``graph``, the resolved ``inputs`` and
    the targets they name; ``digest`` is a sha256 over that canonical pair and
    the later decision binds to it, so a changed procedure or target becomes a
    new proposal rather than a re-decision of this one.

``workflow_id`` / ``revision_id`` / ``chat_id`` / ``run_id`` are all nullable
and SET NULL: a one-off the agent composed has no library workflow behind it,
and losing a workflow, a revision, a conversation or a run must not delete the
approval record. ``requested_by`` / ``decided_by`` are SET NULL for the same
reason — the decision outlives the account.

Credentials never land in this table. Connector binding IDs and script bodies
do (§4.3, deliberately, so a run is reviewable and repeatable).

The enum is created explicitly and referenced with ``create_type=False``, the
same way ``a7c9e2b4d6f8`` does it, so the column bind does not try to create it
a second time.

Revision ID: 2f1c8ad4b3e5
Revises: 107ac584e876
Create Date: 2026-09-09

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = "2f1c8ad4b3e5"
down_revision: Union[str, Sequence[str], None] = "107ac584e876"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


proposal_status_enum = ENUM(
    "pending", "approved", "rejected", "cancelled", "expired",
    name="execution_proposal_status",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    proposal_status_enum.create(op.get_bind(), checkfirst=False)
    op.create_table(
        "execution_proposal",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        # NULL for a one-off the agent composed; set when it came from a revision.
        sa.Column("workflow_id", UUID(as_uuid=False), sa.ForeignKey("workflow.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revision_id", UUID(as_uuid=False), sa.ForeignKey("workflow_revision.id", ondelete="SET NULL"), nullable=True),
        # The conversation that proposed it, so chat and the inbox show one item.
        sa.Column("chat_id", UUID(as_uuid=False), sa.ForeignKey("chat.id", ondelete="SET NULL"), nullable=True),
        sa.Column("graph", JSONB(), nullable=False),
        sa.Column("inputs", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        # Human-readable preview of every side-effecting branch, for the card.
        sa.Column("preview", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        # sha256 over the canonical graph + inputs. The decision binds to this.
        sa.Column("digest", sa.Text(), nullable=False),
        sa.Column("status", proposal_status_enum, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("requested_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # The run the approval started, once one exists. NULL while pending.
        sa.Column("run_id", UUID(as_uuid=False), sa.ForeignKey("workflow_run.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # The approval inbox path: pending proposals in this workspace.
    op.create_index("ix_execution_proposal_pending", "execution_proposal", ["workspace_id", "status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_execution_proposal_pending", table_name="execution_proposal")
    op.drop_table("execution_proposal")
    sa.Enum(name="execution_proposal_status").drop(op.get_bind(), checkfirst=False)
