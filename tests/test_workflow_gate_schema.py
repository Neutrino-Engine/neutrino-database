"""workflow_test_case / workflow_gate_run (NC-797 C1): defaults, CHECKs, cascade."""
import uuid

import pytest
import sqlalchemy as sa


@pytest.mark.asyncio
async def test_workflow_gate_tables(test_engine):
    s = uuid.uuid4().hex[:12]
    tid, wid, wf, vid, case_id, gid = (str(uuid.uuid4()) for _ in range(6))
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            q = lambda sql, **kw: conn.execute(sa.text(sql), kw)  # noqa: E731
            await q("INSERT INTO tenant (id, name, org_external_id, status) VALUES (:id, :n, :o, 'ACTIVE')",
                    id=tid, n=f"G-{s}", o=f"g-{s}")
            await q("INSERT INTO workspace (id, tenant_id, name) VALUES (:id, :t, :n)",
                    id=wid, t=tid, n=f"w-{s}")
            await q("INSERT INTO workflow (id, tenant_id, workspace_id, name) VALUES (:id, :t, :w, 'wf')",
                    id=wf, t=tid, w=wid)
            await q("INSERT INTO workflow_version (id, tenant_id, workspace_id, workflow_id, version, graph, content_hash)"
                    " VALUES (:id, :t, :w, :wf, 1, '{}'::jsonb, 'h')", id=vid, t=tid, w=wid, wf=wf)
            await q("INSERT INTO workflow_test_case (id, tenant_id, workspace_id, workflow_id, name)"
                    " VALUES (:id, :t, :w, :wf, 'c')", id=case_id, t=tid, w=wid, wf=wf)
            await q("INSERT INTO workflow_gate_run (id, tenant_id, workspace_id, workflow_id, version_id)"
                    " VALUES (:id, :t, :w, :wf, :v)", id=gid, t=tid, w=wid, wf=wf, v=vid)
            case = (await q("SELECT input, expectations, kind FROM workflow_test_case WHERE id = :id", id=case_id)).one()
            assert case == ({}, [], "normal")
            gate = (await q("SELECT status, results, summary FROM workflow_gate_run WHERE id = :id", id=gid)).one()
            assert gate == ("running", [], {})

            for sql in ("UPDATE workflow_test_case SET kind = 'evil' WHERE id = :id",
                        "UPDATE workflow_gate_run SET status = 'queued' WHERE id = :id"):
                nested = await conn.begin_nested()
                with pytest.raises(sa.exc.IntegrityError):
                    await q(sql, id=case_id if "case" in sql else gid)
                await nested.rollback()

            await q("DELETE FROM workflow WHERE id = :id", id=wf)
            left = (await q("SELECT (SELECT count(*) FROM workflow_test_case WHERE workflow_id = :wf)"
                            " + (SELECT count(*) FROM workflow_gate_run WHERE workflow_id = :wf)", wf=wf)).scalar()
            assert left == 0
        finally:
            await trans.rollback()
