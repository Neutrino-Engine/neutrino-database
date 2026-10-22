"""Entry 120: the Store B membership tuple is written once per process, and
an "already exists" reply is not a failure."""

import pytest

from neutrino_database.fga import doc_acl
from neutrino_database.fga.doc_acl import DocAclService


class _Client:
    def __init__(self, error=None):
        self.error = error
        self.writes = 0

    async def write(self, body, options=None):
        self.writes += 1
        if self.error:
            raise RuntimeError(self.error)


@pytest.fixture(autouse=True)
def _clear():
    doc_acl._MEMBERSHIP_WRITTEN.clear()
    yield
    doc_acl._MEMBERSHIP_WRITTEN.clear()


@pytest.mark.asyncio
async def test_existing_tuple_counts_as_written_and_is_not_written_again(caplog):
    svc = DocAclService(session_factory=None)
    client = _Client("[write] HTTP 400 cannot write a tuple which already exists")

    await svc._ensure_workspace_membership(client, "m1", "ws1", "u1")
    await svc._ensure_workspace_membership(client, "m1", "ws1", "u1")

    assert client.writes == 1
    assert not [r for r in caplog.records if r.levelname == "WARNING"]


@pytest.mark.asyncio
async def test_a_real_failure_is_retried_on_the_next_listing():
    svc = DocAclService(session_factory=None)
    client = _Client("connection reset")

    await svc._ensure_workspace_membership(client, "m1", "ws1", "u1")
    await svc._ensure_workspace_membership(client, "m1", "ws1", "u1")

    assert client.writes == 2
