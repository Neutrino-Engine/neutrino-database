"""audit_log trigger allows ON DELETE SET NULL; ux_llm_provider ignores soft-deleted rows

Audit entries 93 and 25 (NC-767).

Revision ID: c3f8a1d2e4b5
Revises: 1e84bef559a6
Create Date: 2026-10-21
"""
from alembic import op

revision = "c3f8a1d2e4b5"
down_revision = "1e84bef559a6"
branch_labels = None
depends_on = None

_BLOCK_ALL = """
CREATE OR REPLACE FUNCTION audit_log_block_mutation() RETURNS trigger AS $func$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only; UPDATE/DELETE blocked'
        USING ERRCODE = 'AU001';
END;
$func$ LANGUAGE plpgsql
"""

_ALLOW_SET_NULL = """
CREATE OR REPLACE FUNCTION audit_log_block_mutation() RETURNS trigger AS $func$
BEGIN
    -- The one allowed change: ON DELETE SET NULL clearing actor_user_id
    -- when the user is hard-deleted, every other column untouched.
    IF TG_OP = 'UPDATE' AND OLD.actor_user_id IS NOT NULL
       AND NEW.actor_user_id IS NULL
       AND (to_jsonb(NEW) - 'actor_user_id') = (to_jsonb(OLD) - 'actor_user_id') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'audit_log is append-only; UPDATE/DELETE blocked'
        USING ERRCODE = 'AU001';
END;
$func$ LANGUAGE plpgsql
"""


def upgrade() -> None:
    op.execute(_ALLOW_SET_NULL)
    op.drop_constraint("ux_llm_provider", "providers", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX ux_llm_provider ON providers "
        "(workspace_id, service_type, display_name) WHERE is_deleted = false"
    )


def downgrade() -> None:
    # Fails if soft-deleted duplicates exist; remove them before downgrading.
    op.execute("DROP INDEX IF EXISTS ux_llm_provider")
    op.create_unique_constraint(
        "ux_llm_provider", "providers", ["workspace_id", "service_type", "display_name"]
    )
    op.execute(_BLOCK_ALL)
