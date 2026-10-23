"""ADLC WS3: packages and promotion.

- ``workspace.protected`` / ``two_person_activation`` (D13, D22).
- ``promotion_path``: Dev -> UAT -> Live inside a tenant (D12, D34).
- ``package_trusted_key``: public keys whose bundles a tenant accepts (D20).
- ``package_import``: provenance of every import.
- ``import_id`` on the three version tables.
- ``studio_test_case.synthetic`` (D29).

No backfill: every workspace starts unprotected, so nothing changes.

Revision ID: c9f3e5a7b1d4
Revises: b8e2d4f6a0c3
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "c9f3e5a7b1d4"
down_revision: Union[str, Sequence[str], None] = "b8e2d4f6a0c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VERSION_TABLES = ("workflow_version", "studio_agent_version", "studio_team_version")


def upgrade() -> None:
    op.add_column("workspace", sa.Column("protected", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("workspace", sa.Column("two_person_activation", sa.Boolean(), nullable=False, server_default=sa.text("true")))

    op.create_table(
        "promotion_path",
        sa.Column("source_workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspace.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("target_workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("updated_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_workspace_id <> target_workspace_id", name="ck_promotion_path_distinct"),
    )
    op.create_table(
        "package_trusted_key",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("added_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("added_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "key_id", name="uq_package_trusted_key"),
    )
    op.create_table(
        "package_import",
        sa.Column("id", UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=False), sa.ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=False), sa.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bundle_sha256", sa.String(64), nullable=False),
        sa.Column("source", JSONB(), nullable=False),
        sa.Column("root", JSONB(), nullable=False),
        sa.Column("bindings", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("imported_by", UUID(as_uuid=False), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("imported_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_package_import_workspace", "package_import", ["workspace_id", "imported_at"])

    op.add_column("studio_test_case", sa.Column("synthetic", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    for table in _VERSION_TABLES:
        op.add_column(table, sa.Column("import_id", UUID(as_uuid=False), nullable=True))
        op.create_foreign_key(f"fk_{table}_import", table, "package_import", ["import_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    for table in _VERSION_TABLES:
        op.drop_constraint(f"fk_{table}_import", table, type_="foreignkey")
        op.drop_column(table, "import_id")
    op.drop_column("studio_test_case", "synthetic")
    op.drop_index("ix_package_import_workspace", table_name="package_import")
    op.drop_table("package_import")
    op.drop_table("package_trusted_key")
    op.drop_table("promotion_path")
    op.drop_column("workspace", "two_person_activation")
    op.drop_column("workspace", "protected")
