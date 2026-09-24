"""drop invitation role_key

Reverses 2581db9076d5. Custom roles are gone, so an invitation can no
longer name a tenant role.

Revision ID: f3a1c5d7b920
Revises: 2581db9076d5
Create Date: 2026-08-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a1c5d7b920'
down_revision: Union[str, Sequence[str], None] = '2581db9076d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("workspace_invitation", "role_key")
    op.drop_column("user_invitation", "role_key")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "user_invitation",
        sa.Column("role_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "workspace_invitation",
        sa.Column("role_key", sa.String(length=64), nullable=True),
    )
