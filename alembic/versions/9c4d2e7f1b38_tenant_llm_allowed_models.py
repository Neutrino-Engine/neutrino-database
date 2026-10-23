"""tenant LLM model allow-list (NC-795 G-42).

Adds tenant.llm_allowed_models (TEXT[], default empty). Empty = no
restriction, so existing tenants are unaffected. Entries are model ids as
the provider sees them (``openai/gpt-4o`` on OpenRouter, a deployment name
on Azure), optionally with ``*`` globs; matched case-insensitively app-side.

Revision ID: 9c4d2e7f1b38
Revises: 7e3b9c1d5a20
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "9c4d2e7f1b38"
down_revision = "7e3b9c1d5a20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("llm_allowed_models", ARRAY(sa.Text), nullable=False,
                  server_default=sa.text("'{}'::text[]")),
    )


def downgrade() -> None:
    op.drop_column("tenant", "llm_allowed_models")
