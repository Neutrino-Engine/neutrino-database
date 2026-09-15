"""Backfill a published revision for every legacy published workflow (ITOps merge §10).

Publication used to mean "this workflow has an active webhook trigger". It now
means ``workflow.published_revision_id`` points at an immutable
``workflow_revision``, and after this change the trigger paths resolve that
pointer instead of reading the mutable draft. Every workflow that was
discoverable as published before therefore needs revision 1, or its existing
webhook URL would stop resolving.

What this migration must NOT do, per spec §10: it executes nothing, approves
nothing, and creates or arms no trigger. It only copies a graph that is already
stored into a revision row and sets a pointer. A workflow whose graph is not
structurally runnable is REPORTED for repair and left with a NULL pointer,
rather than silently offered for routine reuse.

ponytail: the structural check below is deliberately a subset of
``workflow_service.validate_graph``. The full validator needs the piece registry
and lives in neutrino-workflow-service, which a migration in this package cannot
import. The subset catches the class §10 names — a definition the interpreter
cannot read at all — and the node-type list is hardcoded on purpose: a migration
is a point-in-time script, so pinning the types as they were on 10 September 2026
is correct and cannot drift. Nothing is weakened by the gap, because
``run_service.refuse_unrunnable_graph`` still applies the full validator before
anything executes; this migration can only publish a pointer, never a run.

Revision ID: 3a7b9c1d2e4f
Revises: 2f1c8ad4b3e5
"""

from __future__ import annotations

import json
import logging
import uuid

import sqlalchemy as sa
from alembic import op

revision = "3a7b9c1d2e4f"
down_revision = "2f1c8ad4b3e5"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

# ``SUPPORTED_NODE_TYPES`` from
# neutrino-workflow-service/app/temporal/workflows/graph_workflow.py:94, as of
# 10 September 2026. Copied, not imported — see the ponytail note above.
_SUPPORTED_NODE_TYPES = frozenset(
    {
        "trigger",
        "action",
        "on_failure",
        "branch",
        "filter",
        "approval",
        "form",
        "llm",
        "agent",
        "code_agent",
        "noc_parse_alert",
        "noc_render_triage",
        "remote_exec",
        "remediate",
    }
)


def _structural_reasons(graph: object) -> list[str]:
    """Every reason the interpreter could not read this graph at all.

    Edges use ``from`` and ``to`` in this product, which is what
    ``graph_workflow._topological_order`` indexes on. Naming them ``source`` and
    ``target`` here would report every real workflow as broken.
    """
    if not isinstance(graph, dict):
        return ["the graph is not an object"]
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return ["the graph has no nodes"]

    reasons: list[str] = []
    if any(not isinstance(node, dict) for node in nodes):
        reasons.append("a node is not an object")
    dicts = [node for node in nodes if isinstance(node, dict)]
    ids = [str(node.get("id") or "") for node in dicts]
    if any(not node_id for node_id in ids):
        reasons.append("a node has no id, so the interpreter cannot order the graph")
    if len(set(ids)) != len(ids):
        reasons.append("two nodes share an id")
    unsupported = sorted(
        {
            str(node.get("type") or "")
            for node in dicts
            if str(node.get("type") or "") not in _SUPPORTED_NODE_TYPES
        }
    )
    if unsupported:
        reasons.append(f"the interpreter cannot run node type(s): {', '.join(unsupported)}")

    known = {node_id for node_id in ids if node_id}
    edges = graph.get("edges") or []
    if not isinstance(edges, list):
        reasons.append("edges is not a list")
        return reasons
    for edge in edges:
        if not isinstance(edge, dict):
            reasons.append("an edge is not an object")
            continue
        for end in ("from", "to"):
            ref = str(edge.get(end) or "")
            if ref not in known:
                reasons.append(f"an edge names '{ref}', which is not a node in this graph")
    return reasons


def upgrade() -> None:
    bind = op.get_bind()
    # DISTINCT ON: a workflow may carry more than one active webhook trigger,
    # and a plain join would try to insert revision 1 twice and trip
    # uq_workflow_revision_number. The earliest trigger's contract is the one
    # the workflow was published with.
    candidates = bind.execute(
        sa.text(
            """
            SELECT DISTINCT ON (w.id)
                   w.id, w.tenant_id, w.workspace_id, w.name, w.graph, t.config
              FROM workflow w
              JOIN workflow_trigger t ON t.workflow_id = w.id
             WHERE w.status <> 'archived'
               AND t.kind = 'webhook'
               AND t.status = 'active'
               AND w.published_revision_id IS NULL
             ORDER BY w.id, t.created_at
            """
        )
    ).mappings().all()

    published = 0
    reported = 0
    for row in candidates:
        reasons = _structural_reasons(row["graph"])
        if reasons:
            reported += 1
            logger.warning(
                "workflow %s (%s) was NOT published and needs repair: %s",
                row["id"],
                row["name"],
                "; ".join(reasons),
            )
            continue
        revision_id = str(uuid.uuid4())
        input_schema = (row["config"] or {}).get("input_schema") or []
        bind.execute(
            sa.text(
                """
                INSERT INTO workflow_revision
                    (id, workflow_id, tenant_id, workspace_id, revision_number,
                     graph, input_schema, created_by)
                VALUES
                    (:id, :workflow_id, :tenant_id, :workspace_id, 1,
                     CAST(:graph AS jsonb), CAST(:input_schema AS jsonb), NULL)
                """
            ),
            {
                "id": revision_id,
                "workflow_id": row["id"],
                "tenant_id": row["tenant_id"],
                "workspace_id": row["workspace_id"],
                "graph": json.dumps(row["graph"]),
                "input_schema": json.dumps(input_schema),
            },
        )
        bind.execute(
            sa.text(
                "UPDATE workflow SET published_revision_id = :revision_id WHERE id = :id"
            ),
            {"revision_id": revision_id, "id": row["id"]},
        )
        published += 1

    logger.info(
        "backfill: %s workflow(s) published as revision 1, %s reported for repair",
        published,
        reported,
    )


def downgrade() -> None:
    """Deliberately a no-op.

    There is no column recording which revisions this migration inserted, and by
    the time anyone downgrades, real users have published revisions of their own.
    A heuristic delete — revision_number = 1, or created_by IS NULL — would take
    those with it. Leaving the rows is harmless: a revision nothing points at is
    inert, and the pointer column existed before this migration.
    """
    logger.info(
        "backfill downgrade is a no-op: published revisions are kept, "
        "because nothing distinguishes them from user-published ones"
    )
