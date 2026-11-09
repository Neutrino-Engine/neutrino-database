"""NC-864 phase 2: identity-table schema (metadata only, no DB)."""

from neutrino_database.models import orm, tables


def test_config_defaults_to_native_and_require_approval():
    c = tables.integration_da_config.c
    assert "native" in str(c.row_scope_mode.server_default.arg)
    assert "require_approval" in str(c.multi_match_policy.server_default.arg)


def test_one_status_per_table_and_one_approval_per_email():
    assert [c.name for c in tables.da_rls_table_status.primary_key.columns] == [
        "integration_id", "schema_name", "table_name"]
    assert [c.name for c in tables.da_rls_identity_approval.primary_key.columns] == [
        "integration_id", "login_email"]


def test_orm_maps_to_tables():
    assert orm.DARlsTableStatus.__table__ is tables.da_rls_table_status
    assert orm.DARlsIdentityApproval.__table__ is tables.da_rls_identity_approval
