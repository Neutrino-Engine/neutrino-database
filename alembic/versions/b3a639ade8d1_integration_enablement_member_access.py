"""integration_workspace_enablement.member_access — Audience (NC-637)

Placement (an enablement row) admits a workspace to a Company connection.
Audience says who inside that workspace may use it. Before this column the two
were fused and Audience was deny-by-default, so a placed connection was usable
by Tenant Admins and by nobody else — the only writer of grant rows is an API
endpoint no screen calls. See docs/adr/0001-placement-and-audience-are-separate.md.

The back-fill is the load-bearing half. A placement that already carries a
hand-written allow grant was deliberately scoped to named people, so it keeps
that shape; everything else opens to the workspace. No deployment silently
gains reach on upgrade.

Revision ID: b3a639ade8d1
Revises: aa9cc3e765da
Create Date: 2026-09-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b3a639ade8d1'
down_revision: Union[str, Sequence[str], None] = 'aa9cc3e765da'


def upgrade() -> None:
    op.add_column(
        "integration_workspace_enablement",
        sa.Column(
            "member_access",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'all_members'"),
        ),
    )
    op.execute(
        """
        UPDATE integration_workspace_enablement e
           SET member_access = 'selected_members'
         WHERE EXISTS (
                   SELECT 1
                     FROM integration_member_grant g
                    WHERE g.integration_id = e.integration_id
                      AND g.workspace_id   = e.workspace_id
                      AND g.effect         = 'allow'
               )
        """
    )


def downgrade() -> None:
    op.drop_column("integration_workspace_enablement", "member_access")
