"""
Schema tests for the Data Analytics metadata layer
(NEU-1811 DA-P0 baseline, refactored in DA-P1g for the tenant-catalog
+ workspace-overlay split).

Layered design (locked in DA-P1g):

  * ``da_connection`` — tenant-level Connection (credentials + lifecycle).
  * ``da_catalog_schema`` / ``da_catalog_table`` / ``da_catalog_column``
    — tenant-level **facts** about what's in the warehouse. Discovered
    by the connector-service sync job, **shared across every workspace
    in the tenant**, written once per re-sync. Facts include PII /
    restricted classification.
  * ``workspace_curation_da_table`` / ``workspace_curation_da_column``
    — workspace-level thin **opinions** layered on top of the catalog
    (is_included / archived / admin seed descriptions / AI descriptions
    / per-workspace LLM context fields). One row per
    (workspace_id, catalog_row_id).
  * ``metric`` / ``join_hint`` — workspace-scoped (opinions), unchanged.
  * ``description_version`` — append-only version history, unchanged.

Why the split exists (production-grade pattern — Looker / dbt / Hex /
Metabase): a column either IS or ISN'T PII; that's a fact about the
data, not about whose workspace is viewing it. AI descriptions vary by
business context per workspace. Facts at tenant, opinions per workspace.
See ``product-feature-roadmap/data-analytics/data-flow.md`` §4.8 and
the DA-P1g design discussion log.

Service ownership (locked as F4 in ``data-analytics/feature.md``):

  * ``connector-service`` owns CRUD on ``da_connection`` + writes to
    ``da_catalog_*`` during sync (discovery is a fact-gathering pass).
  * ``agent-platform`` owns writes to ``workspace_curation_da_*`` +
    ``metric`` / ``join_hint`` / ``description_version`` + all LLM
    calls (description generation, T2S, semantic-layer work).

This file pins the canonical schema shape:

  * presence of each table
  * column names + types + nullability
  * FK wiring with cascade / SET NULL behaviour
  * PII tags on credentials, samples, and replay inputs
  * uniqueness invariants per spec
  * append-only invariant on ``description_version`` (no ``updated_at``)

The test is schema-shape only — round-trip ORM behaviour (inserting rows
and reading them back) lands once the ORM wrappers are in place.

Design source: ``product-feature-roadmap/data-analytics/data-flow.md`` §4.8.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _table_exists(test_engine, table_name: str) -> bool:
    async with test_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).has_table(table_name)
        )


async def _columns(test_engine, table_name: str) -> dict:
    async with test_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: {
                c["name"]: c
                for c in sa.inspect(sync_conn).get_columns(table_name)
            }
        )


async def _foreign_keys(test_engine, table_name: str) -> list[dict]:
    async with test_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).get_foreign_keys(table_name)
        )


async def _indexes(test_engine, table_name: str) -> list[dict]:
    async with test_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).get_indexes(table_name)
        )


def _ondelete(fk: dict) -> str | None:
    return (fk.get("options") or {}).get("ondelete")


# ---------------------------------------------------------------------------
# Old workspace_metadata_* tables are GONE — replaced by the
# tenant-catalog + workspace-overlay split. The migration drops them.
# ---------------------------------------------------------------------------


class TestOldWorkspaceMetadataTablesRemoved:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "table_name",
        [
            "workspace_metadata_connection",
            "workspace_metadata_table",
            "workspace_metadata_column",
        ],
    )
    async def test_old_table_dropped(self, test_engine, table_name):
        assert not await _table_exists(test_engine, table_name), (
            f"{table_name} should be dropped — replaced by da_catalog_* "
            "(tenant) + workspace_curation_da_* (workspace) split."
        )


# ---------------------------------------------------------------------------
# da_connection was DROPPED in DA-U6 — DA warehouse connections now live on the
# unified `integration` table (DA-U3/U4). The table's shape assertions were
# removed with it; integration coverage lives in the connector-service +
# agent-platform suites. The catalog tables below keep their `da_connection_id`
# column name (now FK → integration; rename deferred, TD-DA-CATALOG-COLNAME).
# ---------------------------------------------------------------------------


class TestDAConnectionTableDropped:
    @pytest.mark.asyncio
    async def test_da_connection_table_is_gone(self, test_engine):
        assert not await _table_exists(test_engine, "da_connection"), (
            "da_connection must NOT exist — dropped in DA-U6 (unified onto "
            "the integration table)."
        )


# ---------------------------------------------------------------------------
# Table 2 — da_catalog_schema (DA-P1g — tenant-level schema fact)
# ---------------------------------------------------------------------------


class TestDACatalogSchemaTable:
    @pytest.mark.asyncio
    async def test_table_exists(self, test_engine):
        assert await _table_exists(test_engine, "da_catalog_schema")

    @pytest.mark.asyncio
    async def test_required_columns(self, test_engine):
        cols = await _columns(test_engine, "da_catalog_schema")
        expected = {
            "id",
            "da_connection_id",
            "schema_name",
            "schema_description",  # native comment from the warehouse
            "last_synced_at",
            "created_at",
            "updated_at",
        }
        missing = expected - cols.keys()
        assert not missing, (
            f"da_catalog_schema missing required columns: {missing}"
        )

    @pytest.mark.asyncio
    async def test_connection_fk_cascade(self, test_engine):
        # DA-U2: DA connections moved onto the unified `integration` table, so
        # the catalog's parent FK now targets `integration` (the column keeps
        # its legacy name `da_connection_id` — rename deferred,
        # TD-DA-CATALOG-COLNAME).
        fks = await _foreign_keys(test_engine, "da_catalog_schema")
        c_fk = [
            fk for fk in fks
            if "da_connection_id" in fk["constrained_columns"]
        ]
        assert c_fk and c_fk[0]["referred_table"] == "integration"
        assert _ondelete(c_fk[0]) == "CASCADE", (
            "Deleting the integration must remove its catalog facts — they're "
            "meaningless without the credential that produced them."
        )

    @pytest.mark.asyncio
    async def test_unique_per_connection_schema(self, test_engine):
        indexes = await _indexes(test_engine, "da_catalog_schema")
        unique = [
            idx
            for idx in indexes
            if idx.get("unique")
            and set(idx.get("column_names") or [])
            == {"da_connection_id", "schema_name"}
        ]
        assert unique, (
            "Expected unique (da_connection_id, schema_name) — schemas are "
            f"facts about the connection, no duplicates. Got {indexes!r}"
        )


# ---------------------------------------------------------------------------
# Table 3 — da_catalog_table (DA-P1g — tenant-level table fact)
# ---------------------------------------------------------------------------


class TestDACatalogTableTable:
    @pytest.mark.asyncio
    async def test_table_exists(self, test_engine):
        assert await _table_exists(test_engine, "da_catalog_table")

    @pytest.mark.asyncio
    async def test_required_columns(self, test_engine):
        cols = await _columns(test_engine, "da_catalog_table")
        expected = {
            "id",
            "da_catalog_schema_id",
            "table_name",
            "table_type",
            "native_comment",
            "row_count",
            "last_synced_at",
            "created_at",
            "updated_at",
        }
        missing = expected - cols.keys()
        assert not missing, (
            f"da_catalog_table missing required columns: {missing}"
        )

    @pytest.mark.asyncio
    async def test_no_workspace_or_curation_columns(self, test_engine):
        """Tenant catalog must NOT carry workspace-level opinions —
        per-workspace descriptions / trust metadata / curation state
        all belong on ``workspace_curation_da_table``. Mixing them here
        recreates the original anti-pattern.
        """
        cols = await _columns(test_engine, "da_catalog_table")
        forbidden = {
            "workspace_id",
            "is_included",
            "is_archived",
            # Single-field description + trust metadata (DA-P1l.1.0) is
            # workspace-only — catalog never carries it.
            "description",
            "description_origin",
            "ai_accepted_at",
            "ai_last_generated_at",
            # Legacy two-field model (pre-DA-P1l.1.0) also forbidden —
            # defense against a future migration reintroducing it.
            "admin_seed_description",
            "ai_generated_description",
            "table_logical_name",
            "last_enriched_at",
        }
        present = forbidden & cols.keys()
        assert not present, (
            f"da_catalog_table must not carry workspace opinions; found "
            f"{present}. These belong on workspace_curation_da_table."
        )

    @pytest.mark.asyncio
    async def test_schema_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "da_catalog_table")
        s_fk = [
            fk for fk in fks
            if "da_catalog_schema_id" in fk["constrained_columns"]
        ]
        assert s_fk and s_fk[0]["referred_table"] == "da_catalog_schema"
        assert _ondelete(s_fk[0]) == "CASCADE"

    @pytest.mark.asyncio
    async def test_unique_per_schema_table_name(self, test_engine):
        indexes = await _indexes(test_engine, "da_catalog_table")
        unique = [
            idx
            for idx in indexes
            if idx.get("unique")
            and set(idx.get("column_names") or [])
            == {"da_catalog_schema_id", "table_name"}
        ]
        assert unique, (
            "Expected unique (da_catalog_schema_id, table_name); "
            f"got {indexes!r}"
        )


# ---------------------------------------------------------------------------
# Table 4 — da_catalog_column (DA-P1g — tenant-level column fact + classification)
# ---------------------------------------------------------------------------


class TestDACatalogColumnTable:
    @pytest.mark.asyncio
    async def test_table_exists(self, test_engine):
        assert await _table_exists(test_engine, "da_catalog_column")

    @pytest.mark.asyncio
    async def test_required_columns(self, test_engine):
        cols = await _columns(test_engine, "da_catalog_column")
        expected = {
            "id",
            "da_catalog_table_id",
            # DDL-derived facts
            "column_name",
            "data_type",
            "nullable",
            "is_primary_key",
            "is_foreign_key",
            "foreign_key_to",
            "native_comment",
            "ordinal_position",
            # Compliance classification — fact about the data, not about
            # whose workspace is viewing it. Per SOC2 / HIPAA / GDPR
            # this must live at the catalog (tenant) level so all
            # workspaces see consistent PII handling.
            "is_pii",
            "is_restricted",
            # Lifecycle
            "last_synced_at",
            "created_at",
            "updated_at",
        }
        missing = expected - cols.keys()
        assert not missing, (
            f"da_catalog_column missing required columns: {missing}"
        )

    @pytest.mark.asyncio
    async def test_no_workspace_or_enrichment_columns(self, test_engine):
        """Tenant catalog must NOT carry workspace-level enrichment —
        descriptions / trust metadata / synonyms / sample values /
        valid_aggregations / column_logical_name all belong on
        ``workspace_curation_da_column``.
        """
        cols = await _columns(test_engine, "da_catalog_column")
        forbidden = {
            "workspace_id",
            "is_included",
            "is_archived",
            # Single-field description + trust metadata (DA-P1l.1.0).
            "description",
            "description_origin",
            "ai_accepted_at",
            "ai_last_generated_at",
            # Legacy two-field model (pre-DA-P1l.1.0) also forbidden —
            # defense against a future migration reintroducing it.
            "admin_seed_description",
            "ai_generated_description",
            "column_logical_name",
            "allow_sample_values",
            "sample_values",
            "cardinality_score",
            "statistical_profile",
            "synonyms",
            "unit",
            "format_hint",
            "valid_aggregations",
            "last_enriched_at",
        }
        present = forbidden & cols.keys()
        assert not present, (
            f"da_catalog_column must not carry workspace enrichment; "
            f"found {present}. These belong on workspace_curation_da_column."
        )

    @pytest.mark.asyncio
    async def test_table_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "da_catalog_column")
        t_fk = [
            fk for fk in fks
            if "da_catalog_table_id" in fk["constrained_columns"]
        ]
        assert t_fk and t_fk[0]["referred_table"] == "da_catalog_table"
        assert _ondelete(t_fk[0]) == "CASCADE"

    @pytest.mark.asyncio
    async def test_unique_per_table_column_name(self, test_engine):
        indexes = await _indexes(test_engine, "da_catalog_column")
        unique = [
            idx
            for idx in indexes
            if idx.get("unique")
            and set(idx.get("column_names") or [])
            == {"da_catalog_table_id", "column_name"}
        ]
        assert unique, (
            "Expected unique (da_catalog_table_id, column_name); "
            f"got {indexes!r}"
        )


# ---------------------------------------------------------------------------
# Table 5 — workspace_curation_da_table (DA-P1g — workspace opinion overlay)
# ---------------------------------------------------------------------------


class TestWorkspaceCurationDATableTable:
    @pytest.mark.asyncio
    async def test_table_exists(self, test_engine):
        assert await _table_exists(test_engine, "workspace_curation_da_table")

    @pytest.mark.asyncio
    async def test_required_columns(self, test_engine):
        """DA-P1l.1.0 collapses the two-field model (admin_seed_description
        + ai_generated_description) into a single ``description`` field
        with trust metadata (origin / ai_accepted_at / ai_last_generated_at).
        See ``description-generation.md`` §M1, M2 for the locked design.
        """
        cols = await _columns(test_engine, "workspace_curation_da_table")
        expected = {
            "id",
            "workspace_id",
            "da_catalog_table_id",
            # Per-workspace opinion / context — single description field
            "table_logical_name",
            "description",
            "synonyms",
            # Trust metadata (M2) — origin + HITL accept gate + last-gen stamp
            "description_origin",
            "ai_accepted_at",
            "ai_last_generated_at",
            # Curation
            "is_included",
            "is_archived",
            "last_enriched_at",
            "created_at",
            "updated_at",
        }
        missing = expected - cols.keys()
        assert not missing, (
            f"workspace_curation_da_table missing required columns: {missing}"
        )

    @pytest.mark.asyncio
    async def test_two_field_description_model_removed(self, test_engine):
        """DA-P1l.1.0 — the old two-field description model
        (admin_seed_description + ai_generated_description) is replaced by a
        single ``description`` field plus trust metadata. Both old columns
        must be gone or the migration didn't run.
        """
        cols = await _columns(test_engine, "workspace_curation_da_table")
        forbidden = {"admin_seed_description", "ai_generated_description"}
        present = forbidden & cols.keys()
        assert not present, (
            f"workspace_curation_da_table still has legacy two-field "
            f"description columns: {present}. Expected single ``description`` "
            "field after DA-P1l.1.0 migration."
        )

    @pytest.mark.asyncio
    async def test_description_origin_default_is_human(self, test_engine):
        """Newly-inserted rows default to origin='human' — a fresh row is
        the admin's substrate to type into; AI flips it on generate."""
        cols = await _columns(test_engine, "workspace_curation_da_table")
        col = cols.get("description_origin")
        assert col is not None
        default = (col.get("default") or "").lower()
        assert "human" in default, (
            f"description_origin default must encode 'human'; got {col.get('default')!r}"
        )
        assert col["nullable"] is False, (
            "description_origin is NOT NULL — every row has a defined origin."
        )

    @pytest.mark.asyncio
    async def test_no_fact_columns(self, test_engine):
        """Workspace overlay must NOT duplicate tenant catalog facts —
        ``table_name``, ``table_type``, ``native_comment``, ``row_count``
        live on ``da_catalog_table`` and are joined for display.
        """
        cols = await _columns(test_engine, "workspace_curation_da_table")
        forbidden = {
            "table_name",
            "table_type",
            "native_comment",
            "row_count",
            "last_synced_at",
        }
        present = forbidden & cols.keys()
        assert not present, (
            f"workspace_curation_da_table must not duplicate catalog facts; "
            f"found {present}."
        )

    @pytest.mark.asyncio
    async def test_workspace_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "workspace_curation_da_table")
        ws_fk = [fk for fk in fks if "workspace_id" in fk["constrained_columns"]]
        assert ws_fk and ws_fk[0]["referred_table"] == "workspace"
        assert _ondelete(ws_fk[0]) == "CASCADE"

    @pytest.mark.asyncio
    async def test_catalog_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "workspace_curation_da_table")
        c_fk = [
            fk for fk in fks
            if "da_catalog_table_id" in fk["constrained_columns"]
        ]
        assert c_fk and c_fk[0]["referred_table"] == "da_catalog_table"
        assert _ondelete(c_fk[0]) == "CASCADE", (
            "Catalog row removal (e.g. table dropped from the warehouse) "
            "must cascade to clean up workspace overlays — leaving them "
            "would create dangling references."
        )

    @pytest.mark.asyncio
    async def test_unique_per_workspace_catalog_table(self, test_engine):
        indexes = await _indexes(test_engine, "workspace_curation_da_table")
        unique = [
            idx
            for idx in indexes
            if idx.get("unique")
            and set(idx.get("column_names") or [])
            == {"workspace_id", "da_catalog_table_id"}
        ]
        assert unique, (
            "Expected unique (workspace_id, da_catalog_table_id) — one "
            f"overlay row per workspace per catalog table. Got {indexes!r}"
        )


# ---------------------------------------------------------------------------
# Table 6 — workspace_curation_da_column (DA-P1g — workspace overlay)
# ---------------------------------------------------------------------------


class TestWorkspaceCurationDAColumnTable:
    @pytest.mark.asyncio
    async def test_table_exists(self, test_engine):
        assert await _table_exists(test_engine, "workspace_curation_da_column")

    @pytest.mark.asyncio
    async def test_required_columns(self, test_engine):
        """DA-P1l.1.0 collapses the two-field model into a single
        ``description`` field with trust metadata, and removes the
        per-column ``allow_sample_values`` toggle (lifted to workspace-level
        in ``workspace_da_settings`` per M11).
        """
        cols = await _columns(test_engine, "workspace_curation_da_column")
        expected = {
            "id",
            "workspace_id",
            "da_catalog_column_id",
            # Per-workspace LLM context — the AI describes the same column
            # differently for different teams (sales workspace ≠ finance
            # workspace), so this lives per-workspace, not on the catalog.
            "column_logical_name",
            "description",
            "synonyms",
            "unit",
            "format_hint",
            "valid_aggregations",
            # Trust metadata (M2)
            "description_origin",
            "ai_accepted_at",
            "ai_last_generated_at",
            # Phase-2 enrichment (sample values + stats; sampling toggle
            # itself is now workspace-level in workspace_da_settings)
            "sample_values",
            "cardinality_score",
            "statistical_profile",
            # Upgrade-only restricted override — a workspace can mark a
            # column as additionally restricted, but it CANNOT downgrade
            # the catalog's is_restricted or is_pii classification. App
            # code enforces this; the column is a bool default false.
            "is_restricted_override",
            # Curation
            "is_included",
            "is_archived",
            "last_enriched_at",
            "created_at",
            "updated_at",
        }
        missing = expected - cols.keys()
        assert not missing, (
            f"workspace_curation_da_column missing required columns: {missing}"
        )

    @pytest.mark.asyncio
    async def test_two_field_description_model_removed(self, test_engine):
        """DA-P1l.1.0 — same collapse as workspace_curation_da_table.
        Single ``description`` field + trust metadata; legacy two-field
        columns gone.
        """
        cols = await _columns(test_engine, "workspace_curation_da_column")
        forbidden = {"admin_seed_description", "ai_generated_description"}
        present = forbidden & cols.keys()
        assert not present, (
            f"workspace_curation_da_column still has legacy two-field "
            f"description columns: {present}."
        )

    @pytest.mark.asyncio
    async def test_per_column_allow_sample_values_removed(self, test_engine):
        """DA-P1l.1.0 — per-column ``allow_sample_values`` toggle lifted to
        workspace-level (workspace_da_settings.da_include_sample_values).
        Per M11 / discussion log: per-column was redundant because
        catalog flags (PII / Restricted) hard-block, is_included controls
        whether the column is curated at all, and the remaining case (a
        non-PII curated column the admin wants sample-excluded) is rare
        enough to handle via tagging rather than its own toggle.
        """
        cols = await _columns(test_engine, "workspace_curation_da_column")
        assert "allow_sample_values" not in cols, (
            "workspace_curation_da_column.allow_sample_values must be "
            "dropped — sampling is workspace-level now."
        )

    @pytest.mark.asyncio
    async def test_description_origin_default_is_human(self, test_engine):
        cols = await _columns(test_engine, "workspace_curation_da_column")
        col = cols.get("description_origin")
        assert col is not None
        default = (col.get("default") or "").lower()
        assert "human" in default, (
            f"description_origin default must encode 'human'; got {col.get('default')!r}"
        )
        assert col["nullable"] is False

    @pytest.mark.asyncio
    async def test_no_fact_or_classification_columns(self, test_engine):
        """Workspace overlay must NOT duplicate facts or classifications.
        ``is_pii`` lives ONLY at the catalog — a workspace cannot
        disagree about PII status; that's a compliance landmine.
        Restrictions can be UPGRADED via is_restricted_override but
        never set as the authoritative restricted flag.
        """
        cols = await _columns(test_engine, "workspace_curation_da_column")
        forbidden = {
            "column_name",
            "data_type",
            "nullable",
            "is_primary_key",
            "is_foreign_key",
            "foreign_key_to",
            "native_comment",
            "ordinal_position",
            "last_synced_at",
            # PII has NO override at workspace — strictly catalog-owned
            "is_pii",
            "is_pii_override",
            # is_restricted is catalog-owned; workspaces use
            # is_restricted_override (upgrade-only) instead.
            "is_restricted",
        }
        present = forbidden & cols.keys()
        assert not present, (
            f"workspace_curation_da_column must not carry facts / "
            f"classifications; found {present}. Compliance landmine: "
            f"workspaces disagreeing about PII status."
        )

    @pytest.mark.asyncio
    async def test_sample_values_is_pii_tagged(self, test_engine):
        """``sample_values`` may hold real customer data (email, addresses)
        pulled from the source. Tag for the C6 anonymization runner.
        """
        cols = await _columns(test_engine, "workspace_curation_da_column")
        comment = cols["sample_values"].get("comment") or ""
        assert "pii:freetext" in comment, (
            "workspace_curation_da_column.sample_values must be tagged "
            "'pii:freetext' (real values may contain customer PII)."
        )

    @pytest.mark.asyncio
    async def test_workspace_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "workspace_curation_da_column")
        ws_fk = [fk for fk in fks if "workspace_id" in fk["constrained_columns"]]
        assert ws_fk and ws_fk[0]["referred_table"] == "workspace"
        assert _ondelete(ws_fk[0]) == "CASCADE"

    @pytest.mark.asyncio
    async def test_catalog_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "workspace_curation_da_column")
        c_fk = [
            fk for fk in fks
            if "da_catalog_column_id" in fk["constrained_columns"]
        ]
        assert c_fk and c_fk[0]["referred_table"] == "da_catalog_column"
        assert _ondelete(c_fk[0]) == "CASCADE"

    @pytest.mark.asyncio
    async def test_unique_per_workspace_catalog_column(self, test_engine):
        indexes = await _indexes(test_engine, "workspace_curation_da_column")
        unique = [
            idx
            for idx in indexes
            if idx.get("unique")
            and set(idx.get("column_names") or [])
            == {"workspace_id", "da_catalog_column_id"}
        ]
        assert unique, (
            "Expected unique (workspace_id, da_catalog_column_id); "
            f"got {indexes!r}"
        )


# ---------------------------------------------------------------------------
# Table 7 — metric (Entity 5 in §4.8) — unchanged in DA-P1g
# ---------------------------------------------------------------------------


class TestMetricTable:
    @pytest.mark.asyncio
    async def test_table_exists(self, test_engine):
        assert await _table_exists(test_engine, "metric")

    @pytest.mark.asyncio
    async def test_required_columns(self, test_engine):
        cols = await _columns(test_engine, "metric")
        expected = {
            "id",
            "workspace_id",
            "name",
            "description",
            "sql_expression",
            "filters",
            "applicable_tables",
            "valid_dimensions",
            "source",
            "accepted",
            "created_by",
            "updated_by",
            "last_used_at",
            "is_archived",
            "created_at",
            "updated_at",
        }
        missing = expected - cols.keys()
        assert not missing, f"metric missing required columns: {missing}"

    @pytest.mark.asyncio
    async def test_workspace_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "metric")
        ws_fk = [fk for fk in fks if "workspace_id" in fk["constrained_columns"]]
        assert ws_fk and ws_fk[0]["referred_table"] == "workspace"
        assert _ondelete(ws_fk[0]) == "CASCADE"

    @pytest.mark.asyncio
    async def test_actor_fks_set_null(self, test_engine):
        fks = await _foreign_keys(test_engine, "metric")
        for col in ("created_by", "updated_by"):
            actor_fk = [fk for fk in fks if col in fk["constrained_columns"]]
            assert actor_fk, f"metric.{col} should FK to user(id)"
            assert actor_fk[0]["referred_table"] == "user"
            assert _ondelete(actor_fk[0]) == "SET NULL", (
                f"metric.{col} must be ON DELETE SET NULL for GDPR-safe "
                "anonymization."
            )

    @pytest.mark.asyncio
    async def test_active_name_unique_per_workspace(self, test_engine):
        indexes = await _indexes(test_engine, "metric")
        unique = [
            idx
            for idx in indexes
            if idx.get("unique")
            and set(idx.get("column_names") or []) == {"workspace_id", "name"}
        ]
        assert unique, (
            "Expected unique index over (workspace_id, name) on metric; "
            f"got {indexes!r}"
        )
        partial = [
            idx
            for idx in unique
            if (idx.get("dialect_options") or {}).get("postgresql_where") is not None
            or "is_archived" in str(idx)
        ]
        assert partial, (
            "metric (workspace_id, name) unique index must be partial "
            "(WHERE is_archived = false) so archived metrics don't block "
            f"reuse of their name. Got {unique!r}"
        )


# ---------------------------------------------------------------------------
# Table 8 — join_hint — workspace-scoped; FKs repoint to
# workspace_curation_da_table in DA-P1g.
# ---------------------------------------------------------------------------


class TestJoinHintTable:
    @pytest.mark.asyncio
    async def test_table_exists(self, test_engine):
        assert await _table_exists(test_engine, "join_hint")

    @pytest.mark.asyncio
    async def test_required_columns(self, test_engine):
        cols = await _columns(test_engine, "join_hint")
        expected = {
            "id",
            "workspace_id",
            "left_table_id",
            "left_columns",
            "right_table_id",
            "right_columns",
            "join_type",
            "semantic_description",
            "source",
            "accepted",
            "created_by",
            "is_archived",
            "created_at",
        }
        missing = expected - cols.keys()
        assert not missing, f"join_hint missing required columns: {missing}"

    @pytest.mark.asyncio
    async def test_workspace_fk_cascade(self, test_engine):
        fks = await _foreign_keys(test_engine, "join_hint")
        ws_fk = [fk for fk in fks if "workspace_id" in fk["constrained_columns"]]
        assert ws_fk and ws_fk[0]["referred_table"] == "workspace"
        assert _ondelete(ws_fk[0]) == "CASCADE"

    @pytest.mark.asyncio
    async def test_left_right_table_fks_to_workspace_curation(self, test_engine):
        """Join hints are workspace opinions about which tables join
        usefully — so they reference the workspace's curated set,
        ``workspace_curation_da_table``, NOT the tenant catalog.
        Cascade is required: archive a workspace's curation row → the
        hints that reference it become meaningless.
        """
        fks = await _foreign_keys(test_engine, "join_hint")
        for col in ("left_table_id", "right_table_id"):
            t_fk = [fk for fk in fks if col in fk["constrained_columns"]]
            assert t_fk, (
                f"join_hint.{col} should FK to workspace_curation_da_table(id)"
            )
            assert t_fk[0]["referred_table"] == "workspace_curation_da_table", (
                f"join_hint.{col} must reference workspace_curation_da_table, "
                f"not {t_fk[0]['referred_table']}. Hints are workspace "
                "opinions, not tenant facts."
            )
            assert _ondelete(t_fk[0]) == "CASCADE", (
                f"join_hint.{col} must cascade — losing the curated table "
                "invalidates the hint."
            )

    @pytest.mark.asyncio
    async def test_created_by_fk_set_null(self, test_engine):
        fks = await _foreign_keys(test_engine, "join_hint")
        cb_fk = [fk for fk in fks if "created_by" in fk["constrained_columns"]]
        assert cb_fk and cb_fk[0]["referred_table"] == "user"
        assert _ondelete(cb_fk[0]) == "SET NULL"


# ---------------------------------------------------------------------------
# Table 9 — workspace_da_settings (DA-P1l.1.0 — workspace-level DA settings).
#
# Companion to the description-generation work: holds workspace-level
# toggles that govern AI description gen behaviour (see M11 in
# ``product-feature-roadmap/data-analytics/description-generation.md``).
# Today it carries two fields (sample-value inclusion + PII redaction);
# future DA workspace-level settings (default model preference,
# cost cap, etc.) will land here rather than as JSONB sprawl on the
# workspace row.
# ---------------------------------------------------------------------------


class TestWorkspaceDASettingsTable:
    @pytest.mark.asyncio
    async def test_table_exists(self, test_engine):
        assert await _table_exists(test_engine, "workspace_da_settings"), (
            "workspace_da_settings must exist — holds workspace-level DA "
            "settings (M11)."
        )

    @pytest.mark.asyncio
    async def test_required_columns(self, test_engine):
        cols = await _columns(test_engine, "workspace_da_settings")
        expected = {
            "workspace_id",                # PK + FK to workspace
            "da_include_sample_values",    # M11 toggle 1
            "da_pii_redaction_enabled",    # M11 toggle 2
            "created_at",
            "updated_at",
        }
        missing = expected - cols.keys()
        assert not missing, (
            f"workspace_da_settings missing required columns: {missing}"
        )

    @pytest.mark.asyncio
    async def test_workspace_id_is_primary_key(self, test_engine):
        """One settings row per workspace — workspace_id is both the PK
        and the FK to ``workspace(id)``. Avoids needing a synthetic id.
        """
        async with test_engine.connect() as conn:
            pk = await conn.run_sync(
                lambda sync_conn: sa.inspect(sync_conn).get_pk_constraint(
                    "workspace_da_settings"
                )
            )
        assert pk["constrained_columns"] == ["workspace_id"], (
            f"workspace_da_settings PK must be (workspace_id); got {pk}"
        )

    @pytest.mark.asyncio
    async def test_workspace_fk_cascade(self, test_engine):
        """Workspace deletion cascades to settings — no orphan rows."""
        fks = await _foreign_keys(test_engine, "workspace_da_settings")
        ws_fk = [
            fk for fk in fks if "workspace_id" in fk["constrained_columns"]
        ]
        assert ws_fk and ws_fk[0]["referred_table"] == "workspace"
        assert _ondelete(ws_fk[0]) == "CASCADE", (
            "Deleting a workspace must cascade to its DA settings row."
        )

    @pytest.mark.asyncio
    async def test_defaults_are_safe(self, test_engine):
        """Both toggles default to TRUE — fail-safe posture per M11.
        Sample values flow (better descriptions) and PII redaction is on
        (no raw values reach the LLM provider unless admin explicitly
        opts out). Admin trades quality vs trust deliberately.
        """
        cols = await _columns(test_engine, "workspace_da_settings")
        for name in ("da_include_sample_values", "da_pii_redaction_enabled"):
            col = cols.get(name)
            assert col is not None
            assert col["nullable"] is False, f"{name} must be NOT NULL"
            default = str(col.get("default") or "").lower()
            assert "true" in default, (
                f"{name} default must be TRUE (fail-safe); got {col.get('default')!r}"
            )


# ---------------------------------------------------------------------------
# Table 10 — description_version (Entity 8 in §4.8) — append-only history.
# parent_id is a polymorphic ref via the ``scope`` enum; in DA-P1g it
# still points at the workspace-curation overlays (since descriptions are
# per-workspace), so no structural FK change is needed.
# ---------------------------------------------------------------------------


class TestDescriptionVersionTable:
    @pytest.mark.asyncio
    async def test_table_exists(self, test_engine):
        assert await _table_exists(test_engine, "description_version")

    @pytest.mark.asyncio
    async def test_required_columns(self, test_engine):
        cols = await _columns(test_engine, "description_version")
        expected = {
            "id",
            "scope",
            "parent_id",
            "version_number",
            "source",
            "content",
            "generated_at",
            "generated_by",
            "inputs_snapshot",
        }
        missing = expected - cols.keys()
        assert not missing, (
            f"description_version missing required columns: {missing}"
        )

    @pytest.mark.asyncio
    async def test_no_updated_at_column(self, test_engine):
        """description_version is append-only per §4.5: each correction is
        a new version, not an in-place edit. An ``updated_at`` column
        would signal mutability and violate the design contract.
        """
        cols = await _columns(test_engine, "description_version")
        assert "updated_at" not in cols, (
            "description_version is append-only (§4.5); no updated_at column."
        )

    @pytest.mark.asyncio
    async def test_inputs_snapshot_is_pii_tagged(self, test_engine):
        cols = await _columns(test_engine, "description_version")
        comment = cols["inputs_snapshot"].get("comment") or ""
        assert "pii:freetext" in comment, (
            "description_version.inputs_snapshot must be tagged 'pii:freetext' "
            "(snapshot may contain sample_values with customer PII)."
        )

    @pytest.mark.asyncio
    async def test_generated_by_fk_set_null(self, test_engine):
        fks = await _foreign_keys(test_engine, "description_version")
        gb_fk = [fk for fk in fks if "generated_by" in fk["constrained_columns"]]
        assert gb_fk, "description_version.generated_by should FK to user(id)"
        assert gb_fk[0]["referred_table"] == "user"
        assert _ondelete(gb_fk[0]) == "SET NULL"

    @pytest.mark.asyncio
    async def test_version_number_uniqueness(self, test_engine):
        indexes = await _indexes(test_engine, "description_version")
        unique = [
            idx
            for idx in indexes
            if idx.get("unique")
            and set(idx.get("column_names") or [])
            == {"scope", "parent_id", "version_number"}
        ]
        assert unique, (
            "Expected unique (scope, parent_id, version_number) on "
            f"description_version; got {indexes!r}"
        )


class TestCatalogPrunedAt:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "table_name",
        ["da_catalog_schema", "da_catalog_table", "da_catalog_column"],
    )
    async def test_pruned_at_is_nullable_timestamp(self, test_engine, table_name):
        """NC-739 H5: sync tombstones rows instead of deleting them."""
        col = (await _columns(test_engine, table_name))["pruned_at"]
        assert col["nullable"] is True
        assert "TIMESTAMP" in str(col["type"]).upper()
