"""NC-723: LLM providers with no usable context window get the 500k default.

Providers created before NC-416 have no window at all. A provider whose window
is missing, null, 0 or below, or not a number is set to 500000, the default the
form and agent-platform use. Any other value was set by an admin and is left
alone, including the old form default of 100000.

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

_DEFAULT_CONTEXT_WINDOW = 500000

# Numbers, and integer strings agent-platform's int() accepts, count when
# above 0. Only those are cast, so a string like "" can't abort the migration.
_NO_USABLE_WINDOW = """
    CASE WHEN jsonb_typeof(model_config->'context_window') = 'number'
              OR model_config->>'context_window' ~ '^\\s*[+-]?[0-9]+\\s*$'
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
                'context_window', {_DEFAULT_CONTEXT_WINDOW},
                'context_window_migrated_from',
                    coalesce(model_config->'context_window', 'null'::jsonb)
            )
        WHERE provider_category = 'llm'
          AND {_NO_USABLE_WINDOW}
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
