"""workspace_llm_governance (NC-892): table shape, migration copy up and down, one head.

Every test runs in one transaction and rolls back, so the DDL the migration
runs (drop/create table) never leaks into other tests.
"""
import importlib.util
import json
import pathlib
import uuid

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

ROOT = pathlib.Path(__file__).resolve().parents[1]
REV = "a9c3e5f7b1d2"


def _migration():
    path = next((ROOT / "alembic" / "versions").glob(f"{REV}_*.py"))
    spec = importlib.util.spec_from_file_location("nc892_migration", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(sync_conn, fn):
    ctx = MigrationContext.configure(sync_conn)
    with Operations.context(ctx):
        fn()


async def _seed(conn):
    s = uuid.uuid4().hex[:12]
    q = lambda sql, **kw: conn.execute(sa.text(sql), kw)  # noqa: E731
    tid = str(uuid.uuid4())
    await q("INSERT INTO tenant (id, name, org_external_id, status) VALUES (:id, :n, :o, 'ACTIVE')",
            id=tid, n=f"G-{s}", o=f"g-{s}")
    ws = {}
    for k in "ABC":
        ws[k] = str(uuid.uuid4())
        await q("INSERT INTO workspace (id, tenant_id, name) VALUES (:id, :t, :n)", id=ws[k], t=tid, n=f"{k}-{s}")

    async def prov(w, name, mc, active=True, deleted=False):
        pid = str(uuid.uuid4())
        await q("INSERT INTO providers (id, workspace_id, provider_category, service_type, display_name,"
                " encrypted_value, model_config, is_active, is_deleted)"
                " VALUES (:id, :w, 'llm', 'openai', :n, 'x', CAST(:mc AS jsonb), :a, :d)",
                id=pid, w=w, n=name, mc=json.dumps(mc), a=active, d=deleted)
        return pid

    gov_a = {"enabled": True, "entities": ["EMAIL"], "custom_patterns": []}
    pa = await prov(ws["A"], "a", {"model": "gpt", "governance": gov_a})
    await prov(ws["C"], "c1", {"governance": {"enabled": False}}, active=False)
    await prov(ws["C"], "c2", {"governance": {"enabled": False}}, deleted=True)
    return ws, pa, gov_a


@pytest.mark.asyncio
async def test_table_shape(test_engine):
    async with test_engine.connect() as conn:
        def shape(sync_conn):
            i = sa.inspect(sync_conn)
            cols = {c["name"]: c for c in i.get_columns("workspace_llm_governance")}
            return cols, i.get_pk_constraint("workspace_llm_governance"), i.get_foreign_keys("workspace_llm_governance")
        cols, pk, fks = await conn.run_sync(shape)
    assert set(cols) == {"workspace_id", "governance", "updated_at"}
    assert isinstance(cols["workspace_id"]["type"], sa.UUID)
    assert cols["governance"]["type"].__class__.__name__ == "JSONB"
    assert isinstance(cols["updated_at"]["type"], sa.TIMESTAMP) and cols["updated_at"]["type"].timezone
    assert not any(c["nullable"] for c in cols.values())
    assert cols["updated_at"]["default"]
    assert pk["constrained_columns"] == ["workspace_id"]
    assert [(f["referred_table"], f["options"].get("ondelete")) for f in fks] == [("workspace", "CASCADE")]


@pytest.mark.asyncio
async def test_upgrade_copies_active_provider_governance(test_engine):
    mig = _migration()
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(sa.text("DROP TABLE workspace_llm_governance"))
            ws, _, gov_a = await _seed(conn)
            await conn.run_sync(_run, mig.upgrade)
            rows = (await conn.execute(
                sa.text("SELECT workspace_id::text, governance FROM workspace_llm_governance"
                        " WHERE workspace_id = ANY(CAST(:w AS uuid[]))"),
                {"w": list(ws.values())})).all()
            assert rows == [(ws["A"], gov_a)]
        finally:
            await trans.rollback()


@pytest.mark.asyncio
async def test_downgrade_restores_provider_governance(test_engine):
    mig = _migration()
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(sa.text("DROP TABLE workspace_llm_governance"))
            ws, pa, _ = await _seed(conn)
            await conn.run_sync(_run, mig.upgrade)
            new = {"enabled": False, "entities": []}
            await conn.execute(sa.text("UPDATE workspace_llm_governance SET governance = CAST(:g AS jsonb)"
                                       " WHERE workspace_id = :w"), {"g": json.dumps(new), "w": ws["A"]})
            await conn.run_sync(_run, mig.downgrade)
            mc = (await conn.execute(sa.text("SELECT model_config FROM providers WHERE id = :id"),
                                     {"id": pa})).scalar()
            assert mc == {"model": "gpt", "governance": new}
            gone = (await conn.execute(sa.text("SELECT to_regclass('workspace_llm_governance')"))).scalar()
            assert gone is None
        finally:
            await trans.rollback()


def test_single_alembic_head():
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    assert ScriptDirectory.from_config(cfg).get_heads() == [REV]
