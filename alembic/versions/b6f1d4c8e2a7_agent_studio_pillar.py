"""Agent Studio is a workspace pillar.

``workspace.enabled_pillars`` is ``pillar[]``, a Postgres enum, so the studio
needs its own value there before a workspace can switch it on. The gateway's
readiness endpoint reports the pillar from this column and the frontend hides
the whole Agent Studio section when it is absent — ``tenant.allowed_modules``
(AllowedModuleEnum.AGENT_STUDIO) is the tenant-level twin, but that column is
write-only today, so this is the gate that decides.

``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction that later uses
the new label, so it goes in an autocommit block. It is also irreversible:
Postgres has no DROP VALUE, and rewriting the type would have to rewrite every
column using it. The downgrade therefore only strips the value from any
workspace still carrying it, which is what makes a re-upgrade safe.

Revision ID: b6f1d4c8e2a7
Revises: a5e7c9d1b3f2
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b6f1d4c8e2a7"
down_revision: Union[str, Sequence[str], None] = "a5e7c9d1b3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE pillar ADD VALUE IF NOT EXISTS 'AGENT_STUDIO'")


def downgrade() -> None:
    # The label stays (Postgres cannot drop one); remove it from any workspace
    # that has it so nothing references a value the code no longer knows.
    op.execute(
        "UPDATE workspace SET enabled_pillars = array_remove(enabled_pillars, "
        "'AGENT_STUDIO'::pillar) WHERE 'AGENT_STUDIO' = ANY(enabled_pillars)"
    )
