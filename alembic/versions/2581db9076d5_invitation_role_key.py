"""invitation_role_key

Revision ID: 2581db9076d5
Revises: 470445259496
Create Date: 2026-08-26 01:25:27.294428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2581db9076d5'
down_revision: Union[str, Sequence[str], None] = '470445259496'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_invitation",
        sa.Column("role_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "workspace_invitation",
        sa.Column("role_key", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("workspace_invitation", "role_key")
    op.drop_column("user_invitation", "role_key")
