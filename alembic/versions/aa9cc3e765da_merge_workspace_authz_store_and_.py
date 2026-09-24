"""merge workspace_authz_store and workspace_da_suggested_question

Do not "simplify" this into a repoint of 470445259496 onto e1a3c5d7f9b2:
alembic counts every ancestor of the recorded version as applied, so that
marks e1a3c5d7f9b2's DDL done on databases already past it, without running it.

Revision ID: aa9cc3e765da
Revises: f3a1c5d7b920, e1a3c5d7f9b2
Create Date: 2026-08-27 11:42:20.669291

"""
from typing import Sequence, Union

revision: str = 'aa9cc3e765da'
down_revision: Union[str, Sequence[str], None] = ('f3a1c5d7b920', 'e1a3c5d7f9b2')


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
