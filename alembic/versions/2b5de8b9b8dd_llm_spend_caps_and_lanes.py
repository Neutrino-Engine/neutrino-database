"""LLM spend ledger, per-workspace and per-member caps, admin model lanes

Three things arrive together because none of them is useful alone.

``workspace_llm_spend`` is the ledger. One row per workspace, member and
calendar month; the workspace total is the sum of its rows. ``user_id`` is
NULL for work no person asked for (enrichment, scheduled workflows, a chat
title written after the tab closed), and the unique index is NULLS NOT
DISTINCT so that unattributed work keeps ONE row per month instead of
inserting a fresh one on every call.

The cap columns are nullable everywhere on purpose. A workspace that has
never set a cap inherits the platform default rather than a cap of zero, and
a member with no override inherits the workspace's per-user default. Nothing
is refused the moment this deploys.

``llm_task_lanes`` is the admin's model routing: task key -> provider id, for
the user-facing work (workflow steps) an admin should control. The platform's
own internal tasks keep their defaults in code.

Revision ID: 2b5de8b9b8dd
Revises: d6e7f8a9b0c1
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2b5de8b9b8dd"
down_revision: Union[str, Sequence[str], None] = "d6e7f8a9b0c1"


def upgrade() -> None:
    op.add_column(
        "workspace",
        sa.Column("monthly_llm_usd_cap", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "workspace",
        sa.Column("monthly_llm_usd_cap_per_user", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "workspace",
        sa.Column(
            "llm_task_lanes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "workspace_member",
        sa.Column("monthly_llm_usd_cap", sa.Numeric(10, 2), nullable=True),
    )

    op.create_table(
        "workspace_llm_spend",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("prompt_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("cached_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("llm_calls", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("cost_usd", sa.Numeric(14, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="SET NULL"),
    )
    # NULLS NOT DISTINCT needs raw DDL: alembic's create_index has no flag for
    # it, and without it the UPSERT for unattributed work never conflicts.
    op.execute(
        """
        CREATE UNIQUE INDEX ux_workspace_llm_spend_period
        ON workspace_llm_spend (workspace_id, user_id, period)
        NULLS NOT DISTINCT
        """
    )
    op.create_index(
        "ix_workspace_llm_spend_workspace_period",
        "workspace_llm_spend",
        ["workspace_id", "period"],
    )
    op.create_index(
        "ix_workspace_llm_spend_user_period",
        "workspace_llm_spend",
        ["user_id", "period"],
    )


def downgrade() -> None:
    op.drop_table("workspace_llm_spend")
    op.drop_column("workspace_member", "monthly_llm_usd_cap")
    op.drop_column("workspace", "llm_task_lanes")
    op.drop_column("workspace", "monthly_llm_usd_cap_per_user")
    op.drop_column("workspace", "monthly_llm_usd_cap")
