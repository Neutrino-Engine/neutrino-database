"""Name-parse helper for the A4 workspace_authz_store backfill."""
from __future__ import annotations

from neutrino_database.fga.backfill_workspace_authz_store import (
    workspace_id_from_store_name,
)
from neutrino_database.fga.doc_acl import DocAclService


def test_parses_workspace_id_from_store_name():
    ws = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert workspace_id_from_store_name(f"{ws}_file_permissions") == ws


def test_round_trips_doc_acl_store_name():
    svc = DocAclService.__new__(DocAclService)
    ws = "11111111-2222-3333-4444-555555555555"
    assert workspace_id_from_store_name(svc._get_store_name(ws)) == ws


def test_rejects_tenant_rbac_store_name():
    assert workspace_id_from_store_name("neutrino-tenant-abc") is None


def test_rejects_empty_prefix():
    assert workspace_id_from_store_name("_file_permissions") is None


def test_rejects_non_uuid_prefix():
    assert workspace_id_from_store_name("not-a-uuid_file_permissions") is None
