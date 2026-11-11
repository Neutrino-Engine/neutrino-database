"""incident_report (NC-877): defaults, unique snapshot and version, cascade."""
import uuid

import pytest
import sqlalchemy as sa


@pytest.mark.asyncio
async def test_incident_report_table(test_engine):
    s = uuid.uuid4().hex[:12]
    tid, wid = str(uuid.uuid4()), str(uuid.uuid4())
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            q = lambda sql, **kw: conn.execute(sa.text(sql), kw)  # noqa: E731
            await q("INSERT INTO tenant (id, name, org_external_id, status) VALUES (:id, :n, :o, 'ACTIVE')",
                    id=tid, n=f"I-{s}", o=f"i-{s}")
            await q("INSERT INTO workspace (id, tenant_id, name) VALUES (:id, :t, :n)",
                    id=wid, t=tid, n=f"w-{s}")
            ins = ("INSERT INTO incident_report (id, tenant_id, workspace_id, ticket_id, version, kind, tier, snapshot_hash)"
                   " VALUES (:id, :t, :w, 2127821, :v, 'initial', 'report', :h)")
            rid = str(uuid.uuid4())
            await q(ins, id=rid, t=tid, w=wid, v=1, h="a")
            row = (await q("SELECT reasons, sent_at FROM incident_report WHERE id = :id", id=rid)).one()
            assert row == ([], None)

            for v, h in ((2, "a"), (1, "b")):  # same snapshot, then same version
                nested = await conn.begin_nested()
                with pytest.raises(sa.exc.IntegrityError):
                    await q(ins, id=str(uuid.uuid4()), t=tid, w=wid, v=v, h=h)
                await nested.rollback()

            await q("DELETE FROM workspace WHERE id = :id", id=wid)
            left = (await q("SELECT count(*) FROM incident_report WHERE workspace_id = :w", w=wid)).scalar()
            assert left == 0
        finally:
            await trans.rollback()
