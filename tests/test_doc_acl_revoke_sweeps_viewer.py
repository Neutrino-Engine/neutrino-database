"""A revoke must undo what the canonical grant path wrote.

``_build_viewer_tuples_for_doc`` (used by ``replace_viewer_tuples``) puts every
grant on ``viewer``. ``revoke_access`` used to delete only ``can_access``, so
for a canonically granted user it deleted nothing, ``_delete_tuples`` counted a
not-found, and the function logged "Permission already revoked" and returned
True. The caller was told the revoke succeeded while the user kept passing
``check_access`` through ``can_access = this OR viewer``.

The fake store below implements exactly that one model rule, so a revoke that
misses ``viewer`` shows up as a check that still returns True.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock

from neutrino_database.fga.doc_acl import DocAclService
from neutrino_database.models.canonical import PrincipalKind


class _FakeStore:
    """Tuple set plus the one model rule: can_access = direct OR viewer."""

    def __init__(self):
        self.tuples: set[tuple[str, str, str]] = set()

    def allowed(self, user: str, relation: str, obj: str) -> bool:
        if (user, relation, obj) in self.tuples:
            return True
        if relation == "can_access":
            return ("user:*", "can_access", obj) in self.tuples or (
                user,
                "viewer",
                obj,
            ) in self.tuples
        return False


class _FakeClient:
    def __init__(self, store: _FakeStore):
        self.store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def read(self, body, options=None):
        keys = [
            SimpleNamespace(key=SimpleNamespace(user=u, relation=r, object=o))
            for (u, r, o) in sorted(self.store.tuples)
            if o == body.object and r == body.relation
        ]
        return SimpleNamespace(tuples=keys, continuation_token=None)

    async def write(self, body, options=None):
        for t in body.writes or []:
            self.store.tuples.add((t.user, t.relation, t.object))
        for t in body.deletes or []:
            key = (t.user, t.relation, t.object)
            if key not in self.store.tuples:
                raise RuntimeError("cannot delete a tuple which does not exist")
            self.store.tuples.remove(key)
        return SimpleNamespace()

    async def check(self, body, options=None):
        return SimpleNamespace(
            allowed=self.store.allowed(body.user, body.relation, body.object)
        )


@pytest.fixture
def store():
    return _FakeStore()


@pytest.fixture
def service(monkeypatch, store):
    svc = DocAclService()
    monkeypatch.setattr(
        svc, "_get_or_create_store", AsyncMock(return_value=("s1", "m1"))
    )
    client = _FakeClient(store)
    monkeypatch.setattr(svc, "_get_fga_client", lambda s, m: client)
    monkeypatch.setattr(svc, "_get_base_client", lambda s=None: client)
    return svc


def _user(uid: str):
    return SimpleNamespace(kind=PrincipalKind.USER, neutrino_id=uid)


async def test_revoke_undoes_a_canonical_viewer_grant(service, store):
    granted = await service.replace_viewer_tuples("ws1", "d1", [_user("u1")])
    assert granted["status"] == "success" and granted["granted"] == 1
    assert await service.check_access("ws1", "d1", "u1") is True

    assert await service.revoke_access("ws1", "d1", "u1") is True

    assert await service.check_access("ws1", "d1", "u1") is False
    assert store.tuples == set()


async def test_revoke_still_undoes_a_legacy_can_access_grant(service, store):
    """Sweeping both relations must not regress the legacy direct grant: the
    viewer delete is a not-found, which is not a failure."""
    store.tuples.add(("user:u1", "can_access", "doc:d1"))

    assert await service.revoke_access("ws1", "d1", "u1") is True
    assert await service.check_access("ws1", "d1", "u1") is False


async def test_viewer_granted_users_are_listed(service):
    """``_list_doc_direct_users`` fed sync_doc_permissions. Reading only
    ``can_access`` meant a canonically granted user was invisible to it."""
    await service.replace_viewer_tuples("ws1", "d1", [_user("u1"), _user("u2")])

    is_public, user_ids = await service._list_doc_direct_users("ws1", "d1")

    assert is_public is False
    assert sorted(user_ids) == ["u1", "u2"]
