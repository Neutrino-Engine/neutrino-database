"""workspace_llm_governance: one PII governance setting per workspace (NC-892).

Upgrade copies the governance of each workspace's active LLM provider into the
new table. Downgrade writes the table values back to the active provider rows.
providers.model_config["governance"] stays for one release.

Revision ID: a9c3e5f7b1d2
Revises: f4b8d2a6c1e9
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a9c3e5f7b1d2"
down_revision = "f4b8d2a6c1e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_llm_governance",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("workspace.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("governance", postgresql.JSONB, nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # DISTINCT ON: a workspace with two active LLM rows still gets one record.
    op.execute("""
        INSERT INTO workspace_llm_governance (workspace_id, governance)
        SELECT DISTINCT ON (workspace_id) workspace_id::uuid, model_config->'governance'
        FROM providers
        WHERE provider_category = 'llm' AND is_active AND NOT is_deleted
          AND model_config ? 'governance'
        ORDER BY workspace_id, updated_at DESC
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE providers p
        SET model_config = jsonb_set(COALESCE(p.model_config, '{}'::jsonb), '{governance}', g.governance, true)
        FROM workspace_llm_governance g
        WHERE p.workspace_id = g.workspace_id
          AND p.provider_category = 'llm' AND p.is_active AND NOT p.is_deleted
    """)
    op.drop_table("workspace_llm_governance")
