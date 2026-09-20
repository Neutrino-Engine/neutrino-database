"""Agent Studio shared schemas (plans/AGENT-STUDIO-PLAN.md).

The JSONB ``config`` columns of ``studio_agent`` / ``studio_team`` and the
run-time contracts between the orchestrator and its agents are defined ONCE
here so agent-platform (writer), the gateway (API key middleware) and the
frontend codegen read the same shape.

Contracts:

  * ``AgentConfig``  — what a builder authors for a specialist.
  * ``TeamConfig``   — orchestrator config + roster + policy + guardrails.
  * ``Brief``        — what the orchestrator hands an agent (never history).
  * ``Envelope``     — what an agent returns. ``status != completed`` is an
                       error to the orchestrator, never partial-as-success.
  * ``ToolError``    — the structured error every tool returns instead of a
                       raw exception string.
"""

from __future__ import annotations

from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


RunStatus = Literal[
    "planning", "dispatching", "waiting_approval", "paused", "finishing",
    "completed", "failed", "cancelled",
]
TaskStatus = Literal[
    "pending", "running", "waiting_approval", "completed", "error",
    "budget_exhausted", "stalled", "schema_invalid", "cancelled", "approval_rejected",
]
TriggerKind = Literal["chat", "studio", "api", "schedule", "event", "test"]
ApprovalOutcome = Literal["allowed_once", "rejected", "cancelled", "unavailable"]
ToolErrorCode = Literal[
    "auth", "not_found", "validation", "rate_limited", "timeout",
    "dependency_failed", "policy_denied", "outcome_unknown", "internal",
]
ExecutionMode = Literal["parallel", "exclusive"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


# ---------------------------------------------------------------------------
# Authoring
# ---------------------------------------------------------------------------

class Limits(_Strict):
    max_turns: int = Field(40, ge=1, le=500)
    max_tokens: int = Field(400_000, ge=1_000)
    max_wall_s: int = Field(1_800, ge=30)
    max_tool_calls: int = Field(200, ge=1)
    # Stall detection (decision 10): heartbeats, not wall clock, decide liveness.
    stall_idle_s: int = Field(300, ge=30)
    stall_in_tool_s: int = Field(900, ge=30)
    stall_grace_s: int = Field(60, ge=0)


class ConnectorAction(_Strict):
    """One connector action an agent may call, with its side-effect policy."""
    integration_id: UUID
    action: str
    effect: Literal["read", "write"] = "read"
    write_enabled: bool = False
    requires_approval: bool = True

    @model_validator(mode="after")
    def _read_needs_no_flags(self):
        if self.effect == "read":
            self.write_enabled = False
            self.requires_approval = False
        return self


BuiltinTool = Literal[
    "read_file", "write_file", "list_workspace", "run_python",
    "knowledge_search", "save_memory", "forget_memory", "ask_human",
]


class AgentConfig(_Strict):
    charter: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    builtin_tools: list[BuiltinTool] = Field(default_factory=list)
    connector_actions: list[ConnectorAction] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    # Mandatory (decision 3). ``notes`` is where free text goes.
    output_schema: dict[str, Any]
    limits: Limits = Field(default_factory=Limits)
    # Harness-enforced, not prompt-enforced: tool names the agent may never call.
    deny_list: list[str] = Field(default_factory=list)
    memory_enabled: bool = False
    code_exec_enabled: bool = False

    @model_validator(mode="after")
    def _output_schema_is_object(self):
        if self.output_schema.get("type") != "object":
            raise ValueError("output_schema must be a JSON Schema of type 'object'")
        if self.code_exec_enabled and "run_python" not in self.builtin_tools:
            self.builtin_tools.append("run_python")
        if not self.code_exec_enabled and "run_python" in self.builtin_tools:
            raise ValueError("run_python requires code_exec_enabled")
        return self


class RosterEntry(_Strict):
    alias: str = Field(..., min_length=1, max_length=100)
    agent_id: UUID
    # NULL on a draft team = "latest published"; publishing pins it (decision 25).
    agent_version_id: Optional[UUID] = None


class Ordering(_Strict):
    before: str
    after: str


class MandatoryGate(_Strict):
    after_alias: str
    approver_ids: list[UUID] = Field(default_factory=list)


class Guardrails(_Strict):
    max_parallel: int = Field(3, ge=1, le=20)
    required_aliases: list[str] = Field(default_factory=list)
    forbidden_orderings: list[Ordering] = Field(default_factory=list)
    mandatory_gates: list[MandatoryGate] = Field(default_factory=list)
    max_replans: int = Field(2, ge=0, le=10)
    per_agent_retry_cap: int = Field(1, ge=0, le=5)
    # Orchestrator may call other published teams as black-box agents; two
    # levels total (decision 23).
    allow_team_calls: bool = False


class RunsAs(_Strict):
    kind: Literal["invoker", "owner", "service"] = "invoker"
    # user id for owner/service; ignored for invoker.
    identity_id: Optional[UUID] = None

    @model_validator(mode="after")
    def _identity_present(self):
        if self.kind != "invoker" and self.identity_id is None:
            raise ValueError(f"runs_as.kind={self.kind} requires identity_id")
        return self


class NotificationTarget(_Strict):
    kind: Literal["email", "connector"]
    # email: address; connector: integration_id + action + static params.
    address: Optional[str] = None
    integration_id: Optional[UUID] = None
    action: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    events: list[Literal["approval_requested", "run_finished", "run_failed"]] = Field(
        default_factory=lambda: ["approval_requested", "run_failed"]
    )


class PromotedOutput(_Strict):
    path: str
    index: bool = False


class OrchestratorConfig(_Strict):
    model: str = Field(..., min_length=1)
    limits: Limits = Field(default_factory=lambda: Limits(max_turns=60, max_wall_s=14_400))
    # Free text the orchestrator sees in addition to the team description.
    instructions: str = ""


class TeamConfig(_Strict):
    orchestrator: OrchestratorConfig
    roster: list[RosterEntry] = Field(..., min_length=1)
    guardrails: Guardrails = Field(default_factory=Guardrails)
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    output_schema: dict[str, Any]
    runs_as: RunsAs = Field(default_factory=RunsAs)
    approver_ids: list[UUID] = Field(default_factory=list)
    # wait — pause for a human; deny — unattended runs refuse the write instead.
    approval_policy: Literal["wait", "deny"] = "wait"
    approval_timeout_s: int = Field(72 * 3600, ge=60)
    notification_targets: list[NotificationTarget] = Field(default_factory=list)
    memory_enabled: bool = False
    promoted_outputs: list[PromotedOutput] = Field(default_factory=list)
    # Team-level budget caps; the harness sums task usage against them.
    max_usd: Optional[float] = Field(None, gt=0)
    max_sandbox_s: Optional[int] = Field(None, gt=0)

    @model_validator(mode="after")
    def _aliases_consistent(self):
        aliases = [r.alias for r in self.roster]
        if len(set(aliases)) != len(aliases):
            raise ValueError("roster aliases must be unique")
        known = set(aliases)
        for a in self.guardrails.required_aliases:
            if a not in known:
                raise ValueError(f"required alias {a!r} not in roster")
        for o in self.guardrails.forbidden_orderings:
            if o.before not in known or o.after not in known:
                raise ValueError(f"forbidden ordering names unknown alias: {o.before!r}/{o.after!r}")
        for g in self.guardrails.mandatory_gates:
            if g.after_alias not in known:
                raise ValueError(f"mandatory gate names unknown alias {g.after_alias!r}")
        if self.output_schema.get("type") != "object":
            raise ValueError("output_schema must be a JSON Schema of type 'object'")
        return self


# ---------------------------------------------------------------------------
# Run-time contracts
# ---------------------------------------------------------------------------

class Brief(_Strict):
    """What an agent receives. Never the parent's history (decision 6)."""
    objective: str = Field(..., min_length=1)
    context: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    workspace_paths: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class PlanTask(_Strict):
    alias: str
    objective: str
    context: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)  # aliases
    # Set by the workflow once dispatched.
    task_id: Optional[UUID] = None
    status: TaskStatus = "pending"


class Plan(_Strict):
    tasks: list[PlanTask] = Field(..., min_length=1)
    rationale: str = ""

    @model_validator(mode="after")
    def _acyclic_and_known(self):
        names = [t.alias for t in self.tasks]
        if len(set(names)) != len(names):
            raise ValueError("plan task aliases must be unique")
        known = set(names)
        deps = {t.alias: set(t.depends_on) for t in self.tasks}
        for a, ds in deps.items():
            unknown = ds - known
            if unknown:
                raise ValueError(f"task {a!r} depends on unknown alias(es) {sorted(unknown)}")
            if a in ds:
                raise ValueError(f"task {a!r} depends on itself")
        # Kahn's algorithm; anything left is a cycle.
        indeg = {a: len(ds) for a, ds in deps.items()}
        ready = [a for a, d in indeg.items() if d == 0]
        seen = 0
        while ready:
            cur = ready.pop()
            seen += 1
            for a, ds in deps.items():
                if cur in ds:
                    indeg[a] -= 1
                    if indeg[a] == 0:
                        ready.append(a)
        if seen != len(names):
            raise ValueError("plan contains a dependency cycle")
        return self


class ToolError(_Strict):
    code: ToolErrorCode
    message: str
    retryable: bool = False
    caused_by: Optional[str] = None  # alias or tool that failed upstream


class ToolResult(_Strict):
    ok: bool
    result: Any = None
    error: Optional[ToolError] = None

    @model_validator(mode="after")
    def _one_of(self):
        if self.ok and self.error is not None:
            raise ValueError("ok result carries no error")
        if not self.ok and self.error is None:
            raise ValueError("failed result must carry an error")
        return self


class BudgetUsage(_Strict):
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: int = 0
    turns: int = 0
    wall_s: float = 0
    usd: float = 0
    sandbox_s: float = 0


class Envelope(_Strict):
    """What an agent task returns. Non-completed is an error to the parent."""
    status: TaskStatus
    exit_reason: str = ""
    output: Optional[dict[str, Any]] = None
    raw_text: Optional[str] = None
    schema_errors: Optional[list[str]] = None
    diagnostic: Optional[str] = Field(None, max_length=4096)
    files_written: list[str] = Field(default_factory=list)
    budgets: BudgetUsage = Field(default_factory=BudgetUsage)

    @property
    def completed(self) -> bool:
        return self.status == "completed"

    @model_validator(mode="after")
    def _completed_has_output(self):
        if self.status == "completed" and self.output is None:
            raise ValueError("completed envelope must carry output")
        if self.status == "schema_invalid" and self.raw_text is None:
            raise ValueError("schema_invalid envelope must preserve raw_text")
        return self


__all__ = [
    "AgentConfig", "ApprovalOutcome", "Brief", "BudgetUsage", "BuiltinTool",
    "ConnectorAction", "Envelope", "ExecutionMode", "Guardrails", "Limits",
    "MandatoryGate", "NotificationTarget", "OrchestratorConfig", "Ordering",
    "Plan", "PlanTask", "PromotedOutput", "RosterEntry", "RunStatus", "RunsAs",
    "TaskStatus", "TeamConfig", "ToolError", "ToolErrorCode", "ToolResult",
    "TriggerKind",
]
