"""NC-734: provider names are unique per category, not across categories.

``ux_llm_provider`` is a partial unique index on
``(workspace_id, service_type, display_name) WHERE is_deleted = false``
(NC-767, c3f8a1d2e4b5). NC-734 stores optional workspace embedding providers in
the same ``providers`` table under ``provider_category = 'embedding'``. With
the old key, an embedding provider named "OpenAI" could not coexist with an
LLM provider named "OpenAI" in the same workspace. The new index adds
``provider_category`` and keeps the soft-delete exemption, so names stay
unique within a category among live rows.

Downgrade restores ``ux_llm_provider``; it fails if a workspace has a live LLM
and a live embedding provider sharing a service type and display name, which
is the state this migration exists to allow.

Revision ID: e7f1a3c5b9d2
Revises: 7e3b9c1d5a20
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "e7f1a3c5b9d2"
down_revision: Union[str, Sequence[str], None] = "7e3b9c1d5a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_llm_provider")
    op.execute(
        "CREATE UNIQUE INDEX ux_provider_category_name ON providers "
        "(workspace_id, provider_category, service_type, display_name) "
        "WHERE is_deleted = false"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_provider_category_name")
    op.execute(
        "CREATE UNIQUE INDEX ux_llm_provider ON providers "
        "(workspace_id, service_type, display_name) WHERE is_deleted = false"
    )
