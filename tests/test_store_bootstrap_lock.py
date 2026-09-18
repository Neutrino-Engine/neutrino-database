"""A store bootstrap whose creator died must not brick the workspace.

The previous protocol inserted a claim row with ``store_id IS NULL`` before
calling CreateStore, and recovered a creator that died mid-flight with an
UPDATE matching on ``created_at`` older than a 60-second threshold. A
timestamp cannot tell a dead creator from a slow one, so it got both
directions wrong: it took the claim off creators that were still alive (two
OpenFGA stores for one workspace, and every tuple written through the first
one invisible), and it made every caller poll for 30 seconds and fail for a
full minute after a genuine crash before the first takeover was even
eligible.

``pg_advisory_xact_lock`` is a lease, so it needs no threshold. Postgres drops
it when the transaction ends and when the holding connection dies, which is
exactly the distinction the timestamp was guessing at.

These tests run against real Postgres. The mechanism IS an advisory lock and
an in-Python fake session cannot express one, so a fake would pass while the
real thing deadlocked.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from neutrino_database.fga import doc_acl
from neutrino_database.fga.doc_acl import DocAclService
from neutrino_database.models.tables import (
    tenant,
    workspace,
    workspace_authz_store,
)


@pytest_asyncio.fixture
async def ws_id(test_engine):
    """A committed workspace row.

    ``workspace_authz_store.workspace_id`` carries a foreign key to
    ``workspace.id``, and the rows have to be committed because each caller
    below reads them over its own connection.
    """
    tenant_id, workspace_id = str(uuid.uuid4()), str(uuid.uuid4())
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sessions() as session:
        await session.execute(
            insert(tenant).values(
                id=tenant_id, name="Acme", org_external_id=f"ext-{tenant_id}"
            )
        )
        await session.execute(
            insert(workspace).values(
                id=workspace_id, tenant_id=tenant_id, name=f"ws-{workspace_id}"
            )
        )
        await session.commit()

    yield workspace_id

    async with sessions() as session:
        # ON DELETE CASCADE takes the workspace and its registry row.
        await session.execute(delete(tenant).where(tenant.c.id == tenant_id))
        await session.commit()


@pytest.fixture
def sessions(test_engine):
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
def service(sessions):
    """A service whose sessions are independent connections.

    Independence is the whole point: an advisory lock belongs to a connection,
    so callers sharing one session would each hold the lock they are supposed
    to be queueing behind. ``test_engine`` uses NullPool, so every session here
    opens its own connection.
    """

    @asynccontextmanager
    async def session_factory():
        async with sessions() as session:
            yield session

    return DocAclService(session_factory=session_factory)


class _Fga:
    """Stand-in for OpenFGA's store registry, which permits name collisions."""

    def __init__(self, *, store_id="store-1", delay=0.0):
        self._store_id = store_id
        self._delay = delay
        self.created: list[str] = []

    def install(self, monkeypatch, service):
        async def _create_store(name):
            await asyncio.sleep(self._delay)
            if self._store_id is None:
                return None
            store_id = f"{self._store_id}-{len(self.created) + 1}"
            self.created.append(store_id)
            return store_id

        async def _create_model(store_id):
            return "model-1"

        async def _heal(store_id, model_id):
            return model_id

        monkeypatch.setattr(service, "_create_store", _create_store)
        monkeypatch.setattr(service, "_create_authorization_model", _create_model)
        monkeypatch.setattr(service, "_heal_store_model_if_stale", _heal)
        return self


async def _registry_row(sessions, workspace_id):
    async with sessions() as session:
        result = await session.execute(
            select(workspace_authz_store).where(
                workspace_authz_store.c.workspace_id == workspace_id
            )
        )
        return result.first()


async def test_bootstrap_registers_the_store_once(
    service, sessions, ws_id, monkeypatch
):
    """Baseline. The second call takes the fast path and creates nothing."""
    fga = _Fga().install(monkeypatch, service)

    first = await service._get_or_create_store(ws_id)
    second = await service._get_or_create_store(ws_id)

    assert first == ("store-1-1", "model-1")
    assert second == first
    assert fga.created == ["store-1-1"]
    row = await _registry_row(sessions, ws_id)
    assert (row.store_id, row.model_id) == ("store-1-1", "model-1")


async def test_a_failed_bootstrap_leaves_no_row_and_the_next_caller_retries(
    service, sessions, ws_id, monkeypatch
):
    """This is what the takeover mechanism existed to repair, now structural.

    The registry write and the CreateStore call share one transaction, so a
    bootstrap that fails, or a process killed mid-flight, commits nothing.
    There is no half-written claim row to recover and no dead window: the very
    next caller creates the store.
    """
    dead = _Fga(store_id=None).install(monkeypatch, service)

    assert await service._get_or_create_store(ws_id) is None
    assert dead.created == []
    assert await _registry_row(sessions, ws_id) is None

    alive = _Fga(store_id="store-2").install(monkeypatch, service)
    assert await service._get_or_create_store(ws_id) == ("store-2-1", "model-1")
    assert alive.created == ["store-2-1"]


async def test_a_leftover_null_claim_row_is_filled(
    service, sessions, ws_id, monkeypatch
):
    """Migration case. Environments running the claim protocol can already hold
    a ``store_id IS NULL`` row, which has to be filled rather than collided
    with on the primary key."""
    async with sessions() as session:
        await session.execute(
            insert(workspace_authz_store).values(
                workspace_id=ws_id, store_id=None, model_id=None
            )
        )
        await session.commit()

    fga = _Fga().install(monkeypatch, service)

    assert await service._get_or_create_store(ws_id) == ("store-1-1", "model-1")
    assert fga.created == ["store-1-1"]
    row = await _registry_row(sessions, ws_id)
    assert (row.store_id, row.model_id) == ("store-1-1", "model-1")


async def test_a_store_created_while_we_waited_is_reused_not_duplicated(
    service, sessions, ws_id, monkeypatch
):
    """The double-checked read. The caller that loses the lock re-reads the
    registry after acquiring it, finds the row the previous holder committed,
    and never reaches the OpenFGA API."""
    fga = _Fga(delay=0.2).install(monkeypatch, service)

    results = await asyncio.gather(
        *(service._get_or_create_store(ws_id) for _ in range(4))
    )

    assert fga.created == ["store-1-1"], (
        f"{len(fga.created)} stores for one workspace — tuples written through "
        "one are invisible to checks against the other"
    )
    assert set(results) == {("store-1-1", "model-1")}


async def test_a_caller_that_cannot_get_the_lock_fails_closed(
    service, sessions, ws_id, monkeypatch
):
    """The bound. A waiter gives up on ``lock_timeout`` and returns None rather
    than holding a pooled connection until the holder finishes, so the pool
    cannot be drained by callers queueing on one cold workspace."""
    monkeypatch.setattr(doc_acl, "_STORE_LOCK_WAIT_SECONDS", 0.25)
    fga = _Fga().install(monkeypatch, service)

    async with sessions() as blocker:
        await blocker.execute(text("SELECT pg_advisory_xact_lock(hashtext(:w))"), {"w": ws_id})

        assert await service._get_or_create_store(ws_id) is None
        assert fga.created == []

        await blocker.rollback()

    # The lock went with the blocker's transaction; nothing is stuck.
    assert await service._get_or_create_store(ws_id) == ("store-1-1", "model-1")
