"""tenant.llm_allowed_models (NC-795 G-42): default empty, array of text."""
import uuid

import pytest
import sqlalchemy as sa


@pytest.mark.asyncio
async def test_llm_allowed_models_defaults_empty(test_engine):
    suffix = uuid.uuid4().hex[:12]
    tid = str(uuid.uuid4())
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(
                sa.text("INSERT INTO tenant (id, name, org_external_id, status) "
                        "VALUES (:id, :n, :o, 'ACTIVE')"),
                {"id": tid, "n": f"Lm-{suffix}", "o": f"lm-{suffix}"},
            )
            row = (await conn.execute(
                sa.text("SELECT llm_allowed_models FROM tenant WHERE id = :id"), {"id": tid},
            )).scalar()
            assert row == []
            await conn.execute(
                sa.text("UPDATE tenant SET llm_allowed_models = ARRAY['openai/gpt-4o', 'anthropic/*'] WHERE id = :id"),
                {"id": tid},
            )
            row = (await conn.execute(
                sa.text("SELECT llm_allowed_models FROM tenant WHERE id = :id"), {"id": tid},
            )).scalar()
            assert row == ["openai/gpt-4o", "anthropic/*"]
            nested = await conn.begin_nested()
            with pytest.raises(sa.exc.IntegrityError):
                await conn.execute(sa.text("UPDATE tenant SET llm_allowed_models = NULL WHERE id = :id"), {"id": tid})
            await nested.rollback()
        finally:
            await trans.rollback()
