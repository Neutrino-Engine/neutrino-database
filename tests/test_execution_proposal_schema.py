"""ITOps merge §4.1 — the proposal is the unit of approval.

The row has to freeze everything the decision binds to: the graph, the resolved
inputs and the digest over them. It also has to survive losing the things
around it, so every optional link is nullable, and a decision must never be
inferred from a timeout, so ``expired`` is its own status value. Schema-shape
only; no DB round-trip needed since ``.columns`` is plain SQLAlchemy metadata.
"""

from __future__ import annotations

from neutrino_database.models.enums import ExecutionProposalStatusEnum
from neutrino_database.models.tables import execution_proposal


def test_a_proposal_freezes_the_graph_the_inputs_and_their_digest():
    cols = {c.name for c in execution_proposal.columns}
    assert {"graph", "inputs", "preview", "digest", "expires_at"} <= cols
    for required in ("graph", "digest", "expires_at"):
        assert execution_proposal.columns[required].nullable is False


def test_a_one_off_proposal_needs_no_library_workflow_or_chat():
    for optional in ("workflow_id", "revision_id", "chat_id", "run_id"):
        assert execution_proposal.columns[optional].nullable is True


def test_a_timeout_is_not_an_approval():
    values = {e.value for e in ExecutionProposalStatusEnum}
    assert values == {"pending", "approved", "rejected", "cancelled", "expired"}
    assert execution_proposal.columns["status"].nullable is False


def test_the_inbox_reads_pending_proposals_by_workspace():
    index = {i.name: i for i in execution_proposal.indexes}["ix_execution_proposal_pending"]
    assert [c.name for c in index.columns] == ["workspace_id", "status"]
