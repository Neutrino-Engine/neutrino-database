"""DA-U1 — integration_da_config schema.

The DA capability's per-connection config sidecar for the unified `integration`
table. Keeps `integration` generic: DA-specific facts (the tenant schema
allowlist) live here, keyed 1:1 to the integration. Mirrors the shape a future
`integration_es_config` will take for ES. Pure metadata + ORM shape checks (no
DB) — migration↔metadata parity is exercised by the suite's apply.
"""

from __future__ import annotations

from neutrino_database.models import tables


def test_table_registered():
    assert "integration_da_config" in tables.metadata.tables


def test_columns_and_primary_key():
    t = tables.integration_da_config
    assert {c.name for c in t.columns} == {
        "integration_id",
        "allowed_schemas",
        "row_scoped",
        "created_at",
        "updated_at",
    }
    # 1:1 with the integration — the integration_id IS the primary key.
    assert t.c.integration_id.primary_key


def test_integration_id_fk_cascades():
    t = tables.integration_da_config
    fks = list(t.c.integration_id.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "integration"
    # Deleting the integration removes its DA config — no orphan sidecar.
    assert fks[0].ondelete == "CASCADE"


def test_allowed_schemas_is_nullable():
    # NULL = unrestricted (every schema visible/queryable); list = allowlist.
    # Same semantics as the legacy da_connection.allowed_schemas it replaces.
    assert tables.integration_da_config.c.allowed_schemas.nullable is True


def test_row_scoped_defaults_off():
    # Existing connections keep running as the connection's own login.
    col = tables.integration_da_config.c.row_scoped
    assert col.nullable is False
    assert "false" in str(col.server_default.arg)


def test_orm_maps_to_table():
    from neutrino_database.models.orm import IntegrationDAConfig

    assert IntegrationDAConfig.__table__ is tables.integration_da_config
