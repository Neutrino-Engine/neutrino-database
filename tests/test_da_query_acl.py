"""NC-730 — the shared DA query-authorization rule.

Pins the options connector-service relies on at the execution boundary
(admin bypass that still honours M10, uncatalogued names, exact-case
matching for document stores, refusal of folded-name collisions) on top
of the grant semantics share links already depend on.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from neutrino_database.access.da_query_acl import (
    QueryTarget,
    can_user_read_query_targets,
    walk_grants,
)
from neutrino_database.models.enums import (
    DAAccessEffectEnum,
    DAAccessResourceTypeEnum,
    TenantStatusEnum,
    UserStatusEnum,
    WorkspaceStatusEnum,
)
from neutrino_database.models.orm import (
    DACatalogColumn,
    DACatalogSchema,
    DACatalogTable,
    Tenant,
    User,
    Workspace,
    WorkspaceDAAccessGrant,
    WorkspaceMember,
)


# ---------------------------------------------------------------------------
# walk_grants — pure
# ---------------------------------------------------------------------------

ALLOW = DAAccessEffectEnum.ALLOW.value
DENY = DAAccessEffectEnum.DENY.value


def test_walk_grants_inherits_the_member_default_when_nothing_is_explicit():
    assert walk_grants({}, chain=[("table", "t")], member_default=True) is True
    assert walk_grants({}, chain=[("table", "t")], member_default=False) is False


def test_walk_grants_deny_anywhere_beats_allow_at_the_leaf():
    grants = {("column", "c"): ALLOW, ("schema", "s"): DENY}
    chain = [("column", "c"), ("table", "t"), ("schema", "s")]
    assert walk_grants(grants, chain=chain, member_default=True) is False


def test_walk_grants_allow_overrides_a_non_member_default():
    grants = {("table", "t"): ALLOW}
    assert walk_grants(grants, chain=[("table", "t")], member_default=False) is True


# ---------------------------------------------------------------------------
# can_user_read_query_targets — against the real schema
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(test_engine):
    async with test_engine.connect() as connection:
        outer = await connection.begin()
        session = async_sessionmaker(bind=connection, expire_on_commit=False)()
        try:
            yield session
        finally:
            await session.close()
            if outer.is_active:
                await outer.rollback()


@pytest_asyncio.fixture
async def fx(db_session):
    """public.orders(id, customer_email), public.salaries(id, ssn) and a
    document-store pair hr.Staff / hr.staff on one connection; bob is a
    member, carol is not."""
    s = db_session
    tenant_id, admin_id, bob_id, carol_id = (str(uuid4()) for _ in range(4))
    workspace_id, conn_id = str(uuid4()), str(uuid4())
    s.add(
        Tenant(
            id=tenant_id,
            name=f"acme-{tenant_id[:8]}",
            org_external_id=f"org-{tenant_id[:8]}",
            status=TenantStatusEnum.ACTIVE,
        )
    )
    await s.flush()
    s.add_all(
        [
            User(id=u, tenant_id=tenant_id, email=f"{u[:8]}@example.com",
                 status=UserStatusEnum.ACTIVE)
            for u in (admin_id, bob_id, carol_id)
        ]
    )
    await s.flush()
    s.add(
        Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name=f"main-{workspace_id[:8]}",
            status=WorkspaceStatusEnum.ACTIVE,
            created_by=admin_id,
        )
    )
    await s.flush()
    s.add(
        WorkspaceMember(
            id=str(uuid4()), workspace_id=workspace_id, user_id=bob_id,
            is_workspace_admin=False,
        )
    )
    await s.execute(
        text(
            "INSERT INTO integration (id, tenant_id, owner_kind, provider, "
            "display_name, vault_secret_id, identity_kind, auth_kind, "
            "capabilities, status, created_by, metadata, created_at, updated_at) "
            "VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'tenant', 'postgres', "
            "'test_conn', 'unused/for/test', 'service_account', 'basic', "
            "'{query}'::text[], 'active', CAST(:cb AS uuid), '{}'::jsonb, "
            "now(), now())"
        ),
        {"id": conn_id, "tid": tenant_id, "cb": admin_id},
    )
    await s.flush()

    ids: dict[str, str] = {}

    async def schema(name):
        ids[name] = str(uuid4())
        s.add(DACatalogSchema(id=ids[name], da_connection_id=conn_id,
                              schema_name=name, is_pii=False, is_restricted=False))
        await s.flush()

    async def table(key, schema_key, name, cols):
        ids[key] = str(uuid4())
        s.add(DACatalogTable(id=ids[key], da_catalog_schema_id=ids[schema_key],
                             table_name=name, is_pii=False, is_restricted=False))
        await s.flush()
        for pos, col in enumerate(cols, start=1):
            ids[f"{key}.{col}"] = str(uuid4())
            s.add(DACatalogColumn(id=ids[f"{key}.{col}"], da_catalog_table_id=ids[key],
                                  column_name=col, data_type="text",
                                  ordinal_position=pos, nullable=True,
                                  is_pii=False, is_restricted=False))
        await s.flush()

    await schema("public")
    await schema("hr")
    await table("orders", "public", "orders", ["id", "customer_email"])
    await table("salaries", "public", "salaries", ["id", "ssn"])
    await table("Staff", "hr", "Staff", ["name"])
    await table("staff", "hr", "staff", ["name", "salary"])

    async def grant(resource_type, key, effect, user=bob_id):
        s.add(WorkspaceDAAccessGrant(
            id=str(uuid4()), workspace_id=workspace_id, user_id=user,
            resource_type=resource_type, resource_id=ids[key], effect=effect,
            created_by=admin_id,
        ))
        await s.flush()

    return {
        "ws": workspace_id, "conn": conn_id, "bob": bob_id, "carol": carol_id,
        "ids": ids, "grant": grant,
    }


async def _check(db_session, fx, targets, **kw):
    kw.setdefault("user_id", fx["bob"])
    return await can_user_read_query_targets(
        db_session,
        workspace_id=fx["ws"],
        connection_id=fx["conn"],
        targets=targets,
        **kw,
    )


ORDERS = QueryTarget("public", "orders")
SALARIES = QueryTarget("public", "salaries")


async def test_member_reads_a_table_with_no_grants(db_session, fx):
    assert await _check(db_session, fx, [ORDERS], columns=["id"]) is True


async def test_table_deny_refuses_the_member(db_session, fx):
    await fx["grant"](DAAccessResourceTypeEnum.TABLE, "salaries", DAAccessEffectEnum.DENY)
    assert await _check(db_session, fx, [SALARIES], columns=["id"]) is False
    assert await _check(db_session, fx, [ORDERS], columns=["id"]) is True


async def test_schema_deny_refuses_every_table_in_it(db_session, fx):
    await fx["grant"](DAAccessResourceTypeEnum.SCHEMA, "public", DAAccessEffectEnum.DENY)
    assert await _check(db_session, fx, [ORDERS], columns=["id"]) is False


async def test_schema_deny_beats_a_table_allow(db_session, fx):
    await fx["grant"](DAAccessResourceTypeEnum.SCHEMA, "public", DAAccessEffectEnum.DENY)
    await fx["grant"](DAAccessResourceTypeEnum.TABLE, "orders", DAAccessEffectEnum.ALLOW)
    assert await _check(db_session, fx, [ORDERS], columns=["id"]) is False


async def test_column_deny_refuses_star_but_not_other_columns(db_session, fx):
    await fx["grant"](DAAccessResourceTypeEnum.COLUMN, "salaries.ssn", DAAccessEffectEnum.DENY)
    assert await _check(db_session, fx, [SALARIES], columns=["ssn"]) is False
    assert await _check(db_session, fx, [SALARIES], columns=None) is False
    assert await _check(db_session, fx, [SALARIES], columns=["id"]) is True


async def test_non_member_is_refused_and_missing_user_is_refused(db_session, fx):
    assert await _check(db_session, fx, [ORDERS], columns=["id"], user_id=fx["carol"]) is False
    assert await _check(db_session, fx, [ORDERS], columns=["id"], user_id=None) is False


async def test_unqualified_name_needs_a_fallback_schema(db_session, fx):
    bare = QueryTarget(None, "orders")
    assert await _check(db_session, fx, [bare], columns=["id"]) is False
    assert await _check(
        db_session, fx, [bare], columns=["id"], fallback_schema_name="public"
    ) is True


async def test_uncatalogued_table_is_refused_for_members(db_session, fx):
    assert await _check(
        db_session, fx, [QueryTarget("public", "nope")], columns=["id"]
    ) is False


async def test_admin_bypass_skips_grants(db_session, fx):
    await fx["grant"](DAAccessResourceTypeEnum.TABLE, "salaries", DAAccessEffectEnum.DENY)
    assert await _check(
        db_session, fx, [SALARIES], columns=None, apply_grants=False,
        require_catalogued=False, user_id=fx["carol"],
    ) is True


async def test_admin_bypass_still_honours_pii(db_session, fx):
    await db_session.execute(
        text("UPDATE da_catalog_column SET is_pii = true WHERE id = CAST(:id AS uuid)"),
        {"id": fx["ids"]["salaries.ssn"]},
    )
    kw = dict(apply_grants=False, require_catalogued=False)
    assert await _check(db_session, fx, [SALARIES], columns=None, **kw) is False
    assert await _check(db_session, fx, [SALARIES], columns=["ssn"], **kw) is False
    assert await _check(db_session, fx, [SALARIES], columns=["id"], **kw) is True


async def test_admin_bypass_lets_uncatalogued_names_through(db_session, fx):
    assert await _check(
        db_session, fx, [QueryTarget("public", "nope")], columns=None,
        apply_grants=False, require_catalogued=False,
    ) is True


async def test_folded_name_matching_two_catalog_rows_is_refused(db_session, fx):
    # hr.Staff and hr.staff both fold to hr.staff.
    assert await _check(
        db_session, fx, [QueryTarget("hr", "staff")], columns=["name"]
    ) is False


async def test_case_sensitive_match_picks_the_exact_collection(db_session, fx):
    await fx["grant"](DAAccessResourceTypeEnum.TABLE, "staff", DAAccessEffectEnum.DENY)
    kw = dict(columns=None, case_sensitive=True)
    assert await _check(db_session, fx, [QueryTarget("hr", "Staff")], **kw) is True
    assert await _check(db_session, fx, [QueryTarget("hr", "staff")], **kw) is False
    assert await _check(db_session, fx, [QueryTarget("hr", "STAFF")], **kw) is False


async def test_empty_target_list_is_refused(db_session, fx):
    assert await _check(db_session, fx, [], columns=None) is False


@pytest.mark.parametrize("missing", ["schema", "table"])
async def test_blank_names_are_refused(db_session, fx, missing):
    target = QueryTarget(None if missing == "schema" else "public",
                         "" if missing == "table" else "orders")
    assert await _check(db_session, fx, [target], columns=["id"]) is False
