"""tenant egress allow-list (NC-793 F1).

Adds egress_allowed_domains / egress_allowed_email_domains (TEXT[], default
empty) and egress_mode ('monitor' | 'enforce', default 'monitor'). Existing
tenants land in 'monitor' so nothing breaks; new-tenant creation code sets
'enforce' explicitly. Lowercasing is app-side.

Revision ID: 7e3b9c1d5a20
Revises: 4a240c4c431e
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "7e3b9c1d5a20"
down_revision = "4a240c4c431e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("egress_allowed_domains", "egress_allowed_email_domains"):
        op.add_column(
            "tenant",
            sa.Column(name, ARRAY(sa.Text), nullable=False,
                      server_default=sa.text("'{}'::text[]")),
        )
    op.add_column(
        "tenant",
        sa.Column("egress_mode", sa.Text, nullable=False,
                  server_default=sa.text("'monitor'")),
    )
    op.create_check_constraint(
        "ck_tenant_egress_mode", "tenant", "egress_mode IN ('monitor', 'enforce')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_tenant_egress_mode", "tenant", type_="check")
    op.drop_column("tenant", "egress_mode")
    op.drop_column("tenant", "egress_allowed_email_domains")
    op.drop_column("tenant", "egress_allowed_domains")
