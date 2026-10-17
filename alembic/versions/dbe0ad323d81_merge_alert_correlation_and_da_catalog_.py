"""merge alert correlation and da catalog pruned_at heads

Revision ID: dbe0ad323d81
Revises: e7a1c3d5f9b2, e6f0a4b8c2d3
Create Date: 2026-10-17 12:58:18.340130

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dbe0ad323d81'
down_revision: Union[str, Sequence[str], None] = ('e7a1c3d5f9b2', 'e6f0a4b8c2d3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
