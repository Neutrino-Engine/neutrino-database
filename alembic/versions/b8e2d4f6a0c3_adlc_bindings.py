"""ADLC WS2: references and bindings.

- ``workspace.automation_owner_user_id`` / ``service_user_id``: the people the
  ``runs_as: owner|service`` roles resolve to in this environment.
- ``approver_group`` + ``approver_group_member``: named, workspace-scoped sets
  of people that configs reference as ``group:<key>``.

Backfill changes no behaviour: every existing config still names user ids,
which keep working. The automation owner is seeded from the most common
``runs_as.identity_id`` among each workspace's owner-kind teams, falling back
to the workspace creator, so that a config rewritten to the bare role later
resolves to the same person it does today.

Revision ID: b8e2d4f6a0c3
Revises: a7d1c3e5f9b2
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "b8e2d4f6a0c3"
down_revision: Union[str, Sequence[str], None] = "a7d1c3e5f9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for col in ("automation_owner_user_id", "service_user_id"):
        op.add_column(
            "workspace",
            sa.Column(col, UUID(as_uuid=False),
                      sa.ForeignKey("user.id", ondelete="SET NULL", name=f"fk_workspace_{col}"),
                      nullable=True),
        )

    op.create_table(
        "approver_group",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "key", name="uq_approver_group_key"),
        sa.CheckConstraint("key ~ '^[a-z][a-z0-9-]{0,63}$'", name="ck_approver_group_key"),
    )
    op.create_table(
        "approver_group_member",
        sa.Column("group_id", UUID(as_uuid=False), sa.ForeignKey("approver_group.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("added_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("added_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.execute("""
        UPDATE workspace w SET automation_owner_user_id = COALESCE(
            (SELECT (t.config->'runs_as'->>'identity_id')::uuid
             FROM studio_team t
             JOIN "user" u ON u.id = (t.config->'runs_as'->>'identity_id')::uuid
             WHERE t.workspace_id = w.id AND t.deleted_at IS NULL
               AND t.config->'runs_as'->>'kind' = 'owner'
               AND t.config->'runs_as'->>'identity_id' IS NOT NULL
             GROUP BY 1 ORDER BY count(*) DESC LIMIT 1),
            w.created_by)
    """)


def downgrade() -> None:
    op.drop_table("approver_group_member")
    op.drop_table("approver_group")
    for col in ("automation_owner_user_id", "service_user_id"):
        op.drop_column("workspace", col)
