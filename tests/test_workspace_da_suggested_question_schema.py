"""NC-570 — workspace_da_suggested_question schema.

The chat empty state used to compose its DA cards from three string templates
on the request path. Generation moves into the enrichment run, written by a
language model against the same evidence, and this table is where the result
is stored so the chat home screen goes back to being a read.

The checks below lock down the three properties the serve boundary depends on:

  * The catalog identity travels WITH the question — table, schema and the
    column ids the sentence names — so provenance is never recovered by
    reading names back out of the finished prose.
  * ``da_catalog_column_ids`` is NOT NULL. The NC-568 permission filter fails
    closed on an empty column list, so a question that records no column can
    never be shown to a member subject to column grants. Allowing NULL here
    would put rows in the table that the filter can only ever refuse.
  * ``shape`` exists and is NOT NULL. It is the question's kind, it carries
    the icon the client renders, and the serve boundary groups the pool by it
    so one screen shows four kinds of question rather than one sentence four
    times. It is load bearing, so it is not nullable.

Pure metadata + ORM shape checks (no DB); migration to metadata parity is
exercised by the suite's apply.
"""

from __future__ import annotations

from neutrino_database.models import orm, tables


def test_table_registered():
    assert "workspace_da_suggested_question" in tables.metadata.tables


def test_columns_and_primary_key():
    t = tables.workspace_da_suggested_question
    assert {c.name for c in t.columns} == {
        "id",
        "workspace_id",
        "tenant_id",
        "da_connection_id",
        "da_catalog_schema_id",
        "da_catalog_table_id",
        "da_catalog_column_ids",
        "question_text",
        "shape",
        "origin",
        "generated_by_run_id",
        "generated_at",
        "created_at",
        "updated_at",
    }
    assert t.c.id.primary_key


def test_question_identity_is_not_nullable():
    """Everything the serve boundary needs must be present on every row."""
    t = tables.workspace_da_suggested_question
    for name in (
        "workspace_id",
        "tenant_id",
        "da_connection_id",
        "da_catalog_schema_id",
        "da_catalog_table_id",
        "da_catalog_column_ids",
        "question_text",
        "shape",
        "origin",
    ):
        assert not t.c[name].nullable, f"{name} must be NOT NULL"


def test_run_provenance_is_optional():
    """A pruned enrichment run must not take the pool with it."""
    t = tables.workspace_da_suggested_question
    assert t.c.generated_by_run_id.nullable
    fk = next(iter(t.c.generated_by_run_id.foreign_keys))
    assert fk.column.table.name == "da_enrichment_run"
    assert fk.ondelete == "SET NULL"


def test_catalog_sources_cascade():
    """A removed source drops its questions. A question about a table that no
    longer exists is the exact "names something that isn't there" failure the
    feature exists to remove."""
    t = tables.workspace_da_suggested_question
    expected = {
        "workspace_id": "workspace",
        "tenant_id": "tenant",
        "da_connection_id": "integration",
        "da_catalog_schema_id": "da_catalog_schema",
        "da_catalog_table_id": "da_catalog_table",
    }
    for column_name, parent in expected.items():
        fk = next(iter(t.c[column_name].foreign_keys))
        assert fk.column.table.name == parent
        assert fk.ondelete == "CASCADE", f"{column_name} must cascade"


def test_origin_follows_the_description_origin_house_style():
    """A short string with a CHECK, matching ``description_origin`` on the
    workspace_curation_da_* overlays, so a new value is a constraint change
    and not a type migration."""
    t = tables.workspace_da_suggested_question
    check = next(
        c for c in t.constraints if getattr(c, "name", None) == "ck_wdsq_origin"
    )
    sqltext = str(check.sqltext)
    assert "template" in sqltext
    assert "ai" in sqltext


def test_indexes_cover_the_serve_and_write_lookups():
    t = tables.workspace_da_suggested_question
    by_name = {i.name: [c.name for c in i.columns] for i in t.indexes}
    # The serve path: this workspace's pool, narrowed to the connections it
    # may currently query.
    assert by_name["ix_wdsq_workspace_connection"] == [
        "workspace_id",
        "da_connection_id",
    ]
    # The write path: delete then insert per table.
    assert by_name["ix_wdsq_table"] == ["da_catalog_table_id"]


def test_orm_wrapper_is_bound_to_the_table():
    assert (
        orm.WorkspaceDASuggestedQuestion.__table__
        is tables.workspace_da_suggested_question
    )
