"""
NC-519 — ``user_memory`` + ``user_memory_settings`` (long-term agent memory).

NC-416 gave chat an *intra*-conversation context window (100k tokens, auto
compaction at 80%). It does nothing across conversations, and its summarizer is
told to discard tool observations — so the durable detail a memory layer wants
to keep is precisely what compaction throws away. These two tables are the
cross-chat half: facts, preferences and corrections that outlive the chat they
were learned in.

Locked design points these tests pin:

  * ``user_memory`` is the SOURCE OF TRUTH. The per-tenant Elasticsearch index
    ``memories_tenant_{tenant}`` holds a rebuildable mirror for hybrid
    retrieval only, so an ES outage degrades recall and never correctness.
    Nothing here depends on pgvector — there is no vector column.
  * Keyed on ``user_id``, NOT ``member.id``. Document ACLs are member-keyed
    because the file-permission store keys by member (NC-131), but memory is
    ours end to end and agent-platform already holds ``user_id`` from the
    internal token — keying on it avoids a connector-service round-trip per
    turn. ``user_id`` is NOT NULL with FK **CASCADE**: GDPR erasure rides this
    FK, so a deleted user cannot leave memories behind.
  * ``workspace_id`` is **nullable**, unlike ``chat.workspace_id`` (X-CHAT-WS-1).
    v1 always writes it set so memory learned in one workspace cannot surface
    in another; NULL is reserved for a "follows the user" scope not yet
    committed to. The column shape must not force that decision either way.
  * ``source_chat_id`` / ``source_message_id`` nullable FK **SET NULL** — a
    memory is a durable conclusion that must outlive the conversation that
    produced it (same posture as ``chat_artifact.message_id``). Deleting the
    chat unlinks provenance; it does not destroy the memory.
  * ``superseded_by`` nullable self-FK SET NULL — reconciliation lineage. An
    UPDATE decision inserts the new row and points the old one here before
    soft-deleting it, so "what did we believe, and when did we stop" stays
    answerable. A row may never supersede itself.
  * ``kind`` / ``origin`` / ``scope`` are String + CHECK, a deliberate
    deviation from ``chat_artifact.kind``'s native PgEnum: all three sets are
    expected to grow (procedural memories, workspace-shared scope), and
    extending a CHECK is a one-line migration where
    ``ALTER TYPE ... ADD VALUE`` cannot be rolled back.
  * The dedupe index is UNIQUE on (tenant_id, user_id, content_hash) but
    **partial** on ``deleted_at IS NULL`` — re-learning something the user
    deleted earlier must be allowed, because they may have deleted it for being
    stale rather than wrong forever.
  * ``user_memory_settings.enabled`` defaults **TRUE** — memory is opt-OUT. The
    gate that keeps a deployment dark is the service-level
    ``unified_memory_enabled`` flag (still False); within an enabled deployment
    every user captures without finding the settings page. The row records a
    deliberate choice, which is why absence is not the same as ``false``.

The test engine builds schema from ``tables.py`` via ``metadata.create_all``
(see conftest); the matching alembic revision ``h2i3j4k5l6m7`` carries the same
shape for dev/prod.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import delete, insert, select

from neutrino_database.models.tables import (
    chat,
    message,
    tenant,
    user as user_table,
    user_memory,
    user_memory_settings,
    workspace,
)


# ---------------------------------------------------------------------------
# Helpers — same shape as test_chat_artifact_schema.py
# ---------------------------------------------------------------------------


async def _columns(test_engine, table_name: str) -> dict:
    async with test_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: {
                c["name"]: c for c in sa.inspect(sync_conn).get_columns(table_name)
            }
        )


async def _indexes(test_engine, table_name: str) -> list[dict]:
    async with test_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).get_indexes(table_name)
        )


async def _foreign_keys(test_engine, table_name: str) -> list[dict]:
    async with test_engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: sa.inspect(sync_conn).get_foreign_keys(table_name)
        )


async def _udt_names(test_engine, table_name: str) -> dict[str, str]:
    async with test_engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                """
                SELECT column_name, udt_name
                FROM information_schema.columns
                WHERE table_name = :t
                """
            ),
            {"t": table_name},
        )
        return {name: udt for name, udt in result.fetchall()}


def _ondelete(fk: dict) -> str | None:
    return (fk.get("options") or {}).get("ondelete")


def _fk_for(fks: list[dict], column: str) -> dict | None:
    return next((fk for fk in fks if fk["constrained_columns"] == [column]), None)


def _hash(text_value: str) -> str:
    return hashlib.sha256(text_value.strip().lower().encode()).hexdigest()


async def _seed_principals(conn):
    """A tenant + workspace + user + chat + message, the FK parents a memory
    row needs. Returns the ids as strings."""
    tenant_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    chat_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    await conn.execute(
        insert(tenant).values(
            id=tenant_id,
            name="nc519-tenant",
            org_external_id=f"nc519-{uuid.uuid4()}",
        )
    )
    await conn.execute(
        insert(workspace).values(id=workspace_id, tenant_id=tenant_id, name="nc519-ws")
    )
    await conn.execute(
        insert(user_table).values(
            id=user_id,
            tenant_id=tenant_id,
            email=f"nc519-{uuid.uuid4()}@test.local",
        )
    )
    await conn.execute(
        insert(chat).values(
            id=chat_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            created_by=user_id,
            title="nc519-chat",
        )
    )
    await conn.execute(
        insert(message).values(
            id=message_id,
            tenant_id=tenant_id,
            chat_id=chat_id,
            user_id=user_id,
            role="USER",
            content="I always want the SQL shown.",
        )
    )
    return tenant_id, workspace_id, user_id, chat_id, message_id


def _memory_values(*, tenant_id, user_id, workspace_id=None, **overrides):
    content = overrides.pop("content", "Wants the SQL shown with every answer.")
    values = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "kind": "preference",
        "origin": "auto",
        "content": content,
        "content_hash": _hash(content),
    }
    values.update(overrides)
    return values


async def _cleanup(conn, tenant_id: str) -> None:
    """Tenant CASCADE clears memories, settings, chats and messages."""
    await conn.execute(delete(tenant).where(tenant.c.id == tenant_id))


# ---------------------------------------------------------------------------
# 1. Columns + types
# ---------------------------------------------------------------------------


class TestUserMemoryColumns:
    @pytest.mark.asyncio
    async def test_table_and_core_columns_exist(self, test_engine):
        cols = await _columns(test_engine, "user_memory")
        expected = {
            "id",
            "tenant_id",
            "user_id",
            "workspace_id",
            "scope",
            "kind",
            "content",
            "content_hash",
            "confidence",
            "origin",
            "source_chat_id",
            "source_message_id",
            "superseded_by",
            "last_used_at",
            "use_count",
            "pinned",
            "created_at",
            "updated_at",
            "deleted_at",
        }
        missing = expected - set(cols.keys())
        assert not missing, (
            f"user_memory is missing columns {sorted(missing)}. "
            f"Present: {sorted(cols.keys())}"
        )

    @pytest.mark.asyncio
    async def test_user_id_not_null(self, test_engine):
        """A memory has no meaning without its subject."""
        cols = await _columns(test_engine, "user_memory")
        assert cols["user_id"]["nullable"] is False, (
            "user_memory.user_id must be NOT NULL — memory is per-user by "
            "construction, and a NULL subject would be retrievable by everyone."
        )

    @pytest.mark.asyncio
    async def test_workspace_id_is_nullable(self, test_engine):
        """Deliberately unlike chat.workspace_id (X-CHAT-WS-1): NULL is reserved
        for a cross-workspace 'follows the user' scope we have not committed to.
        v1 always writes it set."""
        cols = await _columns(test_engine, "user_memory")
        assert cols["workspace_id"]["nullable"] is True, (
            "user_memory.workspace_id must stay nullable so the cross-workspace "
            "scope decision does not require a migration."
        )

    @pytest.mark.asyncio
    async def test_no_vector_column(self, test_engine):
        """Embeddings live in Elasticsearch, not Postgres. pgvector is not
        installed anywhere in this platform, and the vestigial
        ``embedding.dense_vector ARRAY(Float)`` column is unindexed and
        unsearchable — building on it would be a trap."""
        cols = await _columns(test_engine, "user_memory")
        vectorish = {
            name for name in cols if "vector" in name or "embedding" in name
        }
        assert not vectorish, (
            "user_memory must not carry vectors — retrieval is Elasticsearch "
            f"hybrid (BM25 + kNN). Found: {sorted(vectorish)}"
        )

    @pytest.mark.asyncio
    async def test_kind_and_origin_are_text_not_native_enum(self, test_engine):
        """Deliberate deviation from chat_artifact.kind. Both sets will grow
        (procedural memories, new origins); extending a CHECK is a one-line
        migration, while ALTER TYPE ... ADD VALUE cannot be rolled back."""
        udts = await _udt_names(test_engine, "user_memory")
        for column in ("kind", "origin", "scope"):
            assert udts.get(column) == "varchar", (
                f"user_memory.{column} must be varchar + CHECK, not a native "
                f"PgEnum. Got udt: {udts.get(column)!r}"
            )

    @pytest.mark.asyncio
    async def test_deleted_at_nullable_for_soft_delete(self, test_engine):
        cols = await _columns(test_engine, "user_memory")
        assert cols["deleted_at"]["nullable"] is True, (
            "user_memory.deleted_at is a soft-delete tombstone — nullable. The "
            "dedupe and hot-path indexes are partial on it."
        )


# ---------------------------------------------------------------------------
# 2. Foreign keys — the ondelete posture is the whole design
# ---------------------------------------------------------------------------


class TestUserMemoryForeignKeys:
    @pytest.mark.asyncio
    async def test_user_id_cascades_for_gdpr_erasure(self, test_engine):
        fks = await _foreign_keys(test_engine, "user_memory")
        fk = _fk_for(fks, "user_id")
        assert fk is not None, "user_memory.user_id must be a FK to user.id"
        assert fk["referred_table"] == "user"
        assert _ondelete(fk) == "CASCADE", (
            "user_memory.user_id must CASCADE: 'delete my account' has to take "
            "the memories with it, and we should not rely on application code "
            "to remember that. Got: " + repr(_ondelete(fk))
        )

    @pytest.mark.asyncio
    async def test_tenant_id_cascades(self, test_engine):
        fks = await _foreign_keys(test_engine, "user_memory")
        fk = _fk_for(fks, "tenant_id")
        assert fk is not None and fk["referred_table"] == "tenant"
        assert _ondelete(fk) == "CASCADE"

    @pytest.mark.asyncio
    async def test_provenance_fks_set_null_not_cascade(self, test_engine):
        """A memory is a durable conclusion. Deleting the chat it was learned in
        must unlink provenance, not destroy the memory — same posture as
        chat_artifact.message_id."""
        fks = await _foreign_keys(test_engine, "user_memory")
        for column, referred in (
            ("source_chat_id", "chat"),
            ("source_message_id", "message"),
        ):
            fk = _fk_for(fks, column)
            assert fk is not None, f"user_memory.{column} must be a FK"
            assert fk["referred_table"] == referred
            assert _ondelete(fk) == "SET NULL", (
                f"user_memory.{column} must SET NULL so a memory outlives the "
                f"conversation that produced it. Got: {_ondelete(fk)!r}"
            )

    @pytest.mark.asyncio
    async def test_superseded_by_is_self_fk_set_null(self, test_engine):
        fks = await _foreign_keys(test_engine, "user_memory")
        fk = _fk_for(fks, "superseded_by")
        assert fk is not None, "user_memory.superseded_by must be a self-FK"
        assert fk["referred_table"] == "user_memory"
        assert _ondelete(fk) == "SET NULL", (
            "A retired memory must survive deletion of the row that replaced "
            f"it, or the audit trail breaks. Got: {_ondelete(fk)!r}"
        )

    @pytest.mark.asyncio
    async def test_memories_die_with_their_user(self, test_engine):
        """The CASCADE above, exercised end to end."""
        async with test_engine.begin() as conn:
            tenant_id = None
            try:
                tenant_id, ws_id, user_id, _chat, _msg = await _seed_principals(conn)
                await conn.execute(
                    insert(user_memory).values(
                        **_memory_values(
                            tenant_id=tenant_id, user_id=user_id, workspace_id=ws_id
                        )
                    )
                )
                await conn.execute(
                    delete(user_table).where(user_table.c.id == user_id)
                )
                remaining = (
                    await conn.execute(
                        select(sa.func.count())
                        .select_from(user_memory)
                        .where(user_memory.c.user_id == user_id)
                    )
                ).scalar_one()
                assert remaining == 0, (
                    "Deleting the user left memories behind — GDPR erasure "
                    "depends on this CASCADE."
                )
            finally:
                if tenant_id:
                    await _cleanup(conn, tenant_id)

    @pytest.mark.asyncio
    async def test_memory_outlives_its_source_chat(self, test_engine):
        async with test_engine.begin() as conn:
            tenant_id = None
            try:
                tenant_id, ws_id, user_id, chat_id, msg_id = await _seed_principals(
                    conn
                )
                memory_id = str(uuid.uuid4())
                await conn.execute(
                    insert(user_memory).values(
                        **_memory_values(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            workspace_id=ws_id,
                            id=memory_id,
                            source_chat_id=chat_id,
                            source_message_id=msg_id,
                        )
                    )
                )
                await conn.execute(delete(chat).where(chat.c.id == chat_id))

                row = (
                    await conn.execute(
                        select(
                            user_memory.c.source_chat_id,
                            user_memory.c.source_message_id,
                            user_memory.c.content,
                        ).where(user_memory.c.id == memory_id)
                    )
                ).one_or_none()
                assert row is not None, (
                    "Deleting the source chat destroyed the memory — provenance "
                    "FKs must be SET NULL, not CASCADE."
                )
                assert row.source_chat_id is None
                # message CASCADEs off chat, so its provenance unlinks too.
                assert row.source_message_id is None
            finally:
                if tenant_id:
                    await _cleanup(conn, tenant_id)


# ---------------------------------------------------------------------------
# 3. CHECK constraints — the integrity the missing PgEnum would have given
# ---------------------------------------------------------------------------


class TestUserMemoryChecks:
    @pytest.mark.parametrize(
        "column,bad_value",
        [
            ("kind", "episodic"),
            ("origin", "imported"),
            ("scope", "global"),
        ],
    )
    @pytest.mark.asyncio
    async def test_rejects_unknown_enumerated_value(
        self, test_engine, column, bad_value
    ):
        """`episodic` is the interesting case: it was considered and rejected —
        chat history and the artifact index already are episodic memory, and
        duplicating them invites recall of stale narrative."""
        async with test_engine.begin() as conn:
            tenant_id = None
            try:
                tenant_id, ws_id, user_id, _c, _m = await _seed_principals(conn)
                with pytest.raises(Exception):
                    await conn.execute(
                        insert(user_memory).values(
                            **_memory_values(
                                tenant_id=tenant_id,
                                user_id=user_id,
                                workspace_id=ws_id,
                                **{column: bad_value},
                            )
                        )
                    )
            finally:
                if tenant_id:
                    # The failed statement aborts the transaction, so cleanup
                    # has to run on a fresh connection.
                    pass
        async with test_engine.begin() as conn:
            if tenant_id:
                await _cleanup(conn, tenant_id)

    @pytest.mark.parametrize("bad_confidence", [-0.1, 1.5])
    @pytest.mark.asyncio
    async def test_confidence_must_be_a_probability(self, test_engine, bad_confidence):
        """Retrieval ranking and the decay job both read confidence as a 0..1
        weight; an out-of-range value would silently dominate every ranking."""
        async with test_engine.begin() as conn:
            tenant_id, ws_id, user_id, _c, _m = await _seed_principals(conn)
            with pytest.raises(Exception):
                await conn.execute(
                    insert(user_memory).values(
                        **_memory_values(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            workspace_id=ws_id,
                            confidence=bad_confidence,
                        )
                    )
                )
        async with test_engine.begin() as conn:
            await _cleanup(conn, tenant_id)

    @pytest.mark.asyncio
    async def test_content_cannot_be_blank(self, test_engine):
        """An empty memory would still consume a slot in the injected block's
        token budget while carrying nothing."""
        async with test_engine.begin() as conn:
            tenant_id, ws_id, user_id, _c, _m = await _seed_principals(conn)
            with pytest.raises(Exception):
                await conn.execute(
                    insert(user_memory).values(
                        **_memory_values(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            workspace_id=ws_id,
                            content="",
                            content_hash=_hash(""),
                        )
                    )
                )
        async with test_engine.begin() as conn:
            await _cleanup(conn, tenant_id)

    @pytest.mark.asyncio
    async def test_memory_cannot_supersede_itself(self, test_engine):
        """An applier bug would otherwise create a row that is simultaneously
        live and retired, which no read path could interpret."""
        async with test_engine.begin() as conn:
            tenant_id, ws_id, user_id, _c, _m = await _seed_principals(conn)
            memory_id = str(uuid.uuid4())
            with pytest.raises(Exception):
                await conn.execute(
                    insert(user_memory).values(
                        **_memory_values(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            workspace_id=ws_id,
                            id=memory_id,
                            superseded_by=memory_id,
                        )
                    )
                )
        async with test_engine.begin() as conn:
            await _cleanup(conn, tenant_id)


# ---------------------------------------------------------------------------
# 4. Indexes — the hot path and the dedupe guard
# ---------------------------------------------------------------------------


class TestUserMemoryIndexes:
    @pytest.mark.asyncio
    async def test_hot_path_index_is_partial_on_deleted_at(self, test_engine):
        """Every list and every retrieval is
        WHERE tenant_id AND user_id AND deleted_at IS NULL."""
        indexes = await _indexes(test_engine, "user_memory")
        idx = next(
            (i for i in indexes if i["name"] == "ix_user_memory_tenant_user"), None
        )
        assert idx is not None, "ix_user_memory_tenant_user is missing"
        assert idx["column_names"] == ["tenant_id", "user_id"]
        predicate = (idx.get("dialect_options") or {}).get("postgresql_where")
        assert predicate and "deleted_at" in str(predicate), (
            "ix_user_memory_tenant_user must be partial on deleted_at IS NULL "
            f"so tombstones stay out of the hot path. Got: {predicate!r}"
        )

    @pytest.mark.asyncio
    async def test_dedupe_index_is_unique_and_partial(self, test_engine):
        indexes = await _indexes(test_engine, "user_memory")
        idx = next((i for i in indexes if i["name"] == "ix_user_memory_dedupe"), None)
        assert idx is not None, "ix_user_memory_dedupe is missing"
        assert idx["unique"], (
            "The dedupe index must be UNIQUE — it is what lets the extractor "
            "short-circuit an exact repeat to NOOP without an LLM call."
        )
        assert idx["column_names"] == ["tenant_id", "user_id", "content_hash"]
        predicate = (idx.get("dialect_options") or {}).get("postgresql_where")
        assert predicate and "deleted_at" in str(predicate), (
            "The dedupe index must be PARTIAL on deleted_at IS NULL, so a user "
            "who deleted a stale memory can still re-learn it later. "
            f"Got: {predicate!r}"
        )

    @pytest.mark.asyncio
    async def test_duplicate_live_content_rejected_but_allowed_after_delete(
        self, test_engine
    ):
        """Both halves of the partial-unique behaviour, exercised.

        The rejected insert runs inside a SAVEPOINT: a unique violation aborts
        the enclosing transaction in Postgres, which would roll back the seeded
        tenant and make the second half of the test meaningless.
        """
        content = "Revenue means net of returns, not gross."
        async with test_engine.begin() as conn:
            tenant_id = None
            try:
                tenant_id, ws_id, user_id, _c, _m = await _seed_principals(conn)
                first_id = str(uuid.uuid4())
                await conn.execute(
                    insert(user_memory).values(
                        **_memory_values(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            workspace_id=ws_id,
                            id=first_id,
                            kind="correction",
                            content=content,
                        )
                    )
                )

                savepoint = await conn.begin_nested()
                with pytest.raises(sa.exc.IntegrityError):
                    await conn.execute(
                        insert(user_memory).values(
                            **_memory_values(
                                tenant_id=tenant_id,
                                user_id=user_id,
                                workspace_id=ws_id,
                                kind="correction",
                                content=content,
                            )
                        )
                    )
                await savepoint.rollback()

                # Soft-delete the original, then re-learn the same fact.
                await conn.execute(
                    user_memory.update()
                    .where(user_memory.c.id == first_id)
                    .values(deleted_at=sa.func.now())
                )
                await conn.execute(
                    insert(user_memory).values(
                        **_memory_values(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            workspace_id=ws_id,
                            kind="correction",
                            content=content,
                        )
                    )
                )
                live = (
                    await conn.execute(
                        select(sa.func.count())
                        .select_from(user_memory)
                        .where(
                            user_memory.c.user_id == user_id,
                            user_memory.c.deleted_at.is_(None),
                        )
                    )
                ).scalar_one()
                assert live == 1, (
                    "Re-learning a previously deleted memory must be allowed "
                    f"and must leave exactly one live row. Got {live}."
                )
            finally:
                if tenant_id:
                    await _cleanup(conn, tenant_id)

    @pytest.mark.asyncio
    async def test_same_content_allowed_for_two_different_users(self, test_engine):
        """The dedupe guard is per-user. Two colleagues may legitimately hold
        the same preference, and one must not block the other's."""
        content = "Prefers short answers."
        async with test_engine.begin() as conn:
            tenant_id = None
            try:
                tenant_id, ws_id, user_a, _c, _m = await _seed_principals(conn)
                user_b = str(uuid.uuid4())
                await conn.execute(
                    insert(user_table).values(
                        id=user_b,
                        tenant_id=tenant_id,
                        email=f"nc519-b-{uuid.uuid4()}@test.local",
                    )
                )
                for uid in (user_a, user_b):
                    await conn.execute(
                        insert(user_memory).values(
                            **_memory_values(
                                tenant_id=tenant_id,
                                user_id=uid,
                                workspace_id=ws_id,
                                content=content,
                            )
                        )
                    )
                count = (
                    await conn.execute(
                        select(sa.func.count())
                        .select_from(user_memory)
                        .where(user_memory.c.content_hash == _hash(content))
                    )
                ).scalar_one()
                assert count == 2
            finally:
                if tenant_id:
                    await _cleanup(conn, tenant_id)


# ---------------------------------------------------------------------------
# 5. user_memory_settings — fail-safe defaults
# ---------------------------------------------------------------------------


class TestUserMemorySettings:
    @pytest.mark.asyncio
    async def test_columns_exist(self, test_engine):
        cols = await _columns(test_engine, "user_memory_settings")
        expected = {
            "user_id",
            "tenant_id",
            "enabled",
            "capture_facts",
            "capture_preferences",
            "capture_corrections",
            "created_at",
            "updated_at",
        }
        missing = expected - set(cols.keys())
        assert not missing, f"user_memory_settings missing {sorted(missing)}"

    @pytest.mark.asyncio
    async def test_enabled_defaults_true(self, test_engine):
        """Memory is opt-OUT: a row created by any path captures. The
        environment-level ``unified_memory_enabled`` flag is what holds a
        deployment dark, not this column."""
        async with test_engine.begin() as conn:
            tenant_id = None
            try:
                tenant_id, _ws, user_id, _c, _m = await _seed_principals(conn)
                await conn.execute(
                    insert(user_memory_settings).values(
                        user_id=user_id, tenant_id=tenant_id
                    )
                )
                row = (
                    await conn.execute(
                        select(
                            user_memory_settings.c.enabled,
                            user_memory_settings.c.capture_facts,
                            user_memory_settings.c.capture_preferences,
                            user_memory_settings.c.capture_corrections,
                        ).where(user_memory_settings.c.user_id == user_id)
                    )
                ).one()
                assert row.enabled is True, (
                    "user_memory_settings.enabled must default TRUE — memory is "
                    "opt-out, and the environment flag is the dark switch."
                )
                # Per-kind switches default ON too, so `enabled` is the only
                # control a user needs to find to turn everything off.
                assert row.capture_facts is True
                assert row.capture_preferences is True
                assert row.capture_corrections is True
            finally:
                if tenant_id:
                    await _cleanup(conn, tenant_id)

    @pytest.mark.asyncio
    async def test_user_id_is_primary_key(self, test_engine):
        """One row per user, like workspace_da_settings keys on workspace_id —
        so a settings write is an upsert with no chance of duplicates."""
        async with test_engine.connect() as conn:
            pk = await conn.run_sync(
                lambda sync_conn: sa.inspect(sync_conn).get_pk_constraint(
                    "user_memory_settings"
                )
            )
        assert pk["constrained_columns"] == ["user_id"]


class TestHardeningColumns:
    """NC-519 second pass — columns added after an industry/research audit.

    Each exists because of a documented failure mode; the docstrings name it.
    """

    @pytest.mark.asyncio
    async def test_the_new_columns_exist(self, test_engine):
        cols = await _columns(test_engine, "user_memory")
        expected = {
            # Reinforcement gating: hold an inferred memory until a second turn
            # corroborates it.
            "observation_count",
            "status",
            # The episodic ledger: a memory is a claim ABOUT evidence, not a
            # replacement for it.
            "source_excerpt",
            # Bi-temporal: when it was true, apart from when we learned it.
            "valid_from",
            "valid_to",
        }
        missing = expected - set(cols.keys())
        assert not missing, f"user_memory is missing {sorted(missing)}"

    @pytest.mark.asyncio
    async def test_status_defaults_active_but_the_service_gates_inferences(
        self, test_engine
    ):
        """The COLUMN default is 'active' because it applies to rows any code
        path creates. Reinforcement gating lives in the service layer, which
        passes 'candidate' explicitly for origin='auto' — that placement is
        deliberate: most memories never get a settings-route insert, so the
        service default is the one that decides."""
        cols = await _columns(test_engine, "user_memory")
        assert "active" in (cols["status"].get("default") or "")

    @pytest.mark.asyncio
    async def test_observation_count_starts_at_one(self, test_engine):
        cols = await _columns(test_engine, "user_memory")
        assert "1" in (cols["observation_count"].get("default") or "")
        assert cols["observation_count"]["nullable"] is False

    @pytest.mark.asyncio
    async def test_validity_window_may_be_open(self, test_engine):
        """NULL valid_to means "still true as far as we know" — the common case,
        and distinct from a closed window that says "was true until"."""
        cols = await _columns(test_engine, "user_memory")
        assert cols["valid_from"]["nullable"] is True
        assert cols["valid_to"]["nullable"] is True

    @pytest.mark.asyncio
    async def test_the_new_check_constraints_are_present(self, test_engine):
        async with test_engine.connect() as conn:
            rows = await conn.execute(
                sa.text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'user_memory'::regclass AND contype = 'c'"
                )
            )
            names = {r[0] for r in rows.fetchall()}
        for expected in (
            "ck_user_memory_status",
            "ck_user_memory_observation_count",
            "ck_user_memory_validity_order",
        ):
            assert expected in names, f"{expected} is missing"

    @pytest.mark.asyncio
    async def test_a_backwards_validity_window_is_rejected(self, test_engine):
        """valid_to before valid_from is not a fact with an odd shape, it is a
        bug — most likely a supersede applied to the wrong row."""
        from datetime import UTC, datetime

        async with test_engine.begin() as conn:
            tenant_id = None
            try:
                tenant_id, ws_id, user_id, _c, _m = await _seed_principals(conn)
                savepoint = await conn.begin_nested()
                with pytest.raises(sa.exc.IntegrityError):
                    await conn.execute(
                        insert(user_memory).values(
                            **_memory_values(
                                tenant_id=tenant_id,
                                user_id=user_id,
                                workspace_id=ws_id,
                                valid_from=datetime(2026, 8, 1, tzinfo=UTC),
                                valid_to=datetime(2026, 3, 1, tzinfo=UTC),
                            )
                        )
                    )
                await savepoint.rollback()
            finally:
                if tenant_id:
                    await _cleanup(conn, tenant_id)

    @pytest.mark.asyncio
    async def test_an_unknown_status_is_rejected(self, test_engine):
        async with test_engine.begin() as conn:
            tenant_id = None
            try:
                tenant_id, ws_id, user_id, _c, _m = await _seed_principals(conn)
                savepoint = await conn.begin_nested()
                with pytest.raises(sa.exc.IntegrityError):
                    await conn.execute(
                        insert(user_memory).values(
                            **_memory_values(
                                tenant_id=tenant_id,
                                user_id=user_id,
                                workspace_id=ws_id,
                                status="archived",
                            )
                        )
                    )
                await savepoint.rollback()
            finally:
                if tenant_id:
                    await _cleanup(conn, tenant_id)
