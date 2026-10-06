"""NC-723: LLM providers saved at the old flat 100k context window get their
model's real window.

The provider form used to save 100000 for every model. A provider still at
exactly 100000 is moved to its model's window, matching the new form defaults
(agent-platform ``model_context_window``). Any other value was chosen by an
admin and is left alone. Each moved row is marked so the downgrade restores
only those.

Revision ID: e6f0a4b8c2d3
Revises: d5e9f3a7b1c2
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "e6f0a4b8c2d3"
down_revision: Union[str, Sequence[str], None] = "d5e9f3a7b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MODEL = "lower(coalesce(model_config->>'default_model', ''))"
_WINDOW = f"""
    CASE
        WHEN service_type IN ('claude', 'bedrock') THEN 200000
        WHEN service_type = 'gemini' THEN 1000000
        WHEN service_type = 'azure_openai' AND {_MODEL} LIKE 'gpt-5%' THEN 922000
        WHEN service_type = 'azure_openai' THEN 200000
        WHEN service_type = 'openai' AND {_MODEL} ~ '^o[1-9]' THEN 200000
        WHEN service_type = 'openai' THEN 128000
    END
"""


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE providers
        SET model_config = model_config
            || jsonb_build_object(
                'context_window', {_WINDOW},
                'context_window_migrated_from', 100000
            )
        WHERE provider_category = 'llm'
          AND model_config->>'context_window' = '100000'
          AND service_type IN ('claude', 'bedrock', 'gemini', 'azure_openai', 'openai')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE providers
        SET model_config = (model_config - 'context_window_migrated_from')
            || jsonb_build_object('context_window', 100000)
        WHERE provider_category = 'llm'
          AND model_config ? 'context_window_migrated_from'
        """
    )
