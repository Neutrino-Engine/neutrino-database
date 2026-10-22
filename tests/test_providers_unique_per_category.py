"""NC-734 — the providers unique key includes ``provider_category``.

Optional workspace embedding providers live in the ``providers`` table next
to LLM providers (``provider_category = 'embedding'``). The unique key must be
scoped per category, otherwise an embedding provider named "OpenAI" collides
with an LLM provider named "OpenAI" in the same workspace.

These are metadata + migration checks: the shared test database is long-lived
and ``create_all`` never alters an existing table, so asserting against a live
constraint would test whatever schema the database happened to be created with.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import Index

from neutrino_database.models.credentials.api_keys import providers
from neutrino_database.models.enums import ProviderCategory

_MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "e7f1a3c5b9d2_providers_unique_per_category.py"
)


def _unique_keys() -> dict[str, tuple[str, ...]]:
    return {
        ix.name: tuple(col.name for col in ix.columns)
        for ix in providers.indexes
        if isinstance(ix, Index) and ix.unique
    }


def test_unique_key_is_scoped_by_category():
    keys = _unique_keys()
    assert keys.get("ux_provider_category_name") == (
        "workspace_id",
        "provider_category",
        "service_type",
        "display_name",
    )


def test_old_cross_category_key_is_gone():
    assert "ux_llm_provider" not in _unique_keys()


def test_soft_deleted_rows_stay_exempt():
    """NC-767's partial index (soft-deleted rows don't block re-adding) is kept."""
    index = next(ix for ix in providers.indexes if ix.name == "ux_provider_category_name")
    where = index.dialect_options["postgresql"]["where"]
    assert "is_deleted = false" in str(where)


def test_embedding_category_exists():
    assert ProviderCategory.EMBEDDING.value == "embedding"


def test_migration_chains_from_previous_head():
    spec = importlib.util.spec_from_file_location("nc734_migration", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "e7f1a3c5b9d2"
    assert module.down_revision == "7e3b9c1d5a20"
