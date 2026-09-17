"""The 3a7b9c1d2e4f backfill decides per workflow whether the interpreter can
read its graph. make test builds the schema with create_all and never runs the
migration chain, so this is the one check on that decision."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "3a7b9c1d2e4f_backfill_published_revisions.py"
)
_spec = importlib.util.spec_from_file_location("backfill_published_revisions", _MIGRATION)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_structural_reasons = _mod._structural_reasons

GOOD = {
    "nodes": [{"id": "t", "type": "trigger"}, {"id": "a", "type": "action"}],
    "edges": [{"from": "t", "to": "a"}],
}


def test_a_runnable_graph_has_no_reasons():
    assert _structural_reasons(GOOD) == []


def test_an_unsupported_node_type_is_named():
    graph = {"nodes": [{"id": "t", "type": "teleport"}], "edges": []}
    assert _structural_reasons(graph) == ["the interpreter cannot run node type(s): teleport"]


def test_a_dangling_edge_is_reported():
    graph = {"nodes": GOOD["nodes"], "edges": [{"from": "t", "to": "ghost"}]}
    assert _structural_reasons(graph) == ["an edge names 'ghost', which is not a node in this graph"]


def test_source_target_edges_are_not_our_shape():
    graph = {"nodes": GOOD["nodes"], "edges": [{"source": "t", "target": "a"}]}
    assert len(_structural_reasons(graph)) == 2


def test_non_object_and_empty_graphs():
    assert _structural_reasons([]) == ["the graph is not an object"]
    assert _structural_reasons({"nodes": []}) == ["the graph has no nodes"]
