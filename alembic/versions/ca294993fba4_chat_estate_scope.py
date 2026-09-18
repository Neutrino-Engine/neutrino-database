"""chat estate scope

ITOps merge S5/S6 — an estate investigation (host or incident) is an
ordinary chat conversation, not a special surface. It carries a durable
scope on the row so a refresh or a reopen from history restores the same
chip, instead of the scope living only in the browser (the same argument
that put ``pillar`` on this table).

  * ``estate_scope_kind``  host | incident, nullable
  * ``estate_uid``         Text, nullable, not a FK — the uid identifies a
                            node in Neo4j, so there is no Postgres row to
                            reference
  * ``estate_display_name`` Text, nullable

All three are nullable: every non-estate chat has no scope, and existing
rows predate this column. Indexed on ``estate_uid`` — reopening an estate
conversation from history filters on the uid.

Revision ID: ca294993fba4
Revises: b3a639ade8d1
Create Date: 2026-09-09 14:43:32.466458

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


# revision identifiers, used by Alembic.
revision: str = 'ca294993fba4'
down_revision: Union[str, Sequence[str], None] = 'b3a639ade8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Explicit enum object, created up front and referenced by add_column with
# create_type=False so the column bind doesn't try to auto-create it again.
estate_scope_kind_enum = ENUM(
    "host",
    "incident",
    name="estate_scope_kind",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    estate_scope_kind_enum.create(op.get_bind(), checkfirst=False)
    op.add_column("chat", sa.Column("estate_scope_kind", estate_scope_kind_enum, nullable=True))
    op.add_column("chat", sa.Column("estate_uid", sa.Text(), nullable=True))
    op.add_column("chat", sa.Column("estate_display_name", sa.Text(), nullable=True))
    # Reopening an estate conversation from history filters on the uid.
    op.create_index("ix_chat_estate_uid", "chat", ["estate_uid"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_chat_estate_uid", table_name="chat")
    op.drop_column("chat", "estate_display_name")
    op.drop_column("chat", "estate_uid")
    op.drop_column("chat", "estate_scope_kind")
    sa.Enum(name="estate_scope_kind").drop(op.get_bind(), checkfirst=False)
