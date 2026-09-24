"""The merged client keeps connector-service's failure reporting and
ES-Ingestion's canonical viewer helpers."""
from __future__ import annotations

import inspect

from neutrino_database.fga.doc_acl import DocAclService


def test_delete_tuples_reports_failures_separately():
    sig = inspect.signature(DocAclService._delete_tuples)
    assert "tuples" in sig.parameters
    src = inspect.getsource(DocAclService._delete_tuples)
    assert "failed_count" in src, "must keep connector-service's third counter"


def test_canonical_viewer_helpers_exist_after_the_merge():
    for name in (
        "replace_viewer_tuples",
        "replace_group_members",
        "revoke_all_doc_tuples",
    ):
        assert hasattr(DocAclService, name), f"{name} lost in the merge"
