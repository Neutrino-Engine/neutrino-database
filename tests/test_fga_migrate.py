"""[NC-113-a] FGA migrator — the ``alembic upgrade head`` analogue for OpenFGA.

Sweeps every store, and for any store whose deployed model is missing or not
the canonical schema, writes the current model — converging all stores. Run on
deploy (after ``alembic upgrade head``). Idempotent: a store already at head is
skipped. Per-store failures are isolated so one bad store can't abort the sweep.

These tests drive the pure orchestration (``migrate_all_stores``) through a fake
admin client — no live OpenFGA needed.
"""

from __future__ import annotations

import copy

import pytest

from neutrino_database.fga import model as fga_model
from neutrino_database.fga.migrate import MANAGED_STORE_SUFFIX, migrate_all_stores


# A pre-NC-113-a stale model: user + doc/can_access only (the connector-service
# model that caused the bug). Its semantic hash differs from the source.
STALE_MODEL = {
    "schema_version": "1.1",
    "type_definitions": [
        {"type": "user"},
        {
            "type": "doc",
            "relations": {"can_access": {"this": {}}},
            "metadata": {
                "relations": {
                    "can_access": {
                        "directly_related_user_types": [{"type": "user"}]
                    }
                }
            },
        },
    ],
}


def _deployed_readback() -> dict:
    """The canonical model as OpenFGA would hand it back (assigned id, empty
    metadata materialized, computedUserset without the empty object)."""
    m = copy.deepcopy(fga_model.load_model())
    m["id"] = "01DEPLOYEDREADBACK"
    for t in m["type_definitions"]:
        if t["type"] == "user":
            t["metadata"] = {}
        if t["type"] == "doc":
            for child in t["relations"]["can_access"]["union"]["child"]:
                cu = child.get("computedUserset")
                if cu is not None:
                    cu.pop("object", None)
    return m


class FakeFgaAdmin:
    """In-memory stand-in for the OpenFGA admin surface the migrator needs."""

    def __init__(self, stores: dict[str, dict | None], fail_write: set[str] | None = None):
        self.stores = dict(stores)  # store_id -> deployed model (or None)
        self.fail_write = fail_write or set()
        self.writes: list[str] = []

    async def list_stores(self) -> list[tuple[str, str]]:
        return [(sid, f"{sid}{MANAGED_STORE_SUFFIX}") for sid in self.stores]

    async def read_latest_model(self, store_id: str) -> dict | None:
        return self.stores.get(store_id)

    async def write_model(self, store_id: str, model: dict) -> str:
        if store_id in self.fail_write:
            raise RuntimeError(f"FGA write failed for {store_id}")
        self.writes.append(store_id)
        self.stores[store_id] = model
        return f"model-{store_id}"


@pytest.mark.asyncio
async def test_migrates_store_with_stale_model():
    client = FakeFgaAdmin({"s-stale": STALE_MODEL})
    report = await migrate_all_stores(client)
    assert report.migrated == ["s-stale"]
    assert report.skipped == []
    assert client.writes == ["s-stale"]
    # the model written is the canonical source
    assert client.stores["s-stale"] == fga_model.load_model()


@pytest.mark.asyncio
async def test_skips_store_already_at_head():
    client = FakeFgaAdmin({"s-current": _deployed_readback()})
    report = await migrate_all_stores(client)
    assert report.skipped == ["s-current"]
    assert report.migrated == []
    assert client.writes == []  # idempotent — no rewrite


@pytest.mark.asyncio
async def test_migrates_store_with_no_model():
    client = FakeFgaAdmin({"s-empty": None})
    report = await migrate_all_stores(client)
    assert report.migrated == ["s-empty"]
    assert client.writes == ["s-empty"]


@pytest.mark.asyncio
async def test_failure_on_one_store_does_not_abort_the_sweep():
    client = FakeFgaAdmin(
        {"s-ok": STALE_MODEL, "s-bad": STALE_MODEL},
        fail_write={"s-bad"},
    )
    report = await migrate_all_stores(client)
    assert report.migrated == ["s-ok"]
    assert [s for s, _ in report.failed] == ["s-bad"]
    assert report.ok is False  # a failure makes the run not-ok


@pytest.mark.asyncio
async def test_report_shape_and_ok():
    client = FakeFgaAdmin({"a": STALE_MODEL, "b": _deployed_readback()})
    report = await migrate_all_stores(client)
    assert report.total == 2
    assert set(report.migrated) == {"a"}
    assert set(report.skipped) == {"b"}
    assert report.ok is True
    d = report.as_dict()
    assert d["migrated"] == ["a"] and d["skipped"] == ["b"]


# ── NC-494: the migrator must only touch its own model family ─────────


class FakeNamedFgaAdmin(FakeFgaAdmin):
    """Adds the name-aware listing the real client now provides."""

    def __init__(self, stores, names, fail_write=None):
        super().__init__(stores, fail_write)
        self.names = dict(names)

    async def list_stores(self):
        return [(sid, self.names[sid]) for sid in self.stores]


@pytest.mark.asyncio
async def test_tenant_rbac_stores_are_never_written():
    """The bug this guards: an unfiltered sweep wrote the document-ACL model
    onto every ``neutrino-tenant-*`` RBAC store in the cluster (355 of them on
    a local run; 31 found already corrupted). Those stores belong to the
    gateway and use a different model from a different source file."""
    client = FakeNamedFgaAdmin(
        stores={
            "s-ws-1": STALE_MODEL,          # ours, needs migrating
            "s-tenant-1": STALE_MODEL,      # gateway's — must be left alone
            "s-tenant-2": None,             # gateway's, no model — still alone
        },
        names={
            "s-ws-1": "ws-uuid-1_file_permissions",
            "s-tenant-1": "neutrino-tenant-aaa",
            "s-tenant-2": "neutrino-tenant-bbb",
        },
    )
    report = await migrate_all_stores(client)

    assert client.writes == ["s-ws-1"], (
        "migrator wrote to a store outside its own model family"
    )
    assert report.migrated == ["s-ws-1"]
    assert report.not_managed == ["s-tenant-1", "s-tenant-2"]
    # And the foreign stores are untouched.
    assert client.stores["s-tenant-1"] == STALE_MODEL
    assert client.stores["s-tenant-2"] is None


@pytest.mark.asyncio
async def test_not_managed_stores_are_reported_not_hidden():
    """A run that migrates nothing must still show what it skipped, so
    "0 migrated" isn't mistaken for "everything already converged"."""
    client = FakeNamedFgaAdmin(
        stores={"s-tenant-1": STALE_MODEL},
        names={"s-tenant-1": "neutrino-tenant-aaa"},
    )
    report = await migrate_all_stores(client)
    assert report.migrated == [] and report.skipped == []
    assert report.not_managed == ["s-tenant-1"]
    assert report.as_dict()["not_managed"] == ["s-tenant-1"]
    assert report.ok is True


