"""A drift-heal that is not written back to the registry heals nothing.

``_heal_store_model_if_stale`` writes the canonical model to a stale store and
caches the store id in the process-local ``_HEALED_STORES`` set. If the new id
never reaches ``workspace_authz_store.model_id``, the next process start reads
the STALE id back out of the registry, asks OpenFGA for the deployed model,
finds it already canonical (the previous process wrote it), short-circuits, and
pins every client to a model with no ``viewer`` relation. Every canonical
viewer write (``replace_viewer_tuples``) then 400s.

So the assertion is about the second resolve, after the restart, not the first.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from neutrino_database.fga import doc_acl, load_model
from neutrino_database.fga.doc_acl import DocAclService


class _Row:
    """Stands in for the workspace_authz_store row, read fresh each time."""

    def __init__(self, registry: dict):
        self.store_id = registry["store_id"]
        self.model_id = registry["model_id"]


class _Session:
    """Applies the heal's UPDATE to the dict standing in for the row."""

    def __init__(self, registry: dict):
        self.registry = registry

    async def execute(self, stmt):
        params = stmt.compile().params
        if params.get("model_id"):
            self.registry["model_id"] = params["model_id"]
        return None

    async def commit(self):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _RaisingSession(_Session):
    """The registry is unreachable — the heal must stay fail-soft."""

    async def execute(self, stmt):
        raise RuntimeError("connection reset")


@pytest.fixture(autouse=True)
def _clean_process_cache():
    doc_acl._HEALED_STORES.clear()
    yield
    doc_acl._HEALED_STORES.clear()


@pytest.fixture
def registry():
    return {"store_id": "store-1", "model_id": "stale-model"}


def _service(monkeypatch, registry, session_cls=_Session):
    svc = DocAclService(session_factory=lambda: session_cls(registry))

    async def _read_store_row(session, workspace_id):
        return _Row(registry)

    monkeypatch.setattr(svc, "_read_store_row", _read_store_row)
    return svc


# A model that is not the canonical one, so the drift check sees drift.
_STALE_DEPLOYED = {"schema_version": "1.1", "type_definitions": [{"type": "user"}]}


async def test_healed_model_id_survives_a_restart(monkeypatch, registry):
    svc = _service(monkeypatch, registry)
    monkeypatch.setattr(
        svc, "_get_latest_model", AsyncMock(return_value=_STALE_DEPLOYED)
    )
    monkeypatch.setattr(
        svc, "_create_authorization_model", AsyncMock(return_value="healed-model")
    )

    assert await svc._get_or_create_store("ws-1") == ("store-1", "healed-model")

    # Restart: the process cache is gone, and the deployed model is now the
    # canonical one this heal just wrote, so the drift check short-circuits
    # and hands back whatever the registry holds.
    doc_acl._HEALED_STORES.clear()
    creator = AsyncMock(return_value="second-heal")
    monkeypatch.setattr(svc, "_create_authorization_model", creator)
    monkeypatch.setattr(svc, "_get_latest_model", AsyncMock(return_value=load_model()))

    assert await svc._get_or_create_store("ws-1") == ("store-1", "healed-model")
    creator.assert_not_awaited()


async def test_persist_failure_still_returns_the_healed_model(monkeypatch, registry):
    """The heal logs and carries on. It must not start raising where it
    previously fell back."""
    svc = _service(monkeypatch, registry, session_cls=_RaisingSession)
    monkeypatch.setattr(
        svc, "_get_latest_model", AsyncMock(return_value=_STALE_DEPLOYED)
    )
    monkeypatch.setattr(
        svc, "_create_authorization_model", AsyncMock(return_value="healed-model")
    )

    assert await svc._heal_store_model_if_stale("store-1", "stale-model") == (
        "healed-model"
    )


async def test_create_model_writes_shared_canonical_model(monkeypatch):
    """Merged from the two service-side copies: a new model is written from
    the neutrino_database SSOT, byte for byte."""
    svc = DocAclService()

    fake_client = AsyncMock()
    fake_client.write_authorization_model = AsyncMock(
        return_value=type("R", (), {"authorization_model_id": "m-new"})()
    )

    @asynccontextmanager
    async def _fake_base_client(store_id=None):
        yield fake_client

    monkeypatch.setattr(svc, "_get_base_client", _fake_base_client)

    assert await svc._create_authorization_model("store-1") == "m-new"
    fake_client.write_authorization_model.assert_awaited_once_with(load_model())


async def test_heal_uses_process_cache(monkeypatch):
    """Merged from the two service-side copies: a store already in
    ``_HEALED_STORES`` short-circuits before any read of the deployed model."""
    doc_acl._HEALED_STORES.add("store-cached")
    svc = DocAclService()
    read = AsyncMock(return_value=_STALE_DEPLOYED)
    monkeypatch.setattr(svc, "_get_latest_model", read)
    create = AsyncMock(return_value="nope")
    monkeypatch.setattr(svc, "_create_authorization_model", create)

    assert await svc._heal_store_model_if_stale("store-cached", "m-old") == "m-old"
    read.assert_not_awaited()
    create.assert_not_awaited()


async def test_registry_catches_up_to_a_migrator_written_model(monkeypatch, registry):
    """``make migrate-fga`` writes a new canonical model version and leaves the
    registry naming the old one; the hash still matches, so the heal must not
    hand back the registry's id.
    """
    svc = _service(monkeypatch, registry)
    deployed = dict(load_model(), id="migrator-model")
    monkeypatch.setattr(svc, "_get_latest_model", AsyncMock(return_value=deployed))
    creator = AsyncMock(return_value="a-third-model")
    monkeypatch.setattr(svc, "_create_authorization_model", creator)

    assert await svc._get_or_create_store("ws-1") == ("store-1", "migrator-model")
    assert registry["model_id"] == "migrator-model"
    # The store is already at head; adopting its id must not write a new model.
    creator.assert_not_awaited()
