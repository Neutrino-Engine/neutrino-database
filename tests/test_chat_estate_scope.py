"""ITOps merge S5/S6 — a durable estate scope on ``chat``.

An estate investigation (host or incident) is an ordinary chat conversation,
not a special surface. The scope it is about — kind, uid, display name — has
to live on the row so it survives a refresh and a reopen from history,
instead of living only in the browser (the same argument that put ``pillar``
on this table). Schema-shape only; no DB round-trip needed since
``chat.columns`` is plain SQLAlchemy metadata.
"""

from __future__ import annotations

from neutrino_database.models.tables import chat


def test_chat_carries_a_durable_estate_scope():
    cols = {c.name for c in chat.columns}
    assert {"estate_scope_kind", "estate_uid", "estate_display_name"} <= cols


def test_the_estate_scope_is_optional_like_every_other_chat_scope():
    for name in ("estate_scope_kind", "estate_uid", "estate_display_name"):
        assert chat.columns[name].nullable is True
