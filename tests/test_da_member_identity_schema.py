"""NC-864 — da_member_identity schema (metadata only, no DB)."""

from neutrino_database.models import tables


def test_one_identity_per_member_per_connection():
    t = tables.da_member_identity
    assert [c.name for c in t.primary_key.columns] == ["integration_id", "user_id"]
    assert t.c.identity.type.length == 320
    assert t.c.identity.nullable is False


def test_deletes_cascade_but_keep_the_row_when_the_setter_leaves():
    t = tables.da_member_identity
    ondelete = {c.name: next(iter(c.foreign_keys)).ondelete for c in t.columns if c.foreign_keys}
    assert ondelete == {"integration_id": "CASCADE", "user_id": "CASCADE", "set_by": "SET NULL"}


def test_orm_maps_to_table():
    from neutrino_database.models.orm import DAMemberIdentity

    assert DAMemberIdentity.__table__ is tables.da_member_identity
