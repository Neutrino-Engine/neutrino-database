"""NC-723: LLM providers at the old flat 100k context window, or with no
usable window, get their model's real window.

The provider form used to save 100000 for every model, and providers created
before NC-416 have no window at all. agent-platform now reads the window only
from model_config (no default), so a provider without one is never compacted.

A provider at exactly 100000, or whose window is missing, null, 0 or below, or
not a number, is moved to its model's window, matching the form defaults
(neutrino-frontend-v3 ``config/llm-providers.ts``). Any other value was chosen
by an admin and is left alone. OpenRouter is skipped: its window comes from the
live catalog, so an admin re-saves those providers.

Each moved row keeps its old value in ``context_window_migrated_from`` (JSON
null when the key was missing), and the downgrade restores exactly that.

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

# Only real numbers are cast; Postgres doesn't fix OR evaluation order, so a
# bare ::numeric on a string value would abort the migration.
_NO_USABLE_WINDOW = """
    CASE WHEN jsonb_typeof(model_config->'context_window') = 'number'
         THEN (model_config->>'context_window')::numeric <= 0
         ELSE true
    END
"""


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE providers
        SET model_config = model_config
            || jsonb_build_object(
                'context_window', {_WINDOW},
                'context_window_migrated_from',
                    coalesce(model_config->'context_window', 'null'::jsonb)
            )
        WHERE provider_category = 'llm'
          AND service_type IN ('claude', 'bedrock', 'gemini', 'azure_openai', 'openai')
          AND (model_config->>'context_window' = '100000' OR {_NO_USABLE_WINDOW})
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE providers
        SET model_config = CASE
                WHEN jsonb_typeof(model_config->'context_window_migrated_from') = 'null'
                THEN model_config - 'context_window' - 'context_window_migrated_from'
                ELSE (model_config - 'context_window_migrated_from')
                    || jsonb_build_object(
                        'context_window', model_config->'context_window_migrated_from'
                    )
            END
        WHERE provider_category = 'llm'
          AND model_config ? 'context_window_migrated_from'
        """
    )
