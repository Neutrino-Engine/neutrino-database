"""DashboardWidgetDataBinding — one widget, one query, either language.

A widget is a query re-executed on every dashboard load, and originally that
query could only be SQL. That quietly made dashboards a relational-only
surface: a chart over a Mongo collection could be produced in chat but never
kept, purely because of where its data lived. Nothing about the user's intent
changes between the two, so the binding carries either shape and the executor
is chosen from the shape.

These tests pin the discriminator, because "which executor runs this widget" is
decided entirely by which fields are populated.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from neutrino_database.models.da_schemas import DashboardWidgetDataBinding
from neutrino_database.models.enums import (
    DATA_BINDING_FORMS,
    DataBindingKindEnum,
)


def _relational(**over):
    return {
        "connection_id": uuid.uuid4(),
        "kind": DataBindingKindEnum.RELATIONAL,
        "schema_name": "sales",
        "sql": "SELECT region, revenue FROM sales.by_region",
        **over,
    }


def _document(**over):
    return {
        "connection_id": uuid.uuid4(),
        "kind": DataBindingKindEnum.DOCUMENT,
        "database": "analytics",
        "collection": "customers",
        "pipeline": [{"$group": {"_id": "$tier", "n": {"$sum": 1}}}],
        **over,
    }


class TestBothFormsAreValid:
    def test_relational_binding(self):
        b = DashboardWidgetDataBinding(**_relational())
        assert b.resolved_kind is DataBindingKindEnum.RELATIONAL
        assert b.execute_route == "execute_query"
        assert b.sql.startswith("SELECT")

    def test_document_binding(self):
        b = DashboardWidgetDataBinding(**_document())
        assert b.resolved_kind is DataBindingKindEnum.DOCUMENT
        assert b.execute_route == "execute_pipeline"
        assert b.collection == "customers"
        assert b.pipeline[0]["$group"]["_id"] == "$tier"

    def test_a_pipeline_survives_verbatim(self):
        """Stored and forwarded opaquely — connector-service's mongo_guard is
        what rejects a write stage, exactly as for a pipeline sent from chat.
        Nothing here may normalise or reshape it."""
        pipeline = [
            {"$match": {"tier": "gold"}},
            {"$group": {"_id": "$region", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
            {"$limit": 20},
        ]
        b = DashboardWidgetDataBinding(**_document(pipeline=pipeline))
        assert b.pipeline == pipeline

    def test_an_empty_pipeline_is_still_a_document_binding(self):
        """`pipeline: []` is a real query (every document, no stages) and must
        not be mistaken for "no pipeline" — the discriminator is presence, not
        truthiness."""
        b = DashboardWidgetDataBinding(**_document(pipeline=[]))
        assert b.resolved_kind is DataBindingKindEnum.DOCUMENT
        assert b.execute_route == "execute_pipeline"


class TestExactlyOneForm:
    """A binding carrying both queries is a widget whose behaviour depends on
    which branch is checked first. Unconstructible beats deterministic."""

    def test_both_forms_at_once_is_rejected(self):
        with pytest.raises(ValidationError, match="runs one query"):
            DashboardWidgetDataBinding(
                **_relational(kind=None, pipeline=[{"$match": {}}])
            )

    def test_neither_form_is_rejected(self):
        with pytest.raises(ValidationError, match="has no query"):
            DashboardWidgetDataBinding(connection_id=uuid.uuid4())

    def test_a_connection_alone_is_not_a_query(self):
        """Guards the specific regression of loosening sql to Optional: before
        the document form existed, sql was required, so this was impossible."""
        with pytest.raises(ValidationError):
            DashboardWidgetDataBinding(
                connection_id=uuid.uuid4(), schema_name="sales"
            )


class TestEachFormIsComplete:
    def test_sql_without_schema_name_is_rejected(self):
        with pytest.raises(ValidationError, match="requires schema_name"):
            DashboardWidgetDataBinding(**_relational(schema_name=None))

    @pytest.mark.parametrize("missing", ["database", "collection"])
    def test_a_pipeline_needs_its_target(self, missing):
        """A pipeline with no collection to run against would reach
        connector-service and fail there, per widget, on every load."""
        with pytest.raises(ValidationError, match=f"requires.*{missing}"):
            DashboardWidgetDataBinding(**_document(**{missing: None}))


class TestRoundTrip:
    def test_a_document_binding_survives_the_jsonb_round_trip(self):
        """data_binding is a JSONB column, so the model is reconstructed from
        whatever was dumped. Nothing may be lost in either direction."""
        original = DashboardWidgetDataBinding(**_document())
        restored = DashboardWidgetDataBinding.model_validate(
            original.model_dump(mode="json")
        )
        assert restored.resolved_kind is DataBindingKindEnum.DOCUMENT
        assert restored.pipeline == original.pipeline
        assert restored.database == original.database
        assert restored.collection == original.collection

    def test_a_relational_binding_survives_the_round_trip(self):
        original = DashboardWidgetDataBinding(**_relational())
        restored = DashboardWidgetDataBinding.model_validate(
            original.model_dump(mode="json")
        )
        assert restored.resolved_kind is DataBindingKindEnum.RELATIONAL
        assert restored.sql == original.sql


class TestLegacyBindingsStillWork:
    """Widgets written before the tag existed have no `kind`. They are all
    relational, because that was the only form there was."""

    def test_an_untagged_sql_binding_is_inferred_relational(self):
        b = DashboardWidgetDataBinding(**_relational(kind=None))
        assert b.kind is DataBindingKindEnum.RELATIONAL
        assert b.execute_route == "execute_query"

    def test_inference_does_not_mask_an_incomplete_legacy_binding(self):
        with pytest.raises(ValidationError):
            DashboardWidgetDataBinding(
                connection_id=uuid.uuid4(), kind=None, schema_name="sales"
            )


class TestAddingADatasourceIsOneTableEntry:
    """The scaling property, asserted rather than asserted-in-a-comment.

    A new structured source — Iceberg, Trino, whatever — must not require
    editing this model, the validator, or any consumer that dispatches on the
    tag. If someone replaces the tag with shape-sniffing, or hardcodes the two
    current forms in a branch, these fail.
    """

    def test_the_model_hardcodes_no_form(self):
        """Every form the validator enforces comes from the table, so a member
        added there is enforced with no code change here."""
        import inspect

        from neutrino_database.models import da_schemas

        source = inspect.getsource(da_schemas.DashboardWidgetDataBinding)
        validator = source[source.index("_complete_for_its_kind"):]
        for leaked in ("RELATIONAL", "DOCUMENT", '"sql"', '"pipeline"'):
            assert leaked not in validator, (
                f"{leaked} is hardcoded in the validator — adding a datasource "
                "would mean editing it, which is what the table exists to avoid"
            )

    def test_the_validator_reads_its_rules_from_the_table(self, monkeypatch):
        """Adding a datasource means an enum member, a table row, and that
        source's own fields — never a new branch in the validator.

        Proved by changing an EXISTING kind's requirements and watching
        enforcement follow, with no code edit: if the rules were hardcoded, the
        binding below would still validate.
        """
        stricter = dict(DATA_BINDING_FORMS)
        stricter[DataBindingKindEnum.RELATIONAL] = {
            "required": ("schema_name", "sql", "params"),
            "execute_route": "execute_iceberg",
        }
        monkeypatch.setattr(
            "neutrino_database.models.da_schemas.DATA_BINDING_FORMS", stricter
        )

        with pytest.raises(ValidationError, match="requires params"):
            DashboardWidgetDataBinding(**_relational())

        # And the route comes from the table too, not from a constant.
        b = DashboardWidgetDataBinding(**_relational(params={"snapshot": "latest"}))
        assert b.execute_route == "execute_iceberg"

    def test_a_table_row_naming_an_unknown_field_fails_readably(self, monkeypatch):
        """The mistake someone adding a datasource is most likely to make: the
        table row lands before the model field. That must read as a missing
        field, not as an AttributeError raised from inside a validator."""
        broken = dict(DATA_BINDING_FORMS)
        broken[DataBindingKindEnum.RELATIONAL] = {
            "required": ("catalog",), "execute_route": "execute_trino",
        }
        monkeypatch.setattr(
            "neutrino_database.models.da_schemas.DATA_BINDING_FORMS", broken
        )
        with pytest.raises(ValidationError, match="requires catalog"):
            DashboardWidgetDataBinding(
                connection_id=uuid.uuid4(),
                kind=DataBindingKindEnum.RELATIONAL,
            )

    def test_every_kind_has_a_complete_table_row(self):
        """A member with a missing key would pass validation and then fail at
        execute time, per widget, per load."""
        for kind in DataBindingKindEnum:
            spec = DATA_BINDING_FORMS.get(kind)
            assert spec, f"{kind.value} has no DATA_BINDING_FORMS entry"
            for key in ("required", "execute_route", "body_fields"):
                assert spec.get(key), f"{kind.value} names no {key}"

    def test_body_fields_are_a_subset_of_the_model(self):
        """A body field the model lacks would send a null to connector-service."""
        fields = set(DashboardWidgetDataBinding.model_fields)
        for kind, spec in DATA_BINDING_FORMS.items():
            unknown = [f for f in spec["body_fields"] if f not in fields]
            assert not unknown, f"{kind.value} body names unknown field(s): {unknown}"

    def test_execute_body_carries_the_query_and_nothing_else(self):
        rel = DashboardWidgetDataBinding(**_relational())
        assert rel.execute_body == {"sql": _relational()["sql"]}
        # schema_name is REQUIRED for validity but is not part of the request —
        # the two lists are deliberately different.
        assert "schema_name" not in rel.execute_body
        assert "connection_id" not in rel.execute_body, (
            "the connection is in the URL, not the body"
        )

    def test_execute_body_for_a_document_binding(self):
        doc = DashboardWidgetDataBinding(**_document())
        assert doc.execute_body == {
            "database": "analytics",
            "collection": "customers",
            "pipeline": [{"$group": {"_id": "$tier", "n": {"$sum": 1}}}],
        }

    def test_every_required_field_exists_on_the_model(self):
        """A table row naming a field the model lacks would make every binding
        of that kind fail its completeness check with a confusing message."""
        fields = set(DashboardWidgetDataBinding.model_fields)
        for kind, spec in DATA_BINDING_FORMS.items():
            missing = [f for f in spec["required"] if f not in fields]
            assert not missing, f"{kind.value} requires unknown field(s): {missing}"

    def test_no_two_kinds_share_an_identifying_field(self):
        """Inference for legacy rows works by which fields are present, so two
        kinds sharing their whole field set would be indistinguishable."""
        signatures = {k: frozenset(s["required"]) for k, s in DATA_BINDING_FORMS.items()}
        assert len(set(signatures.values())) == len(signatures), (
            f"two kinds have identical required fields: {signatures}"
        )
