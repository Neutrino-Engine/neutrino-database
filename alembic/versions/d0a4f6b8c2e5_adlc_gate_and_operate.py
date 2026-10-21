"""ADLC WS4 + WS5: gate v2, shadow runs, feedback queue, retention, run cap.

WS4:
- ``studio_gate_run`` holds one test-suite execution, and versions point at the
  run that admitted them (``gate_run_id``).
- Test cases gain ``trials``, ``judge_rubric``, ``kind`` and ``source_run_id``.
- ``studio_run.is_shadow`` / ``shadow_of_run_id``; ``studio_run.status`` gains ``queued``.

WS5:
- ``run_feedback`` (thumbs + review queue).
- ``tenant.run_retention_days`` / ``sensitive_retention_days`` /
  ``max_concurrent_runs``.

No backfill. The defaults (1 trial, 180/30 days, a cap of 10) change nothing
observable for existing data until the sweeps and gates are switched on.

Revision ID: d0a4f6b8c2e5
Revises: c9f3e5a7b1d4
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "d0a4f6b8c2e5"
down_revision: Union[str, Sequence[str], None] = "c9f3e5a7b1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RUN_STATUSES_OLD = ("'planning', 'dispatching', 'waiting_approval', 'paused', 'finishing', "
                     "'completed', 'failed', 'cancelled'")
# WS5 (D41): a run waiting for a tenant slot is 'queued'.
_RUN_STATUSES_NEW = "'queued', " + _RUN_STATUSES_OLD


def _uuid(name, fk=None, ondelete=None, nullable=True, **kw):
    args = [sa.ForeignKey(fk, ondelete=ondelete)] if fk else []
    return sa.Column(name, UUID(as_uuid=False), *args, nullable=nullable, **kw)


def upgrade() -> None:
    op.add_column("tenant", sa.Column("run_retention_days", sa.Integer(), nullable=False, server_default=sa.text("180")))
    op.add_column("tenant", sa.Column("sensitive_retention_days", sa.Integer(), nullable=False, server_default=sa.text("30")))
    op.add_column("tenant", sa.Column("max_concurrent_runs", sa.Integer(), nullable=False, server_default=sa.text("10")))

    op.drop_constraint("ck_studio_run_status", "studio_run", type_="check")
    op.create_check_constraint("ck_studio_run_status", "studio_run", f"status IN ({_RUN_STATUSES_NEW})")
    op.add_column("studio_run", sa.Column("is_shadow", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("studio_run", _uuid("shadow_of_run_id", "studio_run.id", "SET NULL"))

    op.add_column("studio_test_case", sa.Column("trials", sa.Integer(), nullable=False, server_default=sa.text("1")))
    op.add_column("studio_test_case", sa.Column("judge_rubric", sa.Text(), nullable=True))
    op.add_column("studio_test_case", sa.Column("kind", sa.String(16), nullable=False, server_default=sa.text("'regular'")))
    op.add_column("studio_test_case", _uuid("source_run_id"))

    op.create_table(
        "studio_gate_run",
        _uuid("id", nullable=False, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _uuid("tenant_id", "tenant.id", "CASCADE", nullable=False),
        _uuid("workspace_id", "workspace.id", "CASCADE", nullable=False),
        sa.Column("subject_kind", sa.String(8), nullable=False),
        _uuid("subject_id", nullable=False),
        _uuid("version_id"),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("results", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        _uuid("created_by", "user.id", "SET NULL"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("subject_kind IN ('agent','team')", name="ck_studio_gate_run_subject"),
        sa.CheckConstraint("status IN ('queued','running','passed','failed','error')", name="ck_studio_gate_run_status"),
    )
    op.create_index("ix_studio_gate_run_subject", "studio_gate_run", ["subject_kind", "subject_id", "created_at"])
    for table in ("studio_agent_version", "studio_team_version"):
        op.add_column(table, _uuid("gate_run_id"))
        op.create_foreign_key(f"fk_{table}_gate_run", table, "studio_gate_run", ["gate_run_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "run_feedback",
        _uuid("id", nullable=False, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _uuid("tenant_id", "tenant.id", "CASCADE", nullable=False),
        _uuid("workspace_id", "workspace.id", "CASCADE", nullable=False),
        sa.Column("run_kind", sa.String(16), nullable=False),
        _uuid("run_id", nullable=False),
        _uuid("user_id", "user.id", "SET NULL"),
        sa.Column("rating", sa.String(8), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(16), nullable=False, server_default=sa.text("'open'")),
        _uuid("reviewed_by", "user.id", "SET NULL"),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        _uuid("test_case_id", "studio_test_case.id", "SET NULL"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("run_kind IN ('studio','workflow')", name="ck_run_feedback_kind"),
        sa.CheckConstraint("rating IN ('up','down')", name="ck_run_feedback_rating"),
        sa.CheckConstraint("review_status IN ('open','dismissed','converted')", name="ck_run_feedback_review"),
        sa.UniqueConstraint("run_kind", "run_id", "user_id", name="uq_run_feedback_user"),
    )
    op.create_index("ix_run_feedback_queue", "run_feedback", ["workspace_id", "review_status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_run_feedback_queue", table_name="run_feedback")
    op.drop_table("run_feedback")
    for table in ("studio_agent_version", "studio_team_version"):
        op.drop_constraint(f"fk_{table}_gate_run", table, type_="foreignkey")
        op.drop_column(table, "gate_run_id")
    op.drop_index("ix_studio_gate_run_subject", table_name="studio_gate_run")
    op.drop_table("studio_gate_run")
    for col in ("source_run_id", "kind", "judge_rubric", "trials"):
        op.drop_column("studio_test_case", col)
    op.execute("UPDATE studio_run SET status = 'planning' WHERE status = 'queued'")
    op.drop_constraint("ck_studio_run_status", "studio_run", type_="check")
    op.create_check_constraint("ck_studio_run_status", "studio_run", f"status IN ({_RUN_STATUSES_OLD})")
    op.drop_column("studio_run", "shadow_of_run_id")
    op.drop_column("studio_run", "is_shadow")
    for col in ("max_concurrent_runs", "sensitive_retention_days", "run_retention_days"):
        op.drop_column("tenant", col)
