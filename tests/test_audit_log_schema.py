"""
Schema tests for ``audit_log`` (NEU-1804 — slice C3a).

The audit_log table is the foundation for compliance reporting (SOC 2,
HIPAA, GDPR). Every meaningful mutation in the gateway will write a
single row here so we can answer "who did what to which resource at
what time" — required by every framework's audit/access-review controls.

The table is **append-only**: a Postgres BEFORE UPDATE/DELETE trigger
raises a custom SQLSTATE ('AU001') so the immutability invariant holds
at the database level, not just by convention. Even a DBA going through
the runtime app cannot edit history; break-glass paths exist via
documented superuser DDL.

These tests are written before the schema lands (TDD discipline) so
they fail loudly until ``tables.py``, ``orm.py``, and the alembic
migration agree.

See ``user-stories/user-lifecycle.md`` § "Audit log requirements" and
``user-stories/compliance.md`` for the framework-level mapping.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker

from neutrino_database.models.enums import TenantStatusEnum, UserStatusEnum
from neutrino_database.models.orm import AuditLog, Tenant, User


def _unique() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Helpers — factory fixtures for the rows audit_log references.
# ---------------------------------------------------------------------------


async def _seed_tenant(SessionMaker) -> str:
    """Insert a tenant and return its id; tests reference it for FK."""
    suffix = _unique()
    tenant_id = str(uuid.uuid4())
    async with SessionMaker() as setup:
        async with setup.begin():
            setup.add(
                Tenant(
                    id=tenant_id,
                    name=f"acme-{suffix}",
                    org_external_id=f"acme-{suffix}",
                    status=TenantStatusEnum.ACTIVE,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
    return tenant_id


async def _drop_tenant(SessionMaker, tenant_id: str) -> None:
    """
    Cleanup: clear audit_log rows for this tenant via TRUNCATE-style
    (the BEFORE UPDATE/DELETE trigger blocks DELETE; TRUNCATE skips the
    row trigger), then delete the tenant. In production the retention
    runner is the only thing that removes audit_log rows, but tests
    need a quick way to reset state.
    """
    async with SessionMaker() as cleanup:
        async with cleanup.begin():
            await cleanup.execute(
                sa.text(
                    "TRUNCATE TABLE audit_log RESTART IDENTITY CASCADE"
                )
            )
            await cleanup.execute(
                sa.delete(Tenant).where(Tenant.id == tenant_id)
            )


# ---------------------------------------------------------------------------
# Schema shape: table exists with the expected columns and types.
# ---------------------------------------------------------------------------


class TestAuditLogTable:
    @pytest.mark.asyncio
    async def test_audit_log_table_exists(self, test_engine):
        """The audit_log table must exist after Base.metadata.create_all."""
        async with test_engine.connect() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: sa.inspect(sync_conn).get_table_names()
            )
        assert "audit_log" in tables, (
            "audit_log table is missing — required for compliance "
            "(SOC 2 CC6.6, HIPAA § 164.312(b), GDPR Art 30/32)."
        )

    @pytest.mark.asyncio
    async def test_audit_log_has_all_required_columns(self, test_engine):
        """Pin every column the audit emitter relies on."""
        async with test_engine.connect() as conn:
            cols = await conn.run_sync(
                lambda sync_conn: {
                    c["name"]: c
                    for c in sa.inspect(sync_conn).get_columns("audit_log")
                }
            )
        required = {
            "id",
            "tenant_id",
            "actor_user_id",
            "event_type",
            "resource_type",
            "resource_id",
            "event_metadata",
            "ip_address",
            "user_agent",
            "occurred_at",
        }
        missing = required - set(cols)
        assert not missing, f"audit_log is missing columns: {missing}"

    @pytest.mark.asyncio
    async def test_audit_log_column_types_and_nullability(self, test_engine):
        """The table's column types match the design — UUIDs, JSONB, INET, TIMESTAMPTZ."""
        async with test_engine.connect() as conn:
            cols = await conn.run_sync(
                lambda sync_conn: {
                    c["name"]: c
                    for c in sa.inspect(sync_conn).get_columns("audit_log")
                }
            )

        # Required (NOT NULL) columns
        for required_col in (
            "id",
            "tenant_id",
            "event_type",
            "resource_type",
            "resource_id",
            "event_metadata",
            "occurred_at",
        ):
            assert cols[required_col]["nullable"] is False, (
                f"audit_log.{required_col} must be NOT NULL"
            )

        # Nullable columns (system actor; optional client metadata)
        for nullable_col in ("actor_user_id", "ip_address", "user_agent"):
            assert cols[nullable_col]["nullable"] is True, (
                f"audit_log.{nullable_col} must be nullable"
            )

        # occurred_at must be TIMESTAMP WITH TIME ZONE (matches the rest of this schema)
        occurred_at_type = cols["occurred_at"]["type"]
        assert isinstance(occurred_at_type, sa.TIMESTAMP)
        assert occurred_at_type.timezone is True, (
            "audit_log.occurred_at must be TIMESTAMP WITH TIME ZONE"
        )

    @pytest.mark.asyncio
    async def test_audit_log_indexes_exist(self, test_engine):
        """Pin the three indexes the read paths depend on.

        - (tenant_id, occurred_at DESC) — main read path: tenant admin viewer
        - (event_type) — filter by event type
        - (actor_user_id, occurred_at DESC) WHERE actor_user_id IS NOT NULL —
          "what did user X do" lookup
        """
        async with test_engine.connect() as conn:
            indexes = await conn.run_sync(
                lambda sync_conn: sa.inspect(sync_conn).get_indexes("audit_log")
            )
        idx_names = {idx["name"] for idx in indexes}
        for required_idx in (
            "ix_audit_log_tenant_occurred_at",
            "ix_audit_log_event_type",
            "ix_audit_log_actor_occurred_at",
        ):
            assert required_idx in idx_names, (
                f"audit_log is missing index {required_idx!r}; have {idx_names!r}"
            )


# ---------------------------------------------------------------------------
# Insert: audit emitter must be able to write rows.
# ---------------------------------------------------------------------------


class TestAuditLogInsert:
    @pytest.mark.asyncio
    async def test_can_insert_minimal_row(self, test_engine):
        """A row with only the required columns set must persist; defaults
        for event_metadata ({}) and occurred_at (now()) come from the
        server, not from the ORM."""
        SessionMaker = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        tenant_id = await _seed_tenant(SessionMaker)
        try:
            row_id = str(uuid.uuid4())
            async with SessionMaker() as session:
                async with session.begin():
                    session.add(
                        AuditLog(
                            id=row_id,
                            tenant_id=tenant_id,
                            event_type="tenant.created",
                            resource_type="tenant",
                            resource_id=tenant_id,
                        )
                    )

            async with SessionMaker() as verify:
                fetched = await verify.get(AuditLog, row_id)
                assert fetched is not None
                # event_metadata defaults to {} via server_default — verify
                # via the ORM type round-trip (JSONB → dict).
                assert fetched.event_metadata == {}, (
                    f"event_metadata should default to {{}}; got {fetched.event_metadata!r}"
                )
                # occurred_at defaults to now() and is timezone-aware.
                assert fetched.occurred_at is not None
                assert fetched.occurred_at.tzinfo is not None
        finally:
            await _drop_tenant(SessionMaker, tenant_id)

    @pytest.mark.asyncio
    async def test_can_insert_with_full_metadata(self, test_engine):
        """A row with metadata, ip, user-agent persists those values.

        We assert the JSONB value via ``event_metadata->>'name'`` and
        the INET value via ``host(ip_address)`` — those PG-specific
        operators stay raw on purpose: that's what's being tested. The
        INSERT itself uses the ORM so we exercise the same code path
        the application does.
        """
        SessionMaker = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        tenant_id = await _seed_tenant(SessionMaker)
        try:
            row_id = str(uuid.uuid4())
            resource_id = str(uuid.uuid4())
            async with SessionMaker() as session:
                async with session.begin():
                    session.add(
                        AuditLog(
                            id=row_id,
                            tenant_id=tenant_id,
                            event_type="workspace.created",
                            resource_type="workspace",
                            resource_id=resource_id,
                            event_metadata={"name": "Engineering"},
                            ip_address="203.0.113.42",
                            user_agent="Mozilla/5.0 test",
                        )
                    )

            async with test_engine.connect() as conn:
                result = await conn.execute(
                    sa.text(
                        "SELECT event_metadata->>'name' AS name, "
                        "       host(ip_address) AS ip, "
                        "       user_agent "
                        "FROM audit_log WHERE id = :id"
                    ),
                    {"id": row_id},
                )
                row = result.fetchone()
                assert row is not None
                assert row.name == "Engineering"
                assert row.ip == "203.0.113.42"
                assert row.user_agent == "Mozilla/5.0 test"
        finally:
            await _drop_tenant(SessionMaker, tenant_id)


# ---------------------------------------------------------------------------
# Immutability: UPDATE and DELETE must raise SQLSTATE AU001.
# ---------------------------------------------------------------------------


class TestAuditLogImmutability:
    @pytest.mark.asyncio
    async def test_update_raises_au001(self, test_engine):
        """The trigger must block any UPDATE on audit_log — even one
        issued via the ORM. SQLAlchemy compiles ``sa.update(AuditLog)``
        down to a regular UPDATE statement that hits the BEFORE UPDATE
        trigger identically to a raw DML statement, which is exactly
        the immutability invariant we want to pin."""
        SessionMaker = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        tenant_id = await _seed_tenant(SessionMaker)
        try:
            row_id = str(uuid.uuid4())
            async with SessionMaker() as session:
                async with session.begin():
                    session.add(
                        AuditLog(
                            id=row_id,
                            tenant_id=tenant_id,
                            event_type="test.event",
                            resource_type="test",
                            resource_id="r1",
                        )
                    )

            with pytest.raises(DBAPIError) as excinfo:
                async with SessionMaker() as session:
                    async with session.begin():
                        await session.execute(
                            sa.update(AuditLog)
                            .where(AuditLog.id == row_id)
                            .values(event_type="tampered")
                        )
            sqlstate = getattr(excinfo.value.orig, "sqlstate", None)
            assert sqlstate == "AU001", (
                f"UPDATE on audit_log must raise SQLSTATE AU001; got {sqlstate!r}"
            )
        finally:
            await _drop_tenant(SessionMaker, tenant_id)

    @pytest.mark.asyncio
    async def test_delete_raises_au001(self, test_engine):
        """The trigger must block any DELETE on audit_log — same
        rationale as the UPDATE test above; ORM-issued DELETE compiles
        to a normal DELETE statement that the BEFORE DELETE trigger
        intercepts."""
        SessionMaker = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        tenant_id = await _seed_tenant(SessionMaker)
        try:
            row_id = str(uuid.uuid4())
            async with SessionMaker() as session:
                async with session.begin():
                    session.add(
                        AuditLog(
                            id=row_id,
                            tenant_id=tenant_id,
                            event_type="test.event",
                            resource_type="test",
                            resource_id="r1",
                        )
                    )

            with pytest.raises(DBAPIError) as excinfo:
                async with SessionMaker() as session:
                    async with session.begin():
                        await session.execute(
                            sa.delete(AuditLog).where(AuditLog.id == row_id)
                        )
            sqlstate = getattr(excinfo.value.orig, "sqlstate", None)
            assert sqlstate == "AU001", (
                f"DELETE on audit_log must raise SQLSTATE AU001; got {sqlstate!r}"
            )
        finally:
            await _drop_tenant(SessionMaker, tenant_id)

    @pytest.mark.asyncio
    async def test_hard_deleting_the_actor_nulls_actor_user_id(self, test_engine):
        """The FK's ON DELETE SET NULL is the one UPDATE the trigger allows;
        before entry 93 it raised AU001 and no actor could ever be deleted."""
        SessionMaker = async_sessionmaker(bind=test_engine, expire_on_commit=False)
        tenant_id = await _seed_tenant(SessionMaker)
        try:
            user_id, row_id = str(uuid.uuid4()), str(uuid.uuid4())
            async with SessionMaker() as session:
                async with session.begin():
                    session.add(
                        User(
                            id=user_id,
                            tenant_id=tenant_id,
                            email=f"actor-{_unique()}@example.com",
                            status=UserStatusEnum.ACTIVE,
                            created_at=datetime.now(UTC),
                            updated_at=datetime.now(UTC),
                        )
                    )
                    await session.flush()
                    session.add(
                        AuditLog(
                            id=row_id,
                            tenant_id=tenant_id,
                            actor_user_id=user_id,
                            event_type="test.event",
                            resource_type="test",
                            resource_id="r1",
                        )
                    )

            async with SessionMaker() as session:
                async with session.begin():
                    await session.execute(sa.delete(User).where(User.id == user_id))

            async with SessionMaker() as session:
                row = await session.get(AuditLog, row_id)
            assert row.actor_user_id is None
            assert row.event_type == "test.event"

            # Clearing the actor together with any other column is still blocked.
            with pytest.raises(DBAPIError) as excinfo:
                async with SessionMaker() as session:
                    async with session.begin():
                        await session.execute(
                            sa.update(AuditLog)
                            .where(AuditLog.id == row_id)
                            .values(event_type="tampered")
                        )
            assert getattr(excinfo.value.orig, "sqlstate", None) == "AU001"
        finally:
            await _drop_tenant(SessionMaker, tenant_id)


# ---------------------------------------------------------------------------
# PII tagging: ip_address and user_agent must carry pii:* comments so the
# anonymization runner (slice C6) can find and anonymize them.
# ---------------------------------------------------------------------------


class TestAuditLogPiiTagging:
    @pytest.mark.asyncio
    async def test_ip_address_is_tagged_pii(self, test_engine):
        """``ip_address`` must carry COMMENT 'pii:ipaddress' for the anonymizer."""
        async with test_engine.connect() as conn:
            comment = await conn.scalar(
                sa.text(
                    "SELECT col_description("
                    "  'audit_log'::regclass, "
                    "  (SELECT ordinal_position FROM information_schema.columns "
                    "   WHERE table_name='audit_log' AND column_name='ip_address')"
                    ")"
                )
            )
        assert comment == "pii:ipaddress", (
            f"audit_log.ip_address must carry COMMENT 'pii:ipaddress'; "
            f"got {comment!r}. The anonymization runner reads pg_description "
            "to discover PII columns."
        )

    @pytest.mark.asyncio
    async def test_user_agent_is_tagged_pii(self, test_engine):
        """``user_agent`` must carry COMMENT 'pii:freetext' for the anonymizer."""
        async with test_engine.connect() as conn:
            comment = await conn.scalar(
                sa.text(
                    "SELECT col_description("
                    "  'audit_log'::regclass, "
                    "  (SELECT ordinal_position FROM information_schema.columns "
                    "   WHERE table_name='audit_log' AND column_name='user_agent')"
                    ")"
                )
            )
        assert comment == "pii:freetext", (
            f"audit_log.user_agent must carry COMMENT 'pii:freetext'; "
            f"got {comment!r}."
        )
