"""ITOps merge §5 — an immutable published revision, and a run needing no
library workflow (S1).

Publication freezes a workflow's draft graph and input contract into
``workflow_revision``; ``workflow.published_revision_id`` points at the row
that is live. Editing the draft never touches a past revision. A one-off run
(S1) has no library workflow behind it at all, so ``workflow_run.workflow_id``
is nullable and the run carries its own ``graph_snapshot``. Schema-shape only;
no DB round-trip needed since ``.columns`` is plain SQLAlchemy metadata.
"""

from __future__ import annotations

from neutrino_database.models.tables import workflow, workflow_revision, workflow_run


def test_a_revision_freezes_a_graph_and_its_inputs():
    cols = {c.name for c in workflow_revision.columns}
    assert {"workflow_id", "graph", "input_schema", "revision_number"} <= cols


def test_a_workflow_points_at_its_published_revision():
    assert "published_revision_id" in {c.name for c in workflow.columns}
    assert workflow.columns["published_revision_id"].nullable is True


def test_a_one_off_run_needs_no_library_workflow():
    assert workflow_run.columns["workflow_id"].nullable is True
    assert "graph_snapshot" in {c.name for c in workflow_run.columns}


def test_revision_numbers_are_unique_per_workflow():
    names = [c.name for c in workflow_revision.constraints if getattr(c, "name", None)]
    assert "uq_workflow_revision_number" in names
