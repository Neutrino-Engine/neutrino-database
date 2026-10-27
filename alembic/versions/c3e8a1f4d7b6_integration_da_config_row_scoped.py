"""integration_da_config.row_scoped (NC-826).

Adds row_scoped (BOOLEAN, default false). When true, connector-service runs
each query with the signed-in user's email set on the transaction so the
warehouse's row-level security policies apply. Existing connections are
unaffected.

Revision ID: c3e8a1f4d7b6
Revises: 9c4d2e7f1b38
Create Date: 2026-10-28
"""
import sqlalchemy as sa
from alembic import op

revision = "c3e8a1f4d7b6"
down_revision = "9c4d2e7f1b38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "integration_da_config",
        sa.Column("row_scoped", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("integration_da_config", "row_scoped")
