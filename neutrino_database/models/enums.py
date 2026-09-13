from enum import Enum


class ConnectionStatus(str, Enum):
    active = "active"
    error = "error"
    revoked = "revoked"

class KeyStatusEnum(str, Enum):
    CURRENT = "current"
    NEXT = "next"
    RETIRED = "retired"


class TenantStatusEnum(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    DELETED = "DELETED"
    PENDING_OPENFGA_SETUP = "PENDING_OPENFGA_SETUP"

class AllowedModuleEnum(str, Enum):
    ENTERPRISE_SEARCH = "Enterprise Search"
    DATA_ANALYTICS = "Data Analytics"
    WEB_SEARCH = "Web Search"
    DEEP_RESEARCH = "Deep Research"
    DASHBOARDS = "Dashboards"

class UserStatusEnum(str, Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class PlatformUserStatusEnum(str, Enum):
    """Lifecycle of a platform (cross-tenant) operator account.

    Deliberately separate from ``UserStatusEnum``: a platform user is never
    "INVITED" — there is no invitation flow for operators, they are minted by
    an existing platform admin or the bootstrap CLI. Keeping the enums apart
    also stops a future ``UserStatusEnum`` value from silently acquiring a
    meaning on the operator table.
    """

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class IdpProviderEnum(str, Enum):
    AZURE_AD = "AZURE_AD"
    GOOGLE_IDENTITY = "GOOGLE_IDENTITY"
    # Synthetic provider for password-authed users. There is no external
    # IdP, so the Neutrino user_id IS the stable provider_user_id within
    # this namespace. Lets every Neutrino user have an addressable Member
    # row in OpenFGA Store B regardless of how they signed in
    # (X-MEMBER-BRIDGE-1).
    NEUTRINO_LOCAL = "NEUTRINO_LOCAL"

class MemberSourceEnum(str, Enum):
    """How we discovered this member"""
    SSO_LOGIN = "SSO_LOGIN"              # User logged in via UI/Teams
    FILE_PERMISSIONS = "FILE_PERMISSIONS"  # From file permission sync
    LOCAL_LOGIN = "LOCAL_LOGIN"          # User logged in via local password


class FileProcessingStatusEnum(str, Enum):
    """Where a file is in its processing pipeline (X-DOC-1).

    The user-visible state machine that drives the FE status surface,
    Temporal workflow orchestration, and audit emission. See
    ``user-stories/connect-ingestion-refactor.md`` §6 for transitions
    and §7 for Temporal workflow architecture.

    Forward path:
        pending -> fetching -> fetched
                -> converting (office docs only; PDFs skip it)
                -> parsing -> chunking -> embedding
                -> indexing -> acl_replicated -> indexed
    Terminal:
        any -> failed (with error_code + error_message + retriable_at)
        any -> deleted (tombstone)
    Retry:
        failed -> fetching (new attempt_id)
    """

    PENDING = "pending"
    FETCHING = "fetching"
    FETCHED = "fetched"
    # Office docs (docx/pptx/xlsx/odt...) are converted to PDF before parsing,
    # since MinerU pages over a real PDF. PDFs skip this stage entirely.
    CONVERTING = "converting"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    ACL_REPLICATED = "acl_replicated"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class FileSourceTypeEnum(str, Enum):
    """CanonicalDocument source kind (CANON-DOC-1).

    Closed vocabulary from ``product-feature-roadmap/enterprise-search/
    unified-doc-parse-chunk.md``. Drives chunking regime (long-form
    regime A vs short-record regime B), citation card layout, ranking
    weights (recency matters more for `message`/`issue` than `file`),
    and chat-UI filter chips.

    New kinds require an alembic migration; the framework relies on
    this being exhaustive at the type level.
    """

    FILE = "file"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    COMMIT = "commit"
    PAGE = "page"
    RECORD = "record"
    MESSAGE = "message"
    EMAIL = "email"
    EVENT = "event"
    COMMENT = "comment"
    ATTACHMENT = "attachment"
    TICKET = "ticket"


class MessageRoleEnum(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"

class WorkspaceStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"

class WorkspaceAccessStatusEnum(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RouterModeEnum(str, Enum):
    AUTO = "AUTO"
    SEARCH_ONLY = "SEARCH_ONLY"
    ACTION_ONLY = "ACTION_ONLY"
    DA_ONLY = "DA_ONLY"


class PillarEnum(str, Enum):
    """
    The three product pillars a workspace can have enabled, in any
    combination. Replaces the conflated single-value RouterModeEnum
    as the source-of-truth for "what does this workspace do" — see
    `workspace.enabled_pillars` and the alembic migration that adds
    it. RouterModeEnum stays for now (agent-platform still reads it);
    the gateway writes both during a transition window.
    """
    ENTERPRISE_SEARCH = "ENTERPRISE_SEARCH"
    DATA_ANALYTICS = "DATA_ANALYTICS"
    WORKFLOW_EXECUTION = "WORKFLOW_EXECUTION"


class RetrievalStrategyEnum(str, Enum):
    SEMANTIC = "SEMANTIC"
    KEYWORD = "KEYWORD"
    HYBRID = "HYBRID"
    AGENTIC = "AGENTIC"

class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    OBSERVATION = "observation"


class ServiceType(str, Enum):
    """Supported AI service providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    AZURE_OPENAI = "azure_openai"
    LANDINGAI = "landingai"
    BEDROCK = "bedrock"
    # NC-526 — OpenRouter is an OpenAI-compatible aggregator, but it gets its
    # own service type rather than riding "openai": its model ids are
    # namespaced ("vendor/model"), its catalog is fetched at runtime, and it
    # needs per-model reasoning-budget control that the OpenAI preset has no
    # field for.
    OPENROUTER = "openrouter"


class ProviderCategory(str, Enum):
    """Categories of external service providers"""
    LLM = "llm"
    DOCUMENT_PARSER = "document_parser"
    EMBEDDING = "embedding"


class SpanType(str, Enum):
    """Types of observability spans recorded in trace_spans."""
    LLM = "llm"
    TOOL = "tool"
    AGENT = "agent"


class SpanStatus(str, Enum):
    """Outcome status of an observability span."""
    OK = "ok"
    ERROR = "error"


class ExcelDatasetStatus(str, Enum):
    """Lifecycle status of an uploaded Excel dataset."""
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class ChatAttachmentKindEnum(str, Enum):
    """Which analysis lane an ephemeral chat attachment routes through (NC-137).

    Derived from the uploaded file's mime type at creation; drives both
    dispatch (tabular -> E2B sandbox/pandas, document -> MinerU extraction,
    image -> native model vision) and the FE chip icon.
    """
    TABULAR = "tabular"      # CSV / Excel
    DOCUMENT = "document"    # PDF (MinerU parse-only)
    IMAGE = "image"          # png / jpg (base64 -> vision)


class ChatAttachmentStatusEnum(str, Enum):
    """State machine for an ephemeral chat attachment (NC-137).

    Tabular and image attachments land ``READY`` immediately (no async
    processing). The document lane goes ``PROCESSING`` while MinerU extracts
    (Slice B), then ``READY`` or ``FAILED``.
    """
    UPLOADED = "uploaded"        # bytes in MinIO; row created
    PROCESSING = "processing"    # async extraction in flight (document lane)
    READY = "ready"             # usable in a turn
    FAILED = "failed"           # upload/extraction failed


class ChatAttachmentDirectionEnum(str, Enum):
    """Provenance of a chat_attachment (NC-149).

    The table serves two mirror-image flows over the same ephemeral,
    conversation-scoped, TTL'd MinIO-blob lifecycle:

    inbound  — the user uploaded a file for the agent to analyse (NC-137).
    outbound — the agent generated a file the user asked to "download as a
               report" (CSV / Excel / PDF / Word), surfaced as a download
               button (NC-149).

    ``kind`` stays meaningful across both (a PDF/Word export is ``document``,
    a CSV/Excel export is ``tabular``); direction is the only new axis.
    """
    INBOUND = "inbound"      # user upload (NC-137)
    OUTBOUND = "outbound"    # agent-generated export (NC-149)


class ChatArtifactKindEnum(str, Enum):
    """Render-family discriminator for a unified-agent artifact (NC-151).

    An artifact is a durable, addressable output a chat turn emits, rendered in
    its own view and (Slice B) shareable via link. ``kind`` selects the FE
    renderer AND the safety posture — it is deliberately pillar-agnostic, so DA's
    ECharts is just one producer of ``chart`` here, not a special case.

    Two render families:
      structured — the house owns styling; the model conveys only semantics
                   (like NC-149 exports). Rendered by trusted in-app components.
          chart  — an ECharts-shaped spec + its data.
          table  — columns + rows (typed cells, emphasis roles).
          kpi    — headline metric(s): value, label, delta.
      generative — the model authors the markup; rendered in a SANDBOXED iframe
                   (opaque origin, no parent cookie/DOM access) under a strict CSP.
          html   — a self-contained HTML page ("a full dashboard page and more").
          react  — an interactive React + Tailwind component (compiled in a
                   sandboxed runtime). The single visual/interactive path — it
                   supersedes the legacy inline ```jsx answer artifact.
          doc    — a long-form formatted document (markdown-derived HTML).
    """
    CHART = "chart"
    TABLE = "table"
    KPI = "kpi"
    HTML = "html"
    REACT = "react"
    DOC = "doc"


class ShareLinkResourceTypeEnum(str, Enum):
    """What a share_link points at (NC-151 Slice B). Polymorphic: resource_id
    references different tables by this type. chat_artifact today; dashboards and
    others fold onto this one sharing subsystem later (superseding the DA-specific
    dashboard_link_token)."""
    CHAT_ARTIFACT = "chat_artifact"


class ShareLinkVisibilityEnum(str, Enum):
    """Who can open a shared link (NC-151 Slice B).

    public    — anyone with the link, no login (a frozen, ACL-scrubbed snapshot).
    workspace — the link resolves only for authenticated members of the owning
                workspace ("private with link"). The safe default.
    """
    PUBLIC = "public"
    WORKSPACE = "workspace"


# ---------------------------------------------------------------------------
# Data Analytics pillar (NEU-1811 DA-P0).
#
# Eight enums backing the canonical metadata schema described in
# `product-feature-roadmap/data-analytics/data-flow.md` §4.8. Naming is
# DA-prefixed so they cannot collide with the legacy `ConnectionStatus`
# (which is the ES connector enum, shared with SharePoint/Drive auth).
# ---------------------------------------------------------------------------


class DAConnectionStatusEnum(str, Enum):
    """Lifecycle status of a tenant-level DA Connection.

    pending_auth — created but credentials not yet verified
    active       — credentials validated; ready for metadata sync + queries
    degraded     — last sync had recoverable errors (partial failure)
    error        — credentials invalid / persistent failure; admin attention
    disabled     — admin paused the connection
    """
    PENDING_AUTH = "pending_auth"
    ACTIVE = "active"
    DEGRADED = "degraded"
    ERROR = "error"
    DISABLED = "disabled"


class DASourceTypeEnum(str, Enum):
    """Datasource types supported by the DA pillar.

    v1 ships postgres + snowflake + bigquery; mysql + oracle queued. Mongo is
    the first non-relational source, served by a separate NoSqlBaseAdapter
    (per feature.md F5) that speaks aggregation pipelines rather than SQL.

    Persisted as plain varchar in integration.provider, so adding a member
    here needs no migration.
    """
    POSTGRES = "postgres"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    MYSQL = "mysql"
    ORACLE = "oracle"
    MONGODB = "mongodb"


class DATableTypeEnum(str, Enum):
    """Kind of relation surfaced by INFORMATION_SCHEMA.TABLES."""
    TABLE = "table"
    VIEW = "view"
    MATERIALIZED_VIEW = "materialized_view"


class DAMetricSourceEnum(str, Enum):
    """Where this Metric came from (HITL provenance).

    admin_authored        — Workspace Admin wrote it directly
    ai_suggested          — AI proposed; pending admin accept/reject
    ai_accepted_by_admin  — AI proposed and admin accepted unchanged
    """
    ADMIN_AUTHORED = "admin_authored"
    AI_SUGGESTED = "ai_suggested"
    AI_ACCEPTED_BY_ADMIN = "ai_accepted_by_admin"


class DAJoinHintSourceEnum(str, Enum):
    """Where this JoinHint came from (HITL provenance).

    inferred_from_fk — auto-derived from FK constraints during Phase 1 pull
    admin_authored / ai_suggested / ai_accepted_by_admin as above
    """
    ADMIN_AUTHORED = "admin_authored"
    INFERRED_FROM_FK = "inferred_from_fk"
    AI_SUGGESTED = "ai_suggested"
    AI_ACCEPTED_BY_ADMIN = "ai_accepted_by_admin"


class DAJoinTypeEnum(str, Enum):
    """SQL join semantics the hint describes."""
    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    FULL = "full"


class DADescriptionScopeEnum(str, Enum):
    """What kind of row a description_version row belongs to.

    Soft-FK pattern: `description_version.parent_id` references one of
    four parent tables; `scope` discriminates. No DB-level FK because
    Postgres doesn't support discriminated FKs natively.
    """
    TABLE = "table"
    COLUMN = "column"
    METRIC = "metric"
    JOIN_HINT = "join_hint"


class DADescriptionSourceEnum(str, Enum):
    """Provenance of a description_version entry.

    native_comment  — copied from the source DDL during Phase 1
    ai_generated    — created by GovernedLLM (admin-triggered)
    ai_suggested    — AI proposed but not yet admin-accepted (HITL)
    admin_edited    — Workspace Admin wrote / overrode the description
    """
    NATIVE_COMMENT = "native_comment"
    AI_GENERATED = "ai_generated"
    AI_SUGGESTED = "ai_suggested"
    ADMIN_EDITED = "admin_edited"


# ---------------------------------------------------------------------------
# Dashboards (NEU-1811 DA-P3.1). Workspace-scoped authored surfaces
# built via the build chat. Draft/Published lifecycle + workspace /
# restricted / link-only visibility + per-widget data binding.
# ---------------------------------------------------------------------------


class DashboardStatusEnum(str, Enum):
    """Lifecycle status of a saved dashboard.

    draft     — work in progress, visible only to workspace admins
                in the Library's Drafts section.
    published — finalised, visible to every workspace member per
                the visibility flag.
    """
    DRAFT = "draft"
    PUBLISHED = "published"


class DashboardVisibilityEnum(str, Enum):
    """Audience scope for a published dashboard.

    workspace_members — every member of the workspace can view (default
                        for published dashboards).
    restricted        — explicit member / group allowlist via
                        dashboard_share rows. (v2; the table doesn't
                        ship in DA-P3.1 — TD-DASH-INTERNAL-SHARE-1.)
    link_only         — unlisted; only a link-token holder can view.
                        No workspace-member access by default.
    """
    WORKSPACE_MEMBERS = "workspace_members"
    RESTRICTED = "restricted"
    LINK_ONLY = "link_only"


class DataBindingKindEnum(str, Enum):
    """Which query language a dashboard widget's data_binding speaks.

    A widget re-executes its query on every dashboard load, so the binding has
    to say what kind of query it holds. This is an EXPLICIT tag rather than
    something each consumer infers from which fields are populated, because
    inference does not scale: every new datasource would mean editing every
    reader (the FE's execute call, the public share executor, the pin mapper),
    and a reader that had not been taught the new shape would silently treat it
    as one of the old ones.

    With a tag, adding a datasource is: one member here, one row in
    ``DATA_BINDING_FORMS``, and the DA tool that produces it. Readers dispatch
    on the tag and need no change.

    relational — SQL over a warehouse / relational database.
    document   — an aggregation pipeline over a collection (MongoDB).

    Absent on widgets written before this tag existed; those are all relational,
    and DashboardWidgetDataBinding infers that for them.
    """
    RELATIONAL = "relational"
    DOCUMENT = "document"


# Per-kind contract: the fields that must be present, and the connector-service
# route that executes it. THE table to extend for a new datasource — an Iceberg
# or Trino binding is a member above plus a row here, and every consumer that
# dispatches on the tag keeps working untouched.
#
# ``execute_route`` is the suffix under
# ``/api/v1/da/connections/{connection_id}/`` — shared so the authed widget
# fetch, the anonymous share-link executor and any future caller cannot drift
# apart on which endpoint runs which binding.
#
# ``body_fields`` are the binding fields that make up that route's request body.
# Here rather than at each caller because the anonymous share-link executor
# lives in the gateway and the authed fetch lives in the frontend — two repos
# that would otherwise each hardcode a per-source body and drift. Note it is
# NOT simply ``required``: a relational binding needs ``schema_name`` to be
# valid but the execute route does not take it.
DATA_BINDING_FORMS: dict[DataBindingKindEnum, dict[str, object]] = {
    DataBindingKindEnum.RELATIONAL: {
        "required": ("schema_name", "sql"),
        "execute_route": "execute_query",
        "body_fields": ("sql",),
    },
    DataBindingKindEnum.DOCUMENT: {
        "required": ("database", "collection", "pipeline"),
        "execute_route": "execute_pipeline",
        "body_fields": ("database", "collection", "pipeline"),
    },
}


class DashboardWidgetTypeEnum(str, Enum):
    """v1 widget catalog — what the canvas grid can render.

    Each maps 1:1 to a visualization renderer in
    components/visualizations on the FE side.
    """
    KPI_TILE = "kpi_tile"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    STACKED_BAR = "stacked_bar"
    PIE_CHART = "pie_chart"
    DONUT_CHART = "donut_chart"
    SANKEY = "sankey"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    FUNNEL = "funnel"
    TREEMAP = "treemap"
    RADAR = "radar"
    WATERFALL = "waterfall"
    TABLE = "table"
    TEXT = "text"


class DashboardProposalStateEnum(str, Enum):
    """What became of one widget proposal from a build-chat turn.

    applied   — materialised onto the canvas (``widget_id`` points at it).
    removed   — was applied, then the widget was deleted from the canvas.
                Distinct from never-applied: the build chat must NOT offer
                "Apply" again, or deleting a widget reads as an invitation to
                re-add it. Widget deletes are hard deletes, so this row is the
                only surviving record that the proposal ever landed.
    dismissed — the admin explicitly declined the proposal.
    """
    APPLIED = "applied"
    REMOVED = "removed"
    DISMISSED = "dismissed"


class ChatKindEnum(str, Enum):
    """What a chat thread is for (D6).

    ad_hoc          — the day-to-day Q&A chat surface. The default.
    dashboard_build — admin's build conversation with the dashboard
                      agent. One row per dashboard, set when the
                      dashboard is created. Drafts in the Library
                      are these chats.
    workflow_build  — the "Build with Neutrino" conversation behind one
                      Workflow (linked via ``chat.workflow_id``). One row
                      per workflow; lets the builder resume where the
                      user left off across reloads.
    """
    AD_HOC = "ad_hoc"
    DASHBOARD_BUILD = "dashboard_build"
    WORKFLOW_BUILD = "workflow_build"


class EstateScopeKindEnum(str, Enum):
    """What estate resource a conversation is about (ITOps merge S5).

    A chat with a scope is still an ordinary ad_hoc conversation: the scope is a
    visible chip and a server-side resolution hint, never a permission and never
    hidden text prepended to the user's message. Several conversations may share
    one uid.
    """
    HOST = "host"
    INCIDENT = "incident"


class DAAccessResourceTypeEnum(str, Enum):
    """Which DA catalog level a workspace_da_access_grant row applies
    to (X-DA-ACL-1). The grant + the resource_id together identify the
    exact node in the schema → table → column tree we're granting or
    denying access to."""
    SCHEMA = "schema"
    TABLE = "table"
    COLUMN = "column"


class DAAccessEffectEnum(str, Enum):
    """Two-state effect for a workspace_da_access_grant row
    (X-DA-ACL-1). 'Inherits parent' is the absence of any row at this
    level — it is never stored. Resolution rule applied by the
    service:

      * Walk the resource tree from leaf up (column → table → schema
        → workspace-member). Closest level with an explicit row
        wins.
      * At the same level, deny beats allow (column conflict can't
        happen given the UNIQUE constraint, but the rule still holds
        across levels: a child-allow can override a parent-deny).
      * Tenant Owner / Tenant Admin / Workspace Admin bypass entirely
        via the JWT projection.
      * M10 PII / Restricted catalog flags hard-block above all of
        this.
    """
    ALLOW = "allow"
    DENY = "deny"


# ---------------------------------------------------------------------------
# DA catalog enrichment (NC-103) — durable Reprofile / Regenerate runs wired
# through a Temporal workflow, with a DB-backed progress projection the
# Data Curation page polls and re-attaches to across refreshes.
# ---------------------------------------------------------------------------


class DAEnrichmentScopeEnum(str, Enum):
    """What a single enrichment run targets. The curation UI triggers at
    table and schema level; ``connection`` covers a whole source.

      * ``connection`` → schema_id IS NULL AND table_id IS NULL
      * ``schema``     → schema_id NOT NULL
      * ``table``      → table_id NOT NULL
    """
    CONNECTION = "connection"
    SCHEMA = "schema"
    TABLE = "table"


class DAEnrichmentOperationEnum(str, Enum):
    """Which stage(s) a run performs. The UI exposes Reprofile and
    Regenerate as independent buttons, so a run is not always both.

      * ``profile``  → warehouse column-profile pass only.
      * ``describe`` → LLM description generation only.
      * ``enrich``   → profile then describe (describe consumes the
        fresh stats), the ordered end-to-end pipeline.
    """
    PROFILE = "profile"
    DESCRIBE = "describe"
    ENRICH = "enrich"


class DAEnrichmentRunStatusEnum(str, Enum):
    """Lifecycle of a ``da_enrichment_run``. ``completed_with_errors``
    marks a finished run where at least one table failed but the rest
    succeeded — the run is not aborted by a single bad table."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DAEnrichmentStageStatusEnum(str, Enum):
    """Per-table, per-stage status on ``da_enrichment_table_item``. NULL
    on a stage column means that stage is not part of this run's
    operation (e.g. ``profile_status`` stays NULL for a describe-only
    run). ``skipped`` is a compliance/eligibility skip, not a failure."""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Unified integration hierarchy (WF-VS1) — the credential model shared across
# ES + DA + WF. See product-feature-roadmap/workflow-execution §5a, §9.
# ---------------------------------------------------------------------------


class IntegrationOwnerKindEnum(str, Enum):
    """Where an integration credential is owned. Three tiers — a tenant
    admin establishes corporate connections shared via enablement; a
    workspace admin can also establish a connection their workspace owns
    outright; any member can connect a personal credential. The CHECK
    constraint on ``integration`` ties this to the nullability of
    ``owner_user_id`` / ``workspace_id``:

      * ``tenant``    → owner_user_id IS NULL  AND workspace_id IS NULL
      * ``user``      → owner_user_id NOT NULL AND workspace_id NOT NULL
      * ``workspace`` → owner_user_id IS NULL  AND workspace_id NOT NULL
        (``workspace_id`` is the owning workspace)
    """
    TENANT = "tenant"
    USER = "user"
    WORKSPACE = "workspace"


class IntegrationIdentityKindEnum(str, Enum):
    """Who the destination SaaS sees when this credential is used.
    Derived from the provider catalog at create time, never
    client-supplied. Orthogonal to owner_kind.

    ``none`` is reserved for local-only sources (member uploads a PDF /
    CSV) where there is no remote destination, so the "identity the
    destination sees" question doesn't apply. Introduced in
    UC-ES-DB-1.A when collapsing legacy ``datasources`` onto
    ``integration``."""
    USER = "user"
    APP = "app"
    SERVICE_ACCOUNT = "service_account"
    NONE = "none"


class IntegrationAuthKindEnum(str, Enum):
    """How the credential authenticates. ``api_key`` / ``basic`` need no
    OAuth app registration (the member/tenant pastes a token);
    ``oauth2`` / ``oauth2_app_only`` require a platform or BYO app
    (Level-1 registration).

    Two distinct OAuth flows — they look similar at the catalog layer
    but have very different security shapes, so the SOC2 evidence chain
    ("how did this credential authenticate?") records them separately:

      * ``oauth2``          — delegated authorization-code grant.
                               The user signs in via popup; the
                               credential acts AS that user. Refresh
                               token rotates per user. Identity kind
                               = ``user``.
      * ``oauth2_app_only`` — client-credentials grant. The app
                               authenticates as itself; needs admin
                               pre-grant on the destination (e.g.
                               SharePoint Sites.Selected). No user
                               involvement at credential-mint time.
                               Identity kind = ``app``. Added in
                               UC-ES-DB-1.D.1e.

    ``none`` is reserved for sources that don't authenticate against a
    remote system at all (member uploads a PDF directly into ES). When
    ``auth_kind == 'none'``, ``vault_secret_id`` is also NULL (no
    credential to vault). Introduced in UC-ES-DB-1.A."""
    OAUTH2 = "oauth2"
    OAUTH2_APP_ONLY = "oauth2_app_only"
    API_KEY = "api_key"
    BASIC = "basic"
    CUSTOM = "custom"
    NONE = "none"


class IntegrationStatusEnum(str, Enum):
    """Lifecycle of an integration credential."""
    ACTIVE = "active"
    DISABLED = "disabled"
    REVOKED = "revoked"
    EXPIRED = "expired"


class IntegrationEnablementStatusEnum(str, Enum):
    """Lifecycle of a per-workspace enablement of a tenant integration.
    Disabling pauses workspace use without revoking the underlying
    tenant credential."""
    ACTIVE = "active"
    DISABLED = "disabled"


class IntegrationSyncJobStatusEnum(str, Enum):
    """Lifecycle of one record-source sync run (RECORD-SYNC-TEMPORAL-1).
    Driven by ES-Ingestion's ``RecordSourceSyncWorkflow``:

      pending → running → succeeded | failed | cancelled

    Mirrors the file-source side's ``ingestion_job_status`` shape so
    Indexed Content can render run-level rollup identically for either
    ingestion path."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IntegrationGrantEffectEnum(str, Enum):
    """Two-state effect for an integration_member_grant row. Same
    deny-wins-anywhere semantics as DAAccessEffectEnum, scoped to
    integration capabilities. 'No row' = no explicit grant (default
    deny for members; admins bypass via JWT projection)."""
    ALLOW = "allow"
    DENY = "deny"


# ---------------------------------------------------------------------------
# Workflow Execution pillar (WF-VS2) — workflow definitions.
# ---------------------------------------------------------------------------


class WorkflowStatusEnum(str, Enum):
    """Lifecycle of a workflow definition.

    draft     — being built; not yet runnable on a schedule/trigger.
    active    — live; may be triggered / run.
    disabled  — paused without deletion (triggers won't fire).
    archived  — retired; retained for audit, hidden from the builder.
    """
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class WorkflowRunStatusEnum(str, Enum):
    """Lifecycle of a single workflow execution (one ``workflow_run`` row).

    queued    — run row created; Temporal start in flight, not yet executing.
    running   — at least one node has begun.
    succeeded — every node completed without error.
    failed    — a node failed (after retries) and aborted the run.
    cancelled — explicitly cancelled by a user / admin.
    """
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowActorKindEnum(str, Enum):
    """How a run was triggered — drives the identity/audit interpretation.

    user           — a person clicked Run (manual). ``actor_user_id`` set.
    cron           — a schedule fired; no actor (``audit_principal`` = author).
    event          — an internal event fired the run.
    webhook_auth   — an authenticated inbound webhook (actor from the JWT).
    webhook_anon   — an anonymous inbound webhook; no actor.
    fan_out_member — one iteration of a per-member cron fan-out (actor = member).

    M1 only ever writes ``user``; the rest are defined now so M4/M5/M7 add no
    enum migration.
    """
    USER = "user"
    CRON = "cron"
    EVENT = "event"
    WEBHOOK_AUTH = "webhook_auth"
    WEBHOOK_ANON = "webhook_anon"
    FAN_OUT_MEMBER = "fan_out_member"


class WorkflowRunStepStatusEnum(str, Enum):
    """Lifecycle of a single executed node within a run (``workflow_run_step``).

    pending   — recorded but not yet started.
    running   — the node's activity is in flight.
    succeeded — completed without error.
    failed    — failed after exhausting retries.
    skipped   — not executed (e.g. a branch not taken).
    expired   — a human-wait node reached its deadline with no answer, after
                every configured approver tier was notified. Distinct from
                ``failed`` (nothing malfunctioned — no activity errored and no
                retries were exhausted) and from ``succeeded`` (nobody decided,
                so nothing downstream ran). NC-257: a timeout must never read
                as an approval, and an unanswered gate must be visible as such
                in the run history rather than hidden behind a green or red
                row. The run itself stays alive so the Case remains open.
    """
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    EXPIRED = "expired"


class WorkflowTriggerKindEnum(str, Enum):
    """How a stored trigger fires a workflow (manual isn't stored — it's the
    Run button).

    webhook — a public token URL is POSTed to; the request body is the payload.
    cron    — a schedule fires it (config holds the cron expression). [M4]
    event   — an internal event fires it (config names the event). [later]
    """
    WEBHOOK = "webhook"
    CRON = "cron"
    EVENT = "event"


class WorkflowTriggerStatusEnum(str, Enum):
    """Whether a trigger is live.

    active   — armed; will fire.
    disabled — paused without deletion (webhook URL 409s, schedule won't fire).
    """
    ACTIVE = "active"
    DISABLED = "disabled"


class ExecutionProposalStatusEnum(str, Enum):
    """Where an agent-proposed execution stands (ITOps merge S4, §4.1).

    pending   — recorded, awaiting a human decision. Nothing has run.
    approved  — a human approved this exact digest; the run may start.
    rejected  — a human refused it. It never becomes approvable again.
    cancelled — withdrawn before anyone decided (the requester, or a superseding
                proposal). Distinct from ``rejected``: nobody said no.
    expired   — ``expires_at`` passed with no decision. A timeout must never
                read as an approval, so this is its own terminal value.
    succeeded — the approved run finished and its postcheck passed.
    failed    — the approved run finished and its postcheck failed, or the run
                itself failed. Terminal; the requester proposes again.
    """
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
