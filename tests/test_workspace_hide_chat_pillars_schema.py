"""NC-500 — ``workspace.hide_chat_pillars``.

The chat sidebar used to draw its pillar picker for every workspace, so
every member was asked which engine should answer before they had asked
anything. This column turns the picker off and pins chat to Unified.

Two properties matter enough to pin at the schema level:

* **The default is True.** A workspace inserted without ever mentioning
  the column must come back Unified-only — that is how the gateway's own
  workspace auto-create inserts, and it is what makes the executive path
  the default path rather than something an admin has to remember.
* **It is independent of** ``enabled_pillars``. Presentation and
  capability are separate decisions: a workspace can have all three
  pillars and still show one Unified chat. If these ever fuse, tidying
  the chat UI would silently revoke a pillar.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from neutrino_database.models.enums import (
    PillarEnum,
    TenantStatusEnum,
    WorkspaceStatusEnum,
)
from neutrino_database.models.orm import Tenant, Workspace


def _unique() -> str:
    return uuid.uuid4().hex[:12]


class TestWorkspaceHideChatPillarsColumn:
    """Workspace gains a presentation flag for the chat pillar picker."""

    @pytest.mark.asyncio
    async def test_workspace_table_has_hide_chat_pillars_column(self, test_engine):
        async with test_engine.connect() as conn:
            cols = await conn.run_sync(
                lambda sync_conn: {
                    c["name"]: c
                    for c in sa.inspect(sync_conn).get_columns("workspace")
                }
            )

        assert "hide_chat_pillars" in cols, (
            "workspace.hide_chat_pillars column is missing — required to "
            "run a workspace's chat as Unified-only."
        )
        assert cols["hide_chat_pillars"]["nullable"] is False, (
            "hide_chat_pillars must be NOT NULL — a null would leave the "
            "chat surface with no answer about whether to draw the picker."
        )

    @pytest.mark.asyncio
    async def test_defaults_to_true(self, test_engine):
        """Insert without the column; the workspace comes back hidden."""
        SessionMaker = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        suffix = _unique()
        tenant_id = str(uuid.uuid4())
        workspace_id = str(uuid.uuid4())

        try:
            async with SessionMaker() as setup:
                async with setup.begin():
                    setup.add(
                        Tenant(
                            id=tenant_id,
                            name=f"acme-{suffix}",
                            org_external_id=f"acme-{suffix}",
                            status=TenantStatusEnum.ACTIVE,
                            created_at=datetime.now(UTC),
                            updated_at=datetime.now(UTC),
                        )
                    )
                    setup.add(
                        Workspace(
                            id=workspace_id,
                            tenant_id=tenant_id,
                            name=f"main-{suffix}",
                            status=WorkspaceStatusEnum.ACTIVE,
                            created_at=datetime.now(UTC),
                            updated_at=datetime.now(UTC),
                        )
                    )

            async with SessionMaker() as verify:
                row = await verify.get(Workspace, workspace_id)
                assert row is not None
                assert row.hide_chat_pillars is True, (
                    "hide_chat_pillars must default to True (Unified-only); "
                    f"got {row.hide_chat_pillars!r}"
                )
        finally:
            async with SessionMaker() as cleanup:
                async with cleanup.begin():
                    await cleanup.execute(
                        sa.delete(Workspace).where(Workspace.id == workspace_id)
                    )
                    await cleanup.execute(
                        sa.delete(Tenant).where(Tenant.id == tenant_id)
                    )

    @pytest.mark.asyncio
    async def test_independent_of_enabled_pillars(self, test_engine):
        """All three pillars enabled AND the picker hidden — the whole
        point of the column. Flipping it back leaves the pillar set
        untouched."""
        SessionMaker = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        suffix = _unique()
        tenant_id = str(uuid.uuid4())
        workspace_id = str(uuid.uuid4())
        all_pillars = [
            PillarEnum.ENTERPRISE_SEARCH,
            PillarEnum.DATA_ANALYTICS,
            PillarEnum.WORKFLOW_EXECUTION,
        ]

        try:
            async with SessionMaker() as setup:
                async with setup.begin():
                    setup.add(
                        Tenant(
                            id=tenant_id,
                            name=f"acme-{suffix}",
                            org_external_id=f"acme-{suffix}",
                            status=TenantStatusEnum.ACTIVE,
                            created_at=datetime.now(UTC),
                            updated_at=datetime.now(UTC),
                        )
                    )
                    setup.add(
                        Workspace(
                            id=workspace_id,
                            tenant_id=tenant_id,
                            name=f"main-{suffix}",
                            status=WorkspaceStatusEnum.ACTIVE,
                            enabled_pillars=all_pillars,
                            hide_chat_pillars=True,
                            created_at=datetime.now(UTC),
                            updated_at=datetime.now(UTC),
                        )
                    )

            async with SessionMaker() as verify:
                row = await verify.get(Workspace, workspace_id)
                assert row is not None
                assert row.hide_chat_pillars is True
                assert sorted(p.value for p in row.enabled_pillars) == sorted(
                    p.value for p in all_pillars
                ), "hiding the picker must not disturb enabled_pillars"

            async with SessionMaker() as update:
                async with update.begin():
                    await update.execute(
                        sa.update(Workspace)
                        .where(Workspace.id == workspace_id)
                        .values(hide_chat_pillars=False)
                    )

            async with SessionMaker() as reverify:
                row = await reverify.get(Workspace, workspace_id)
                assert row is not None
                assert row.hide_chat_pillars is False
                assert len(row.enabled_pillars) == 3, (
                    "handing the picker back must not disturb enabled_pillars"
                )
        finally:
            async with SessionMaker() as cleanup:
                async with cleanup.begin():
                    await cleanup.execute(
                        sa.delete(Workspace).where(Workspace.id == workspace_id)
                    )
                    await cleanup.execute(
                        sa.delete(Tenant).where(Tenant.id == tenant_id)
                    )
