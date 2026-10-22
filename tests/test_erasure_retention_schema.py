"""Schema tests for NC-795 G-21 / G-44: erasure_request + tenant retention."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from neutrino_database.models import tables


async def _tenant(conn) -> str:
    tid = str(uuid.uuid4())
    await conn.execute(
        sa.insert(tables.tenant).values(
            id=tid, name="t", org_external_id=f"org-{tid}", status="ACTIVE"
        )
    )
    return tid


@pytest.mark.asyncio
async def test_retention_columns_nullable_and_positive(test_engine):
    async with test_engine.connect() as conn:
        tid = await _tenant(conn)
        row = (await conn.execute(
            sa.select(tables.tenant.c.retention_chat_days).where(tables.tenant.c.id == tid)
        )).scalar_one()
        assert row is None
        await conn.execute(
            sa.update(tables.tenant).where(tables.tenant.c.id == tid).values(retention_trace_days=30)
        )
        with pytest.raises(IntegrityError):
            await conn.execute(
                sa.update(tables.tenant).where(tables.tenant.c.id == tid).values(retention_chat_days=0)
            )
        await conn.rollback()


@pytest.mark.asyncio
async def test_one_open_request_per_target(test_engine):
    async with test_engine.connect() as conn:
        tid = await _tenant(conn)
        target = str(uuid.uuid4())
        ins = sa.insert(tables.erasure_request)
        await conn.execute(ins.values(id=str(uuid.uuid4()), tenant_id=tid, scope="user", target_id=target))
        with pytest.raises(IntegrityError):
            await conn.execute(ins.values(id=str(uuid.uuid4()), tenant_id=tid, scope="user", target_id=target))
        await conn.rollback()


@pytest.mark.asyncio
async def test_closed_request_allows_a_new_one(test_engine):
    async with test_engine.connect() as conn:
        tid = await _tenant(conn)
        target = str(uuid.uuid4())
        ins = sa.insert(tables.erasure_request)
        await conn.execute(ins.values(
            id=str(uuid.uuid4()), tenant_id=tid, scope="user", target_id=target, status="cancelled"
        ))
        await conn.execute(ins.values(id=str(uuid.uuid4()), tenant_id=tid, scope="user", target_id=target))
        with pytest.raises(IntegrityError):
            await conn.execute(ins.values(
                id=str(uuid.uuid4()), tenant_id=tid, scope="bogus", target_id=str(uuid.uuid4())
            ))
        await conn.rollback()
