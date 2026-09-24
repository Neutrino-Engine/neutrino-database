"""Backfill workspace_authz_store from existing OpenFGA stores.

Run this once per environment BEFORE any process hits the new
DocAclService client. ``_get_or_create_store`` never looks a store up by
NAME, so a workspace whose ``{workspace_id}_file_permissions`` store
already exists but has no mapping row gets a second, empty store on
first access and every existing document-ACL tuple becomes invisible.

This script lists OpenFGA stores, matches names
``{workspace_id}_file_permissions`` (the same shape as
``DocAclService._get_store_name``), and maps each one onto
``workspace_authz_store (workspace_id, store_id, model_id)``.

Safe to run twice. A workspace already mapped to a store is left exactly
as it is, so a second run writes nothing. The one row it does rewrite is
a ``store_id IS NULL`` claim left behind by the retired claim-row
protocol, which would otherwise be filled with a second store on first
access.

Do not run against production from a workstation without an explicit ops
plan.

Usage::

    OPENFGA_API_URL=http://localhost:8080 \\
    DATABASE_URL=postgresql://... \\
        python -m neutrino_database.fga.backfill_workspace_authz_store
"""

from __future__ import annotations

import logging
import uuid

from neutrino_database.fga.migrate import MANAGED_STORE_SUFFIX

logger = logging.getLogger(__name__)


def workspace_id_from_store_name(name: str) -> str | None:
    """Inverse of ``DocAclService._get_store_name``.

    Returns the workspace id when ``name`` is
    ``{workspace_id}_file_permissions`` and the prefix is a UUID;
    otherwise None (tenant RBAC stores, empty prefix, junk names).
    """
    if not name.endswith(MANAGED_STORE_SUFFIX):
        return None
    prefix = name[: -len(MANAGED_STORE_SUFFIX)]
    if not prefix:
        return None
    try:
        uuid.UUID(prefix)
    except ValueError:
        return None
    return prefix


async def collect_mappings(client) -> list[tuple[str, str, str]]:
    """Return ``(workspace_id, store_id, model_id)`` for managed stores.

    First store wins when OpenFGA has duplicate names. Stores with no
    authorization model are skipped.
    """
    mappings: list[tuple[str, str, str]] = []
    seen: dict[str, str] = {}
    stores = await client.list_stores()
    for store_id, name in stores:
        workspace_id = workspace_id_from_store_name(name)
        if workspace_id is None:
            continue
        if workspace_id in seen:
            logger.warning(
                "duplicate store name for workspace %s: keeping %s, skipping %s",
                workspace_id,
                seen[workspace_id],
                store_id,
            )
            continue
        model = await client.read_latest_model(store_id)
        model_id = (model or {}).get("id")
        if not model_id:
            logger.warning(
                "store %s (%s) has no authorization model; skipping",
                store_id,
                name,
            )
            continue
        seen[workspace_id] = store_id
        mappings.append((workspace_id, store_id, model_id))
    return mappings


def upsert_mappings(conn, mappings: list[tuple[str, str, str]]) -> list[str]:
    """Map each workspace onto its store. Returns the workspace ids written.

    One statement. The join onto ``workspace`` does what a per-row
    existence check did, and does it without letting a single store whose
    workspace has since been deleted abort the whole batch on the foreign
    key — which is why the join is here rather than a bare reliance on the
    constraint. ON CONFLICT then makes a second run a no-op, so there is
    no savepoint and no IntegrityError to catch.

    A real ``store_id`` is never overwritten. The conflict clause fires
    only on a NULL one.
    """
    from sqlalchemy import String, column, select, values
    from sqlalchemy.dialects.postgresql import UUID, insert

    from neutrino_database.models.tables import workspace, workspace_authz_store

    if not mappings:
        return []

    incoming = values(
        column("workspace_id", UUID(as_uuid=False)),
        column("store_id", String(64)),
        column("model_id", String(64)),
        name="incoming",
    ).data(mappings)

    stmt = insert(workspace_authz_store).from_select(
        ["workspace_id", "store_id", "model_id"],
        select(
            incoming.c.workspace_id, incoming.c.store_id, incoming.c.model_id
        ).join_from(incoming, workspace, workspace.c.id == incoming.c.workspace_id),
    )
    written = [
        str(row[0])
        for row in conn.execute(
            stmt.on_conflict_do_update(
                index_elements=["workspace_id"],
                set_={
                    "store_id": stmt.excluded.store_id,
                    "model_id": stmt.excluded.model_id,
                },
                where=workspace_authz_store.c.store_id.is_(None),
            ).returning(workspace_authz_store.c.workspace_id)
        )
    ]

    # A managed store with no row at all after that had no workspace to
    # join to. Name it: this is the one case an operator has to act on.
    mapped = sorted({workspace_id for workspace_id, _, _ in mappings})
    present = set(
        conn.scalars(
            select(workspace_authz_store.c.workspace_id).where(
                workspace_authz_store.c.workspace_id.in_(mapped)
            )
        )
    )
    for workspace_id, store_id, _ in mappings:
        if workspace_id not in present:
            logger.warning(
                "no workspace row for %s (store %s); not mapped",
                workspace_id,
                store_id,
            )
    return written


async def run() -> tuple[int, list[str]]:
    """Returns ``(managed stores found, workspace ids written)``."""
    import os

    from sqlalchemy import create_engine

    from neutrino_database.config import settings
    from neutrino_database.fga._client import OpenFgaAdminClient

    api_url = os.environ.get("OPENFGA_API_URL", "http://localhost:8080")
    api_token = os.environ.get("OPENFGA_API_TOKEN") or None
    allow_insecure_http = os.environ.get("OPENFGA_ALLOW_INSECURE_HTTP", "").lower() in (
        "1",
        "true",
        "yes",
    )
    client = OpenFgaAdminClient(
        api_url,
        api_token=api_token,
        allow_insecure_http=allow_insecure_http,
    )
    mappings = await collect_mappings(client)

    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg2://",
    )
    engine = create_engine(sync_url)
    try:
        with engine.begin() as conn:
            written = upsert_mappings(conn, mappings)
    finally:
        engine.dispose()

    return len(mappings), written


def main() -> None:
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    found, written = asyncio.run(run())
    for workspace_id in written:
        logger.info("mapped workspace %s", workspace_id)
    logger.info(
        "%d managed store(s) in OpenFGA, %d row(s) written, %d left as-is",
        found,
        len(written),
        found - len(written),
    )


if __name__ == "__main__":
    main()
