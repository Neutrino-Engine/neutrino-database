"""Daily LLM allowance per member, and the background reserve

A monthly allowance alone lets a member spend the whole month before lunch
on the first and be locked out for thirty days. The daily ceiling paces it.
NULL everywhere means "derive from the monthly figure", so nothing changes
for a workspace that has set nothing.

Revision ID: 3f9aa289344c
Revises: 2b5de8b9b8dd
Create Date: 2026-09-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3f9aa289344c"
down_revision: Union[str, Sequence[str], None] = "2b5de8b9b8dd"


def upgrade() -> None:
    op.add_column("workspace", sa.Column("daily_llm_usd_cap_per_user", sa.Numeric(10, 2), nullable=True))
    op.add_column("workspace", sa.Column("llm_background_reserve_pct", sa.Numeric(5, 2), nullable=True))
    op.add_column("workspace_member", sa.Column("daily_llm_usd_cap", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("workspace_member", "daily_llm_usd_cap")
    op.drop_column("workspace", "llm_background_reserve_pct")
    op.drop_column("workspace", "daily_llm_usd_cap_per_user")
