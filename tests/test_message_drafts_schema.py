"""NC-694 — message drafts: ``message.parent_message_id`` and ``chat.active_leaf_message_id``."""

from __future__ import annotations

import sqlalchemy as sa


async def _inspect(test_engine, fn):
    async with test_engine.connect() as conn:
        return await conn.run_sync(lambda sync_conn: fn(sa.inspect(sync_conn)))


async def test_message_parent_is_a_nullable_self_fk_set_null(test_engine):
    cols = await _inspect(test_engine, lambda i: {c["name"]: c for c in i.get_columns("message")})
    assert cols["parent_message_id"]["nullable"] is True
    fks = await _inspect(test_engine, lambda i: i.get_foreign_keys("message"))
    fk = next(f for f in fks if f["constrained_columns"] == ["parent_message_id"])
    assert fk["referred_table"] == "message"
    assert (fk.get("options") or {}).get("ondelete") == "SET NULL"
    idx = await _inspect(test_engine, lambda i: i.get_indexes("message"))
    assert any(ix["column_names"] == ["parent_message_id"] for ix in idx)


async def test_chat_active_leaf_is_nullable_without_fk(test_engine):
    cols = await _inspect(test_engine, lambda i: {c["name"]: c for c in i.get_columns("chat")})
    assert cols["active_leaf_message_id"]["nullable"] is True
    fks = await _inspect(test_engine, lambda i: i.get_foreign_keys("chat"))
    assert not any(f["constrained_columns"] == ["active_leaf_message_id"] for f in fks)
