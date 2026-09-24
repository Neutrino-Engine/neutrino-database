"""A genuine OpenFGA error during delete must not read as 'nothing to delete'."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from neutrino_database.fga.doc_acl import DocAclService


class _FailingClient:
    def __init__(self, exc): self.exc = exc
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def write(self, body, options=None): raise self.exc


def _service(monkeypatch, client):
    svc = DocAclService()
    monkeypatch.setattr(
        svc, "_get_or_create_store", AsyncMock(return_value=("s1", "m1"))
    )
    monkeypatch.setattr(svc, "_get_fga_client", lambda s, m: client)
    return svc


async def test_transport_error_counts_as_failed(monkeypatch):
    svc = _service(monkeypatch, _FailingClient(RuntimeError("connection reset")))
    client = svc._get_fga_client("s1", "m1")
    deleted, not_found, failed = await svc._delete_tuples(client, [object()], "m1")
    assert (deleted, not_found, failed) == (0, 0, 1)


async def test_genuine_not_found_is_tolerated(monkeypatch):
    svc = _service(
        monkeypatch, _FailingClient(RuntimeError("cannot delete a tuple which does not exist"))
    )
    client = svc._get_fga_client("s1", "m1")
    deleted, not_found, failed = await svc._delete_tuples(client, [object()], "m1")
    assert (deleted, not_found, failed) == (0, 1, 0)


@pytest.mark.parametrize(
    "method", ["revoke_access", "bulk_revoke_access", "unpublish_file"]
)
async def test_revoke_methods_fail_closed(monkeypatch, method):
    svc = _service(monkeypatch, _FailingClient(RuntimeError("connection reset")))
    fn = getattr(svc, method)
    if method == "bulk_revoke_access":
        result = await fn("ws1", [{"doc_id": "d1", "user_id": ["u1"]}])
        assert result == -1
    else:
        arg = ("ws1", "d1", "u1") if method == "revoke_access" else ("ws1", "d1")
        assert await fn(*arg) is False


async def test_sync_doc_permissions_fail_closed(monkeypatch):
    """Spec R9: sync_doc_permissions must not report success for a failed revoke."""
    svc = _service(monkeypatch, _FailingClient(RuntimeError("connection reset")))
    monkeypatch.setattr(
        svc,
        "_list_doc_direct_users",
        AsyncMock(return_value=(False, ["u1"])),
    )
    result = await svc.sync_doc_permissions("ws1", "d1", [])
    assert result["status"] == "error"
    assert result["error"]
