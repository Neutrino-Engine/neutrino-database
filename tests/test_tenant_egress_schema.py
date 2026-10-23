"""tenant egress allow-list columns (NC-793 F1): defaults + egress_mode CHECK."""
import uuid

import pytest
import sqlalchemy as sa


@pytest.mark.asyncio
async def test_egress_defaults_and_mode_check(test_engine):
    suffix = uuid.uuid4().hex[:12]
    tid = str(uuid.uuid4())
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(
                sa.text("INSERT INTO tenant (id, name, org_external_id, status) "
                        "VALUES (:id, :n, :o, 'ACTIVE')"),
                {"id": tid, "n": f"Eg-{suffix}", "o": f"eg-{suffix}"},
            )
            row = (await conn.execute(
                sa.text("SELECT egress_allowed_domains, egress_allowed_email_domains, "
                        "egress_mode FROM tenant WHERE id = :id"), {"id": tid},
            )).one()
            assert row == ([], [], "monitor")

            await conn.execute(sa.text("UPDATE tenant SET egress_mode = 'enforce' WHERE id = :id"), {"id": tid})
            nested = await conn.begin_nested()
            with pytest.raises(sa.exc.IntegrityError):
                await conn.execute(sa.text("UPDATE tenant SET egress_mode = 'block' WHERE id = :id"), {"id": tid})
            await nested.rollback()
            nested = await conn.begin_nested()
            with pytest.raises(sa.exc.IntegrityError):
                await conn.execute(sa.text("UPDATE tenant SET egress_mode = NULL WHERE id = :id"), {"id": tid})
            await nested.rollback()
        finally:
            await trans.rollback()
