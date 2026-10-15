"""NC-739 H5: tombstone catalog rows instead of deleting them.

Adds a nullable ``pruned_at`` to da_catalog_schema / table / column. A sync
sets it when it no longer finds a row and clears it on rediscovery, so the row
id, its is_pii / is_restricted flags and any grant on that id survive a prune.

Revision ID: e6f0a4b8c2d3
Revises: d5e9f3a7b1c2
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6f0a4b8c2d3"
down_revision: Union[str, Sequence[str], None] = "d5e9f3a7b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("da_catalog_schema", "da_catalog_table", "da_catalog_column")


def upgrade() -> None:
    for t in _TABLES:
        op.add_column(t, sa.Column("pruned_at", sa.TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    # Rows tombstoned by a sync have no meaning in the old shape: drop them
    # child-first so foreign keys cannot block.
    op.execute("DELETE FROM da_catalog_column WHERE pruned_at IS NOT NULL")
    op.execute("DELETE FROM da_catalog_table WHERE pruned_at IS NOT NULL")
    op.execute("DELETE FROM da_catalog_schema WHERE pruned_at IS NOT NULL")
    for t in reversed(_TABLES):
        op.drop_column(t, "pruned_at")
