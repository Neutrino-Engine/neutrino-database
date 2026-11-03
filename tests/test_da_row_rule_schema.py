"""NC-845 — da_row_rule and da_member_row_value schema shape."""

from __future__ import annotations

from neutrino_database.models import tables


def _fk(table, column):
    (fk,) = table.c[column].foreign_keys
    return fk.column.table.name, fk.ondelete


def test_rule_fks_cascade_with_workspace_and_catalog():
    t = tables.da_row_rule
    assert _fk(t, "workspace_id") == ("workspace", "CASCADE")
    assert _fk(t, "da_catalog_table_id") == ("da_catalog_table", "CASCADE")
    assert _fk(t, "parent_rule_id") == ("da_row_rule", "CASCADE")


def test_one_rule_per_table_per_workspace():
    names = {c.name for c in tables.da_row_rule.constraints}
    assert {"ux_da_row_rule_workspace_table", "ck_da_row_rule_link_complete"} <= names


def test_values_cascade_with_rule_and_user():
    t = tables.da_member_row_value
    assert _fk(t, "rule_id") == ("da_row_rule", "CASCADE")
    assert _fk(t, "user_id") == ("user", "CASCADE")
    assert "ux_da_member_row_value" in {c.name for c in t.constraints}


def test_orm_maps_to_tables():
    from neutrino_database.models.orm import DAMemberRowValue, DARowRule

    assert DARowRule.__table__ is tables.da_row_rule
    assert DAMemberRowValue.__table__ is tables.da_member_row_value
