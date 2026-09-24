"""Revert NC-666 (PR #116): drop the ITOps tool-surface schema.

Undoes, as a forward migration, everything ca294993fba4 .. d6e7f8a9b0c1 added:

  * ``execution_proposal`` and its ``execution_proposal_status`` enum
  * ``workflow_revision`` and ``workflow.published_revision_id``
  * ``workflow_run.graph_snapshot`` and ``ck_workflow_run_has_graph``;
    ``workflow_run.workflow_id`` is NOT NULL again
  * ``chat.estate_scope_kind`` / ``estate_uid`` / ``estate_display_name``,
    ``ix_chat_estate_uid`` and the ``estate_scope_kind`` enum

The original migration files stay in the chain because live databases already
carry those revision ids; removing them would leave ``alembic upgrade`` unable
to find the current revision.

Data loss, by design: every proposal and revision row, every graph snapshot,
every chat's estate scope, and every one-off run (``workflow_id IS NULL``) with
its steps, since those cannot satisfy NOT NULL. No service reads any of it.

``IF EXISTS`` throughout: a5e7c9d1b3f2's autogenerate saw ``ix_chat_estate_uid``
as drift, so a database stamped rather than migrated may not have it.

The downgrade restores the structure only, as d6e7f8a9b0c1 left it. Dropped
data does not come back.

Revision ID: f2b8d4a6c0e3
Revises: e1a5c9d3b7f4
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "f2b8d4a6c0e3"
down_revision: Union[str, Sequence[str], None] = "e1a5c9d3b7f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS execution_proposal")
    op.execute("DROP TYPE IF EXISTS execution_proposal_status")

    op.execute("ALTER TABLE workflow_run DROP CONSTRAINT IF EXISTS ck_workflow_run_has_graph")
    # One-off runs have no workflow; their steps cascade with them.
    op.execute("DELETE FROM workflow_run WHERE workflow_id IS NULL")
    op.execute("ALTER TABLE workflow_run DROP COLUMN IF EXISTS graph_snapshot")
    op.execute("ALTER TABLE workflow_run ALTER COLUMN workflow_id SET NOT NULL")

    op.execute("ALTER TABLE workflow DROP CONSTRAINT IF EXISTS fk_workflow_published_revision")
    op.execute("ALTER TABLE workflow DROP COLUMN IF EXISTS published_revision_id")
    op.execute("DROP TABLE IF EXISTS workflow_revision")

    op.execute("DROP INDEX IF EXISTS ix_chat_estate_uid")
    op.execute("ALTER TABLE chat DROP COLUMN IF EXISTS estate_display_name")
    op.execute("ALTER TABLE chat DROP COLUMN IF EXISTS estate_uid")
    op.execute("ALTER TABLE chat DROP COLUMN IF EXISTS estate_scope_kind")
    op.execute("DROP TYPE IF EXISTS estate_scope_kind")


def downgrade() -> None:
    op.execute("CREATE TYPE estate_scope_kind AS ENUM ('host', 'incident')")
    op.execute("ALTER TABLE chat ADD COLUMN estate_scope_kind estate_scope_kind")
    op.execute("ALTER TABLE chat ADD COLUMN estate_uid TEXT")
    op.execute("ALTER TABLE chat ADD COLUMN estate_display_name TEXT")
    op.execute("CREATE INDEX ix_chat_estate_uid ON chat (estate_uid)")

    op.execute(
        """
        CREATE TABLE workflow_revision (
            id UUID PRIMARY KEY,
            workflow_id UUID NOT NULL REFERENCES workflow(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
            workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
            revision_number INTEGER NOT NULL,
            graph JSONB NOT NULL,
            input_schema JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_by UUID REFERENCES "user"(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_workflow_revision_number UNIQUE (workflow_id, revision_number)
        )
        """
    )
    op.execute("CREATE INDEX ix_workflow_revision_workflow ON workflow_revision (workflow_id)")
    op.execute("ALTER TABLE workflow ADD COLUMN published_revision_id UUID")
    op.execute(
        "ALTER TABLE workflow ADD CONSTRAINT fk_workflow_published_revision "
        "FOREIGN KEY (published_revision_id) REFERENCES workflow_revision(id) ON DELETE SET NULL"
    )

    op.execute("ALTER TABLE workflow_run ALTER COLUMN workflow_id DROP NOT NULL")
    op.execute("ALTER TABLE workflow_run ADD COLUMN graph_snapshot JSONB")
    op.execute(
        "ALTER TABLE workflow_run ADD CONSTRAINT ck_workflow_run_has_graph "
        "CHECK (workflow_id IS NOT NULL OR graph_snapshot IS NOT NULL)"
    )

    op.execute(
        "CREATE TYPE execution_proposal_status AS ENUM "
        "('pending', 'approved', 'rejected', 'cancelled', 'expired', 'succeeded', 'failed')"
    )
    op.execute(
        """
        CREATE TABLE execution_proposal (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
            workspace_id UUID NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
            workflow_id UUID REFERENCES workflow(id) ON DELETE SET NULL,
            revision_id UUID REFERENCES workflow_revision(id) ON DELETE SET NULL,
            chat_id UUID REFERENCES chat(id) ON DELETE SET NULL,
            graph JSONB NOT NULL,
            inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
            preview JSONB NOT NULL DEFAULT '{}'::jsonb,
            digest TEXT NOT NULL,
            status execution_proposal_status NOT NULL DEFAULT 'pending',
            requested_by UUID REFERENCES "user"(id) ON DELETE SET NULL,
            decided_by UUID REFERENCES "user"(id) ON DELETE SET NULL,
            decided_at TIMESTAMPTZ,
            run_id UUID REFERENCES workflow_run(id) ON DELETE SET NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_execution_proposal_pending ON execution_proposal (workspace_id, status)")
    op.execute(
        "CREATE UNIQUE INDEX uq_execution_proposal_open_digest ON execution_proposal (workspace_id, digest) "
        "WHERE status IN ('pending', 'approved')"
    )
