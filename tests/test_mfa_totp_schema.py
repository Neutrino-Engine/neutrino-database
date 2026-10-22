"""mfa_totp + tenant.require_mfa_local (NC-795 G-30)."""
import uuid

import pytest
import sqlalchemy as sa


@pytest.mark.asyncio
async def test_mfa_totp_owner_check_uniqueness_and_defaults(test_engine):
    suffix = uuid.uuid4().hex[:12]
    tid, uid = str(uuid.uuid4()), str(uuid.uuid4())
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(sa.text(
                "INSERT INTO tenant (id, name, org_external_id, status) VALUES (:id, :n, :o, 'ACTIVE')"),
                {"id": tid, "n": f"M-{suffix}", "o": f"m-{suffix}"})
            assert (await conn.execute(sa.text(
                "SELECT require_mfa_local FROM tenant WHERE id = :id"), {"id": tid})).scalar() is False
            await conn.execute(sa.text(
                "INSERT INTO \"user\" (id, tenant_id, email, status) VALUES (:id, :t, :e, 'ACTIVE')"),
                {"id": uid, "t": tid, "e": f"m-{suffix}@example.com"})
            await conn.execute(sa.text(
                "INSERT INTO mfa_totp (id, user_id, secret_encrypted) VALUES (:id, :u, 'x')"),
                {"id": str(uuid.uuid4()), "u": uid})
            row = (await conn.execute(sa.text(
                "SELECT recovery_code_hashes, enrolled_at, last_used_step FROM mfa_totp WHERE user_id = :u"),
                {"u": uid})).one()
            assert row == ([], None, None)

            for sql, params in (
                ("INSERT INTO mfa_totp (id, user_id, secret_encrypted) VALUES (:id, :u, 'y')", {"u": uid}),
                ("INSERT INTO mfa_totp (id, secret_encrypted) VALUES (:id, 'z')", {}),
            ):
                nested = await conn.begin_nested()
                with pytest.raises(sa.exc.IntegrityError):
                    await conn.execute(sa.text(sql), {"id": str(uuid.uuid4()), **params})
                await nested.rollback()

            await conn.execute(sa.text("DELETE FROM \"user\" WHERE id = :u"), {"u": uid})
            assert (await conn.execute(sa.text(
                "SELECT count(*) FROM mfa_totp WHERE user_id = :u"), {"u": uid})).scalar() == 0
        finally:
            await trans.rollback()
