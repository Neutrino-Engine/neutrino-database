"""TOTP MFA (NC-795 G-30).

mfa_totp: one row per local user or platform operator (CHECK exactly one),
AES-GCM secret + optional key id, enrolled_at (NULL = pending), last used
RFC 6238 step (replay guard), bcrypt-hashed recovery codes.
tenant.require_mfa_local BOOLEAN NOT NULL DEFAULT false: existing tenants
off; new-tenant creation turns it on app-side.

Revision ID: b4d2e6f8a1c3
Revises: 7e3b9c1d5a20
Create Date: 2026-10-22
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "b4d2e6f8a1c3"
down_revision = "7e3b9c1d5a20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column("require_mfa_local", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.create_table(
        "mfa_totp",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=True),
        sa.Column("platform_user_id", UUID(as_uuid=False),
                  sa.ForeignKey("platform_user.id", ondelete="CASCADE"), nullable=True),
        sa.Column("secret_encrypted", sa.Text, nullable=False),
        sa.Column("secret_key_id", sa.String(64), nullable=True),
        sa.Column("enrolled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_used_step", sa.BigInteger, nullable=True),
        sa.Column("recovery_code_hashes", ARRAY(sa.Text), nullable=False,
                  server_default=sa.text("'{}'::text[]")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("(user_id IS NULL) <> (platform_user_id IS NULL)", name="ck_mfa_totp_one_owner"),
        sa.UniqueConstraint("user_id", name="ux_mfa_totp_user"),
        sa.UniqueConstraint("platform_user_id", name="ux_mfa_totp_platform_user"),
    )


def downgrade() -> None:
    op.drop_table("mfa_totp")
    op.drop_column("tenant", "require_mfa_local")
