from sqlalchemy import (
    Date, BigInteger,
    Table, Column, Integer, SmallInteger, String, Text, TIMESTAMP, DateTime, Index, Float, ForeignKey, BigInteger, Enum as PgEnum,
    UniqueConstraint, Numeric, DDL, event, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY, INET
from sqlalchemy.sql import func, text
from sqlalchemy import Boolean
from neutrino_database.models.base import metadata

from neutrino_database.models.enums import (
    AgentMessageRole,
    AllowedModuleEnum,
    ChatArtifactKindEnum,
    ShareLinkResourceTypeEnum,
    ShareLinkVisibilityEnum,
    ChatAttachmentDirectionEnum,
    ChatAttachmentKindEnum,
    ChatAttachmentStatusEnum,
    ChatKindEnum,
    ConnectionStatus,
    DAAccessEffectEnum,
    DAAccessResourceTypeEnum,
    DAConnectionStatusEnum,
    DADescriptionScopeEnum,
    DADescriptionSourceEnum,
    DAEnrichmentOperationEnum,
    DAEnrichmentRunStatusEnum,
    DAEnrichmentScopeEnum,
    DAEnrichmentStageStatusEnum,
    DAJoinHintSourceEnum,
    DAJoinTypeEnum,
    DAMetricSourceEnum,
    DASourceTypeEnum,
    DATableTypeEnum,
    DashboardProposalStateEnum,
    DashboardStatusEnum,
    DashboardVisibilityEnum,
    DashboardWidgetTypeEnum,
    EstateScopeKindEnum,
    ExcelDatasetStatus,
    ExecutionProposalStatusEnum,
    FileProcessingStatusEnum,
    FileSourceTypeEnum,
    IdpProviderEnum,
    IntegrationAuthKindEnum,
    IntegrationEnablementStatusEnum,
    IntegrationSyncJobStatusEnum,
    IntegrationGrantEffectEnum,
    IntegrationIdentityKindEnum,
    IntegrationOwnerKindEnum,
    IntegrationStatusEnum,
    WorkflowStatusEnum,
    WorkflowRunStatusEnum,
    WorkflowActorKindEnum,
    WorkflowRunStepStatusEnum,
    WorkflowTriggerKindEnum,
    WorkflowTriggerStatusEnum,
    KeyStatusEnum,
    MemberSourceEnum,
    MessageRoleEnum,
    PillarEnum,
    PlatformUserStatusEnum,
    RetrievalStrategyEnum,
    RouterModeEnum,
    RunStatus,
    SpanStatus,
    SpanType,
    TenantStatusEnum,
    UserStatusEnum,
    WorkspaceAccessStatusEnum,
    WorkspaceStatusEnum,
)

import uuid


files = Table(
    "files",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    # UC-ES-DB-1.B — repointed from datasources.id onto integration.id
    # as part of collapsing the legacy connector schema onto the
    # canonical integration table. Every file belongs to an integration
    # (member upload via auth_kind='none', or an OAuth source).
    Column(
        "integration_id",
        UUID(as_uuid=True),
        ForeignKey("integration.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),

    Column("external_file_info", JSONB, nullable=True, comment="Stores file_id and drive_id of external sources, e.g., SharePoint"),

    # File-source info — nullable since CANON-DOC-1 unified files with
    # record-source connectors (Jira issues / Confluence pages / Slack
    # messages have none of these). File-source rows still populate them.
    Column("original_filename", String, nullable=True),
    Column("file_type", String(255), nullable=True),  # full MIME content-type (Office MIMEs exceed 20)
    Column("storage_uri", Text, nullable=True),
    Column("file_size_bytes", BigInteger, nullable=True),
    Column("file_sha256", String(64), nullable=True),

    # ── CanonicalDocument shape (CANON-DOC-1) ────────────────────────
    # See product-feature-roadmap/enterprise-search/unified-doc-parse-chunk.md.
    Column(
        "source_type",
        PgEnum(
            FileSourceTypeEnum,
            name="file_source_type",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'file'"),
        comment="CanonicalDocument source kind. Drives chunker regime + citation card + ranking.",
    ),
    Column("source_url", Text, nullable=False, server_default=text("''")),
    Column("container_id", String(255), nullable=False, server_default=text("''")),
    Column("container_name", Text, nullable=False, server_default=text("''")),
    Column("breadcrumb", JSONB, nullable=True),
    Column("language", String(10), nullable=True),
    Column(
        "parent_doc_id",
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=True,
        comment="Self-FK for comments / replies / attachments; cascade delete.",
    ),
    Column("facets", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column(
        "display_metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Display-only bag (named display_metadata to avoid SA MetaData clash).",
    ),
    Column("title", Text, nullable=True),
    Column(
        "viewers",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        comment="Serialized ViewerSet — source of truth for ACL. Default {} = default-deny.",
    ),
    Column("acl_extractor_version", SmallInteger, nullable=True),
    Column("acl_extracted_at", TIMESTAMP(timezone=True), nullable=True),

    # Legacy free-form status (kept for backwards compatibility; deprecated
    # in favour of `processing_status` below — see TD-DOC-2).
    Column("status", String(50), nullable=False, server_default=text("'DOWNLOADED'")),

    # X-DOC-1 typed pipeline-state machine. Drives the FE status surface,
    # Temporal workflow orchestration, and audit emission. See
    # `user-stories/connect-ingestion-refactor.md` §6 for transitions.
    Column(
        "processing_status",
        PgEnum(
            FileProcessingStatusEnum,
            name="file_processing_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'pending'"),
    ),
    Column(
        "status_updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column("error_code", String(64), nullable=True),
    Column("error_message", Text, nullable=True),
    Column("error_retriable_at", TIMESTAMP(timezone=True), nullable=True),

    # Timestamps
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, onupdate=func.now()),

    Column("created_by", String, nullable=False),
    Column("is_deleted", Boolean, nullable=False, server_default=text("false")),

    Column("permission_mirroring_status", String(50), nullable=False, server_default=text("'NOT INITIATED'")),

    # Per-workspace + status filter is the dominant FE/admin query shape
    # ("show me failed files in this workspace").
    Index("ix_files_workspace_processing_status", "workspace_id", "processing_status"),

    # Parent → children lookup (chat agent rebuilds threads from chunks).
    Index(
        "ix_files_parent_doc_id",
        "parent_doc_id",
        postgresql_where=text("parent_doc_id IS NOT NULL"),
    ),
)


# ---------------------------------------------------------------------------
# X-DOC-1: ingestion's private retry / Temporal-state ledger.
#
# One row per file (lazy — only created when ingestion picks the file up).
# The canonical user-visible state stays on the `files` row; this side
# table holds retry counters, the current Temporal workflow id, and
# stage-specific payloads that would otherwise pollute the canonical row.
# Decision 5.9 in connect-ingestion-refactor.md.
# ---------------------------------------------------------------------------
file_processing_state = Table(
    "file_processing_state",
    metadata,
    Column(
        "file_id",
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "temporal_workflow_id",
        String(255),
        nullable=True,
        comment="Temporal workflow id for the in-flight ingestion run; "
                "shape: 'file:{uuid}'",
    ),
    Column(
        "attempt_id",
        Integer,
        nullable=False,
        server_default=text("1"),
        comment="Increments on each retry of the full pipeline. "
                "Used as part of the idempotency key for chunk / "
                "embedding writes.",
    ),
    Column(
        "last_activity",
        String(64),
        nullable=True,
        comment="Name of the most recently observed activity, e.g. "
                "'parse', 'chunk', 'embed', 'index', 'replicate_acl'.",
    ),
    Column(
        "retry_count",
        Integer,
        nullable=False,
        server_default=text("0"),
    ),
    Column("next_retry_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "payload",
        JSONB,
        nullable=True,
        comment="Activity-specific opaque state. Ingestion writes here; "
                "documents-owner doesn't interpret.",
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),

    Index(
        "ix_file_processing_state_due_retries",
        "next_retry_at",
        postgresql_where=text("next_retry_at IS NOT NULL"),
    ),
)


ingestion_jobs = Table(
    "ingestion_jobs",
    metadata,

    # Identifiers
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("file_id", UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),

    # Status
    Column("overall_status", String(50), nullable=False, server_default=text("'READY_FOR_INGESTION'")),
    Column("progress_status", JSONB, nullable=True),
    Column("progress_percentage", Integer, nullable=False, server_default=text("0")),

    # Timestamps
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),

    Column("created_by", String, nullable=False),
    Column("is_deleted", Boolean, nullable=False, server_default=text("false")),

)

parsing = Table(
    "parsing",
    metadata,

    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False),ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("file_id", UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),

    Column("page_no", Integer, nullable=False),
    Column("page_text", Text, nullable=False),
    Column("page_hash", Text, nullable=False),

    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),

    Index("idx_parsing_file_page", "file_id", "page_no", unique=True)
)

chunk = Table(
    "chunk",
    metadata,

    # Identifiers
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("file_id", UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),

    Column("page_no", Integer, nullable=True, server_default=text("0")),
    Column("ord", Integer, nullable=True),
    Column("chunk_text", Text, nullable=False),
    Column("chunk_hash", Text, nullable=False),

    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),

    Index("idx_chunk_file_page_hash", "file_id", "page_no", "chunk_hash", unique=True)
)

embedding = Table(
    "embedding",
    metadata,

    # Identifiers
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("file_id", UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
    Column("chunk_hash", String, nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),

    # Dense vector - simple float array
    Column("dense_vector", ARRAY(Float), nullable=True),
    Column("dense_dim", Integer, nullable=False),

    # Sparse vector - JSONB with indices/values
    Column("sparse_vector", JSONB, nullable=True),
    Column("sparse_dim", Integer, nullable=True),

    # Metadata
    Column("model", String(100), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),

    Index("idx_embedding_tenant_file_chunk_unique", "tenant_id", "file_id", "chunk_hash", unique=True)
)


index_sync = Table(
    "index_sync",
    metadata,
    Column("doc_id", UUID(as_uuid=True), primary_key=True),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("file_id", UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
    Column("chunk_id", UUID(as_uuid=True), ForeignKey("chunk.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),

    Column("chunk_hash", Text, nullable=False),
    Column("ack_at", TIMESTAMP(timezone=True), nullable=True),
    Column("last_error", Text, nullable=True),
    Column("attempt_count", Integer, nullable=False, server_default=text("0"))
)


chunking_strategies = Table(
    "chunking_strategies",
    metadata,

    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("name", String, nullable=False),
    Column("description", Text, nullable=True),
    Column("config", JSONB, nullable=True),
    Column("is_active", Boolean, nullable=False, server_default=text("true")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
)

strategies = Table(
    "strategies",
    metadata,

    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("name", String, nullable=False),
    Column("strategy_id", UUID(as_uuid=True), nullable=True),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    # Foreign keys
    Column("file_id", UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
    Column("chunking_strategy_id", UUID(as_uuid=True), ForeignKey("chunking_strategies.id", ondelete="CASCADE"), nullable=False),

    Column("description", Text, nullable=True),
    Column("custom_config", JSONB, nullable=True, server_default=text("'{}'::jsonb")),

    Column(
        "status",
        String,
        nullable=False,
        server_default=text("'draft'"),
    ),

    # Timestamps
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),

    # Audit fields
    Column("created_by", String, nullable=False),
    Column("updated_by", String, nullable=False),
    Column("is_deleted", Boolean, nullable=False, server_default=text("false")),
)


lock_lease = Table(
    "mutex_locks",
    metadata,

    Column("name", Text, primary_key=True),
    Column("owner_id", Text, nullable=True),
    Column("lease_until", TIMESTAMP(timezone=True), nullable=True),
    Column("fencing_token", BigInteger, nullable=False, default=0),
)


rotation_mutex = Table(
    "rotation_mutex",
    metadata,

    Column("id", Boolean, primary_key=True, default=True),
    Column("held_by", Text, nullable=True),
    Column("held_since", TIMESTAMP(timezone=True), nullable=True),
)

signing_key = Table(
    "signing_keys",
    metadata,

    Column("kid", Text, primary_key=True),
    Column("public_pem", Text, nullable=False),
    Column("private_pem", Text, nullable=False),
    Column("status", PgEnum(KeyStatusEnum, name="key_status"), nullable=False),
    Column("not_before", TIMESTAMP(timezone=True), nullable=True),
    Column("not_after", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
)

tenant_authz_store = Table(
    "tenant_authz_store",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("store_id", String(255), nullable=False),
    Column("model_id", String(255), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
)

workspace_authz_store = Table(
    "workspace_authz_store",
    metadata,
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("store_id", String(64), nullable=True),
    Column("model_id", String(64), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

tenant = Table(
    "tenant",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("name", String(255), nullable=False),
    Column("org_external_id", String(200), nullable=False, unique=True),
    Column("status", PgEnum(TenantStatusEnum, name="tenant_status"), nullable=False, default=TenantStatusEnum.PENDING),
    Column("allowed_modules", JSONB, nullable=True, default=lambda: [module.value for module in AllowedModuleEnum]),
    Column("status_updated_at", TIMESTAMP(timezone=True), nullable=True),
    Column("status_updated_by", UUID(as_uuid=False), nullable=True),
    Column("status_reason", Text, nullable=True),
    Column("tenant_owner", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    # First-class signal of "this tenant has finished initial onboarding."
    # Stamped atomically by POST /api/v1/onboarding/complete; replaces the
    # !workspace_id proxy used by the FE post-auth callback to decide
    # /welcome vs /chat.
    Column("onboarding_completed_at", TIMESTAMP(timezone=True), nullable=True),
    # Per-tenant cap on active workspaces (NEU-1805 § 1d). Soft-deleted
    # workspaces don't count; the retention runner cleans them up at
    # 30 days. Default 50 covers real teams; enterprise raises it via a
    # one-row UPDATE rather than a code change.
    Column("max_workspaces", Integer, nullable=False, server_default=text("50")),
    # Owner-controlled domain allowlist for invitations (NEU-X4).
    # Empty array = no restriction (anyone can be invited). Non-empty
    # = invitations rejected unless the invitee's email domain is in
    # the list. Owner edits this via /tenants/{id}/settings.
    # Replaces the previous hardcoded "must match owner email domain"
    # check that broke for orgs with multiple legitimate domains
    # (IBM: ibm.com, ibm.co.in, ibm.co.uk, …).
    Column(
        "allowed_invitation_domains",
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    ),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),

    Index("ix_tenant_status", "status"),
    Index("ix_tenant_created_at", "created_at"),
)

user = Table(
    "user",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("email", String(320), nullable=False, comment="pii:email"),
    Column("display_name", String(255), nullable=True, comment="pii:name"),
    Column("status", PgEnum(UserStatusEnum, name="user_status"), nullable=False, default=UserStatusEnum.ACTIVE),
    Column("first_login_at", TIMESTAMP(timezone=True), nullable=True),
    Column("last_login_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("default_workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="SET NULL"), nullable=True),

    # Local auth columns — nullable so SSO-only users are unaffected
    Column("username", String(100), nullable=True, comment="pii:name"),
    Column("password_hash", Text, nullable=True),
    Column("must_change_password", Boolean, nullable=False, server_default="false"),
    Column("password_changed_at", TIMESTAMP(timezone=True), nullable=True),

    # NEU-X8 — Authorization-state freshness marker. Touched whenever any
    # claim affecting this user's principal changes (promote/demote
    # tenant admin, promote/demote workspace admin, ownership transfer
    # accept on either side). The auth middleware compares the JWT's
    # `iat` against this column on each request; if `permissions_changed_at`
    # is newer, the JWT is force-renewed regardless of the normal
    # renewal-window threshold. Closes the "promoted-but-FE-still-shows-
    # non-admin until sign-out + sign-in" UX gap. Defaults to created_at
    # so existing rows behave like "no change since issuance" for
    # back-compat.
    Column("permissions_changed_at", TIMESTAMP(timezone=True), nullable=True),

    UniqueConstraint("tenant_id", "email", name="ux_user_tenant_email"),
    UniqueConstraint("tenant_id", "username", name="ux_user_tenant_username"),  # NULLs excluded from uniqueness — multiple SSO-only users per tenant are valid
    Index("ix_user_tenant_status", "tenant_id", "status"),
    Index("ix_user_last_login_at", "last_login_at"),
    Index("ix_user_tenant_username_lower", "tenant_id", func.lower(Column("username", String(100))), unique=True, postgresql_where=text("username IS NOT NULL")),
    Index("ix_user_email_lower_active", func.lower(Column("email", String(320))), postgresql_where=text("deleted_at IS NULL")),
    Index("ix_user_username_lower_active", func.lower(Column("username", String(100))), postgresql_where=text("deleted_at IS NULL AND username IS NOT NULL")),
)

# NC-494 — platform (cross-tenant) operator accounts.
#
# Deliberately NOT a row in `user`: `user.tenant_id` is NOT NULL, so an
# operator would have to be parked inside some arbitrary tenant, and every
# `(tenant_id, email)` uniqueness guarantee would start lying. Worse, a
# platform bit riding on a normal session token would be forwarded to
# downstream services by `mint_internal_token`.
#
# Email is globally unique here (unlike `user.email`, which is unique only
# per tenant), so the operator login lookup has none of the cross-tenant
# ambiguity that `LocalAuthService.login` has to defend against.
platform_user = Table(
    "platform_user",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("email", String(320), nullable=False, comment="pii:email"),
    Column("display_name", String(255), nullable=True, comment="pii:name"),
    Column(
        "status",
        PgEnum(PlatformUserStatusEnum, name="platform_user_status"),
        nullable=False,
        server_default=PlatformUserStatusEnum.ACTIVE.value,
    ),
    Column("password_hash", Text, nullable=False),
    Column("must_change_password", Boolean, nullable=False, server_default="false"),
    Column("password_changed_at", TIMESTAMP(timezone=True), nullable=True),
    Column("last_login_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),

    UniqueConstraint("email", name="ux_platform_user_email"),
    # Case-insensitive uniqueness among live rows, mirroring
    # ix_user_email_lower_active. Soft-deleted rows are excluded so an
    # address can be reused after an operator is removed.
    Index(
        "ix_platform_user_email_lower_active",
        func.lower(Column("email", String(320))),
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    ),
)

tenant_identity = Table(
    "tenant_identity",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("provider", PgEnum(IdpProviderEnum, name="idp_provider"), nullable=False, default=IdpProviderEnum.AZURE_AD),
    Column("provider_org_id", String(200), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    UniqueConstraint("provider", "provider_org_id", name="ux_tenant_identity_provider_org"),
)

sso_identity = Table(
    "sso_identity",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("provider", PgEnum(IdpProviderEnum, name="idp_provider"), nullable=False, default=IdpProviderEnum.AZURE_AD),
    Column("provider_user_id", String(200), nullable=False),
    Column("provider_org_id", String(200), nullable=False),
    Column("last_login_at", TIMESTAMP(timezone=True), nullable=True),
    Column("raw_profile", JSONB, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    UniqueConstraint("provider", "provider_user_id", name="ux_sso_identity_provider_user"),
    Index("ix_sso_identity_provider_org", "provider", "provider_org_id"),
    Index("ix_sso_identity_user_id", "user_id"),
)

member = Table(
    "member",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("email", String(255), nullable=True, comment="pii:email"),
    Column("name", String(255), nullable=True, comment="pii:name"),
    Column("provider", PgEnum(IdpProviderEnum, name="idp_provider"), nullable=False, default=IdpProviderEnum.AZURE_AD),
    Column("provider_user_id", String(200), nullable=False),
    Column("provider_org_id", String(200), nullable=False),
    Column("source", PgEnum(MemberSourceEnum, name="member_source"), nullable=False, default=MemberSourceEnum.SSO_LOGIN),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    UniqueConstraint("provider", "provider_user_id", name="ux_member_provider_user"),
    Index("ix_member_provider_org", "provider", "provider_org_id"),
    Index("ix_member_user_id", "user_id"),
    Index("ix_member_source", "source"),
)

role = Table(
    "role",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id"), nullable=False),
    Column("key", String(120), nullable=False),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=True),

    UniqueConstraint("tenant_id", "key", name="ux_role_tenant_key"),
    Index("ix_role_tenant_name", "tenant_id", "name"),
)

app_permission = Table(
    "app_permission",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("key", String(120), nullable=False, unique=True),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=True),
)

user_invitation = Table(
    "user_invitation",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("inviter", UUID(as_uuid=False), ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("email", String(320), nullable=False),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    Column("accepted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    Index("ix_user_invitation_tenant_email", "tenant_id", "email"),
    Index("ix_user_invitation_expires_at", "expires_at"),
    Index("ix_user_invitation_tenant_email_pending", "tenant_id", "email", postgresql_where=text("accepted_at IS NULL AND deleted_at IS NULL")),
)

chat = Table(
    "chat",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    # Workspace this chat thread belongs to (X-CHAT-WS-1). NOT NULL —
    # every chat lives inside exactly one workspace. CASCADE so that
    # deleting a workspace removes its chats (mirrors
    # ``dashboard.workspace_id`` which is also CASCADE). Without this
    # column the per-workspace list query has nothing to ground its
    # authorization on, so a Tenant Admin in two workspaces sees the
    # same threads in both — see X-CHAT-WS-1 for context.
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("title", String(255), nullable=True),
    Column("incognito", Boolean, nullable=False, server_default=text("false")),
    Column("pinned", Boolean, nullable=False, server_default=text("false")),
    # D6 — what this chat is for. ``ad_hoc`` (default) is the day-to-
    # day Q&A chat surface. ``dashboard_build`` flags this row as the
    # build conversation behind one Dashboard (linked via the
    # ``dashboard.build_chat_id`` FK back-pointer). Drafts in the
    # Library are these chats.
    Column(
        "kind",
        PgEnum(
            ChatKindEnum,
            name="chat_kind",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'ad_hoc'"),
    ),
    # Back-pointer to the dashboard this chat is building. NULL for
    # ad_hoc chats. CASCADE on the dashboard side so deleting a
    # dashboard also wipes its build chat — drafts and dashboards have
    # a 1:1 lifecycle.
    Column(
        "dashboard_id",
        UUID(as_uuid=False),
        ForeignKey("dashboard.id", ondelete="CASCADE"),
        nullable=True,
    ),
    # Back-pointer to the workflow this chat is building (kind=
    # ``workflow_build``). NULL for ad_hoc / dashboard chats. CASCADE so
    # deleting a workflow also wipes its build conversation — a workflow
    # and its build chat share a 1:1 lifecycle, mirroring ``dashboard_id``.
    Column(
        "workflow_id",
        UUID(as_uuid=False),
        ForeignKey("workflow.id", ondelete="CASCADE"),
        nullable=True,
    ),
    # TD-DA-PILLAR-PERSIST — the pillar this chat was initiated on, so the
    # pillar (and, for DA, its data scope) survive reopen/continue and are
    # authoritative across devices instead of living only in the browser's
    # ``pillar_for_thread_<id>`` localStorage stopgap. NULL means "no single
    # pillar": Unified chats (AUTO, spans all pillars — exempt by design) and
    # legacy rows created before this column existed. Reuses the shared
    # ``pillar`` enum type owned by ``workspace.enabled_pillars``
    # (create_type=False so metadata create_all doesn't try to re-create it).
    Column(
        "pillar",
        PgEnum(PillarEnum, name="pillar", create_type=False),
        nullable=True,
    ),
    # ITOps merge S5 — the estate resource this conversation is about. Mirrors
    # the dashboard_id / workflow_id / pillar precedent above: scope belongs to
    # the row, not to localStorage, so the chip survives a refresh and a reopen
    # from history. NULL for every non-estate chat. Not a foreign key: an estate
    # uid lives in Neo4j, so there is nothing here to reference.
    Column(
        "estate_scope_kind",
        PgEnum(
            EstateScopeKindEnum,
            name="estate_scope_kind",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=True,
    ),
    Column("estate_uid", Text, nullable=True),
    Column("estate_display_name", Text, nullable=True),
    # DA data scope captured at chat creation (only set when pillar =
    # DATA_ANALYTICS). Mirrors the FE ``text_to_sql_config`` so a reopened DA
    # chat auto-selects its schema and runs against the same connection
    # without depending on the global ``selected_schema`` localStorage key.
    # NC-474 — the pinned connection as a real FK. ``da_connection_name`` is a
    # display string with no uniqueness constraint, so once a workspace has more
    # than one Postgres connector it stops identifying a row (two same-named
    # connectors made the resolver raise MultipleResultsFound). The name column
    # stays for display + legacy-row fallback. SET NULL so deleting a connection
    # doesn't take the chat history with it.
    Column(
        "da_connection_id",
        UUID(as_uuid=False),
        ForeignKey("integration.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("da_connection_name", String, nullable=True),
    Column("da_schema_name", String, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),

    Index("ix_chat_tenant_incognito", "tenant_id", "incognito"),
    Index("ix_chat_tenant_non_incognito", "tenant_id", postgresql_where=text("incognito = false")),
    Index("ix_chat_tenant_updated_at", "tenant_id", "updated_at"),
    # Per-user per-workspace list index (X-CHAT-WS-1). Keys exactly
    # the FE's list query:
    #   WHERE workspace_id = :ws AND created_by = :user
    #         AND deleted_at IS NULL
    #   ORDER BY updated_at DESC
    # Partial on ``deleted_at IS NULL`` so soft-deleted rows don't
    # bloat the index.
    Index(
        "ix_chat_workspace_created_by_updated_at",
        "workspace_id",
        "created_by",
        text("updated_at DESC"),
        postgresql_where=text("deleted_at IS NULL"),
    ),
    # Keys the build-chat lookup (one row per workflow):
    #   WHERE workflow_id = :wf AND deleted_at IS NULL
    Index(
        "ix_chat_workflow_id",
        "workflow_id",
        postgresql_where=text("workflow_id IS NOT NULL AND deleted_at IS NULL"),
    ),
)

message = Table(
    "message",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("chat_id", UUID(as_uuid=False), ForeignKey("chat.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("role", PgEnum(MessageRoleEnum, name="message_role"), nullable=False, default=MessageRoleEnum.USER),
    Column("content", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),

    Index("ix_message_chat_created_at", "chat_id", "created_at"),
    Index("ix_message_tenant_chat", "tenant_id", "chat_id"),
    Index("ix_message_user_id", "user_id"),
)


# NC-137 — ephemeral, conversation-scoped file attachments for Unified
# Chat (Claude-style upload-and-analyse). DELIBERATELY separate from
# Enterprise Search ingestion (permanent, indexed, ACL'd via `files`) and
# from the DA Excel-dataset path (Excel -> Postgres queryable schema):
# these attachments are throwaway, scoped to one chat, TTL'd, and never
# indexed. Their own status state machine + TTL sweep + delete-with-chat
# cascade are why this is a table, not a JSONB column on `message`.
chat_attachment = Table(
    "chat_attachment",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    # Nullable: the upload can precede the chat row (the composer uploads
    # on paperclip-click, before the first message creates the chat) and is
    # linked when the message is sent. CASCADE purges attachments with the
    # chat; never-linked (NULL) orphans are reaped by the TTL sweep.
    Column("chat_id", UUID(as_uuid=False), ForeignKey("chat.id", ondelete="CASCADE"), nullable=True),
    # Linked when the user sends the message. An attachment's lifecycle is a
    # subset of its message's, hence CASCADE.
    Column("message_id", UUID(as_uuid=False), ForeignKey("message.id", ondelete="CASCADE"), nullable=True),
    # Always set at insert; SET NULL on user delete so a departed uploader
    # doesn't cascade-delete in-flight attachments (mirrors chat.created_by).
    Column("uploaded_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),

    Column("filename", String(512), nullable=False),
    Column("mime_type", String(255), nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    # MinIO object key for the raw bytes.
    Column("storage_key", Text, nullable=False),
    # MinIO object key for MinerU-extracted markdown (document lane, Slice B).
    Column("extracted_text_key", Text, nullable=True),

    Column(
        "kind",
        PgEnum(ChatAttachmentKindEnum, name="chat_attachment_kind",
               values_callable=lambda enum: [e.value for e in enum]),
        nullable=False,
    ),
    Column(
        "status",
        PgEnum(ChatAttachmentStatusEnum, name="chat_attachment_status",
               values_callable=lambda enum: [e.value for e in enum]),
        nullable=False,
        server_default=text("'uploaded'"),
    ),
    # Provenance: inbound = user upload (NC-137); outbound = agent-generated
    # export (NC-149). Defaults to inbound so every existing row and the
    # untouched upload path stay correct with no code change.
    Column(
        "direction",
        PgEnum(ChatAttachmentDirectionEnum, name="chat_attachment_direction",
               values_callable=lambda enum: [e.value for e in enum]),
        nullable=False,
        server_default=text("'inbound'"),
    ),
    Column("error", Text, nullable=True),

    # TTL/GC sweep target — when this ephemeral row should be reaped.
    Column("expires_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),

    # Per-chat attachment list: WHERE chat_id = :c AND deleted_at IS NULL.
    Index(
        "ix_chat_attachment_chat_id",
        "chat_id",
        postgresql_where=text("deleted_at IS NULL"),
    ),
    # TTL/GC reaper scans by expiry; partial so soft-deleted rows don't bloat it.
    Index(
        "ix_chat_attachment_expires_at",
        "expires_at",
        postgresql_where=text("deleted_at IS NULL AND expires_at IS NOT NULL"),
    ),
    # Pre-link listing of a user's recent uploads in a workspace.
    Index("ix_chat_attachment_uploaded_by", "workspace_id", "uploaded_by"),
)


# A durable, addressable artifact a unified-agent turn produces (NC-151). Unlike
# chat_attachment (opaque bytes to download), an artifact is small structured
# content the FE renders in its own view: a governed chart/table/kpi, or a
# model-authored generative html/doc page. Deliberately pillar-agnostic — kind +
# a JSONB content payload model every render family, so DA's ECharts is just one
# `chart` producer, not a special case. This id is the handle the Share feature
# (Slice B) mints links against.
chat_artifact = Table(
    "chat_artifact",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    # NOT NULL: an artifact is always produced inside an existing conversation
    # (the agent emits it mid-turn), so — unlike an upload — it never precedes
    # the chat. CASCADE so it dies with its chat.
    Column("chat_id", UUID(as_uuid=False), ForeignKey("chat.id", ondelete="CASCADE"), nullable=False),
    # The producing assistant message. SET NULL (not CASCADE): an artifact is a
    # durable, addressable snapshot meant to outlive an edited/deleted message —
    # a shared link (Slice B) must not 404 because the origin turn was trimmed.
    Column("message_id", UUID(as_uuid=False), ForeignKey("message.id", ondelete="SET NULL"), nullable=True),
    # Known at insert; SET NULL so a departed author doesn't cascade-destroy
    # their artifacts (mirrors chat.created_by / chat_attachment.uploaded_by).
    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),

    # Render-family discriminator: structured (chart/table/kpi, house-rendered)
    # vs generative (html/doc, sandboxed-iframe rendered).
    Column(
        "kind",
        PgEnum(ChatArtifactKindEnum, name="chat_artifact_kind",
               values_callable=lambda enum: [e.value for e in enum]),
        nullable=False,
    ),
    Column("title", String(512), nullable=True),
    # The whole render payload, inline: structured spec+data, or {"html": ...}
    # for generative. Inline JSONB (not a MinIO blob) because an artifact is
    # structured content the FE renders, not opaque download bytes. Large-HTML-
    # to-blob is tracked debt (TD-ARTIFACT-CONTENT-BLOB), not a v1 concern.
    Column("content", JSONB, nullable=False),
    # Claude-style iterate-in-place bumps this ("update this artifact"); the
    # column exists now so the UX lands without a migration.
    Column("version", Integer, nullable=False, server_default=text("1")),
    # Agent Studio: a team run's final output lands in chat as an artifact and
    # links back to the run so the card can deep-link to the console. SET NULL:
    # the artifact is the user's; the run record may be purged independently.
    Column("run_id", UUID(as_uuid=False), ForeignKey("studio_run.id", ondelete="SET NULL"), nullable=True),
    # Lineage for revisualize/fork. Self-FK SET NULL so a derived artifact
    # survives its parent's deletion.
    Column(
        "derived_from_artifact_id",
        UUID(as_uuid=False),
        ForeignKey("chat_artifact.id", ondelete="SET NULL"),
        nullable=True,
    ),

    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),

    # Per-chat artifact list: WHERE chat_id = :c AND deleted_at IS NULL.
    Index(
        "ix_chat_artifact_chat_id",
        "chat_id",
        postgresql_where=text("deleted_at IS NULL"),
    ),
    # Reload rehydration fetches a message's artifacts by message_id.
    Index(
        "ix_chat_artifact_message_id",
        "message_id",
        postgresql_where=text("deleted_at IS NULL"),
    ),
)


# One sharing subsystem (NC-151 Slice B). A share_link points at a resource by
# (resource_type, resource_id) — polymorphic, so chat_artifact today and
# dashboards/others later ride ONE audited token stack instead of per-type
# copies. Improves on DA's dashboard_link_token: a `visibility` axis (public vs
# workspace-members-with-link), a curator-facing `label`, and last_accessed_at.
# Keeps DA's hardening: SHA-256 token_hash (UNIQUE), non-secret token_short,
# optional expiry, soft-delete revoke + who-revoked, CHECK constraints, partial
# active-link index.
share_link = Table(
    "share_link",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),

    Column(
        "resource_type",
        PgEnum(ShareLinkResourceTypeEnum, name="share_link_resource_type",
               values_callable=lambda enum: [e.value for e in enum]),
        nullable=False,
    ),
    # Polymorphic — references different tables by resource_type, so deliberately
    # NOT a FK. The service validates the target on mint/resolve.
    Column("resource_id", UUID(as_uuid=False), nullable=False),

    # public = anyone with the link; workspace = authenticated members only.
    # Defaults to workspace (private-first) — a snapshot may carry restricted
    # data, so public exposure must be an explicit, audited choice.
    Column(
        "visibility",
        PgEnum(ShareLinkVisibilityEnum, name="share_link_visibility",
               values_callable=lambda enum: [e.value for e in enum]),
        nullable=False,
        server_default=text("'workspace'"),
    ),

    # SHA-256 hex of the plaintext token — the DB never stores the secret.
    Column("token_hash", String(64), nullable=False),
    # First 8 chars of the plaintext — a non-secret handle for the curator UI.
    Column("token_short", String(12), nullable=False),
    # Optional curator-facing name so many links stay distinguishable.
    Column("label", String(255), nullable=True),

    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=True),
    # Soft-delete: revoked links stay for the audit trail; NULL = active.
    Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
    Column("revoked_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),

    Column("accessed_count", Integer, nullable=False, server_default=text("0")),
    Column("last_accessed_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    CheckConstraint("expires_at IS NULL OR expires_at > created_at", name="ck_share_link_expiry_after_creation"),
    CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="ck_share_link_revoke_after_creation"),

    # Single-row resolve: hash the token, look it up by this unique index.
    Index("ix_share_link_token_hash", "token_hash", unique=True),
    # A resource's active links: WHERE resource_type/id AND revoked_at IS NULL.
    Index(
        "ix_share_link_resource_active",
        "resource_type", "resource_id",
        postgresql_where=text("revoked_at IS NULL"),
    ),
)



# ---------------------------------------------------------------------------
# user_memory (NC-519) — long-term, per-user agent memory.
#
# NC-416's context window solves conversation LENGTH; it does nothing across
# conversations, and its compaction actively discards the detail a memory layer
# wants to keep. This table is the cross-chat half: durable facts, preferences
# and corrections that survive the chat they were learned in.
#
# Postgres is the SOURCE OF TRUTH. A mirror doc lands in the per-tenant
# Elasticsearch index ``memories_tenant_{tenant}`` purely for hybrid retrieval
# (BM25 + kNN) and is rebuildable from these rows at any time — so an ES outage
# degrades recall, never correctness.
#
# Scoping: keyed on ``user_id`` (the JWT's ``user_id``), NOT ``member.id``.
# Document ACLs are member-keyed because the file-permission store keys by
# member (NC-131), but memory is ours end-to-end and agent-platform already
# holds user_id from the internal token — keying on it avoids a
# connector-service round-trip on every turn.
#
# ``kind`` / ``origin`` / ``scope`` are String + CHECK rather than PgEnum, a
# deliberate deviation from chat_artifact.kind: all three sets are expected to
# GROW (procedural memories, workspace-shared scope), and extending a CHECK is
# a one-line migration where ALTER TYPE ... ADD VALUE cannot be rolled back.
# ---------------------------------------------------------------------------
user_memory = Table(
    "user_memory",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    # NOT NULL and CASCADE: a memory has no meaning without its subject, and a
    # deleted user's memories must not outlive them (GDPR erasure rides the FK).
    Column("user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    # NULLABLE, unlike chat.workspace_id (X-CHAT-WS-1). v1 always writes it set,
    # so memory learned in one workspace does not leak into another. NULL is
    # reserved for "follows the user across workspaces" — a product decision we
    # have not taken yet, and the column shape must not force it either way.
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=True),

    # Who the memory is ABOUT. 'user' today; 'workspace'/'tenant' are reserved
    # so team-shared memory needs no migration, only a read-path change.
    Column("scope", String(16), nullable=False, server_default=text("'user'")),
    # Agent Studio (decision 22): scope='team' memories belong to a Team, not a
    # person. CASCADE with the team; agent_id records which specialist wrote it
    # and is SET NULL so deleting an agent keeps what the team learned.
    Column("team_id", UUID(as_uuid=False), ForeignKey("studio_team.id", ondelete="CASCADE"), nullable=True),
    Column("agent_id", UUID(as_uuid=False), ForeignKey("studio_agent.id", ondelete="SET NULL"), nullable=True),
    # fact       — durable, reusable state ("owns the APAC region")
    # preference — changes output shape ("wants the SQL shown")
    # correction — a domain fix ("revenue means net of returns")
    # Deliberately no 'episodic': "what happened in chat X" is what chat history
    # and the artifact index already are, and duplicating it invites recall of
    # stale narrative.
    Column("kind", String(32), nullable=False),
    Column("content", Text, nullable=False),
    # sha256 of the normalized content. Lets the extractor short-circuit an
    # exact repeat to NOOP without spending an LLM call on reconciliation, and
    # backs the per-user uniqueness index below.
    Column("content_hash", String(64), nullable=False),
    Column("confidence", Float, nullable=False, server_default=text("0.5")),
    # How many separate turns have asserted this. Reinforcement, not a guess:
    # an extractor's confidence number is its own opinion, whereas being said
    # twice is evidence. Drives promotion out of `candidate` (see `status`).
    Column("observation_count", Integer, nullable=False, server_default=text("1")),
    # candidate — extracted once, NOT injected yet. Held until a second
    #             observation promotes it, which is the cheapest defence against
    #             the overgeneralisation that makes consolidated memory decay
    #             below a no-memory baseline (arXiv 2605.12978).
    # active    — injected into turns.
    # proposed  — recognised as ORG knowledge, not personal: it names something
    #             in the DA catalog, so it was routed there as an
    #             `ai_suggested` description for review instead of becoming one
    #             analyst's private definition. Never injected.
    Column("status", String(16), nullable=False, server_default=text("'active'")),
    # auto     — background extraction
    # explicit — the agent called save_memory ("remember that…")
    # manual   — the user typed it into the Memory settings tab
    Column("origin", String(16), nullable=False),

    # The verbatim span this memory was derived from. Keeping it makes a memory
    # a claim ABOUT evidence rather than a replacement for it: a wrong
    # abstraction can be re-derived, and a consolidation pass can be diffed
    # against the source instead of being trusted. Anthropic's Dreams keeps the
    # input store for this reason; OpenAI's Dreaming V3 overwrites in place and
    # gives up the ability to tell whether it is working.
    Column("source_excerpt", Text, nullable=True),

    # BI-TEMPORAL, kept separate from created_at on purpose:
    #   created_at            — when WE learned it
    #   valid_from / valid_to — when it was true in the world
    # "Worked on APAC until March" needs both, and a store that only knows when
    # it heard something cannot resolve two memories that disagree. NULL
    # valid_to means "still true as far as we know".
    Column("valid_from", TIMESTAMP(timezone=True), nullable=True),
    Column("valid_to", TIMESTAMP(timezone=True), nullable=True),

    # Provenance — "learned in this chat". SET NULL, not CASCADE: a memory is a
    # durable conclusion that must outlive the conversation that produced it
    # (same reasoning as chat_artifact.message_id).
    Column("source_chat_id", UUID(as_uuid=False), ForeignKey("chat.id", ondelete="SET NULL"), nullable=True),
    Column("source_message_id", UUID(as_uuid=False), ForeignKey("message.id", ondelete="SET NULL"), nullable=True),

    # Reconciliation lineage. An UPDATE decision inserts the new row and points
    # the old one here before soft-deleting it, so "what did we believe, and
    # when did we stop believing it" is answerable. Self-FK SET NULL so the
    # superseded row survives deletion of its successor.
    Column(
        "superseded_by",
        UUID(as_uuid=False),
        ForeignKey("user_memory.id", ondelete="SET NULL"),
        nullable=True,
    ),

    # Usage telemetry, stamped off the critical path. Drives decay: an unused,
    # unpinned, low-confidence memory is the first thing to expire.
    Column("last_used_at", TIMESTAMP(timezone=True), nullable=True),
    Column("use_count", Integer, nullable=False, server_default=text("0")),
    # "Always remember this" — exempt from decay and from the retrieval token
    # budget's drop list.
    Column("pinned", Boolean, nullable=False, server_default=text("false")),

    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),

    CheckConstraint("scope IN ('user', 'workspace', 'tenant', 'team')", name="ck_user_memory_scope"),
    CheckConstraint("scope <> 'team' OR team_id IS NOT NULL", name="ck_user_memory_team_scope_has_team"),
    CheckConstraint("kind IN ('fact', 'preference', 'correction')", name="ck_user_memory_kind"),
    CheckConstraint("origin IN ('auto', 'explicit', 'manual')", name="ck_user_memory_origin"),
    CheckConstraint(
        "status IN ('candidate', 'active', 'proposed')", name="ck_user_memory_status"
    ),
    CheckConstraint("observation_count >= 1", name="ck_user_memory_observation_count"),
    CheckConstraint(
        "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
        name="ck_user_memory_validity_order",
    ),
    CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_user_memory_confidence_range"),
    CheckConstraint("length(content) > 0", name="ck_user_memory_content_not_blank"),
    # A memory cannot supersede itself — an applier bug would otherwise create a
    # row that is both live and retired.
    CheckConstraint("superseded_by IS NULL OR superseded_by <> id", name="ck_user_memory_no_self_supersede"),

    # The hot path: every list/retrieve is
    # WHERE tenant_id = :t AND user_id = :u AND deleted_at IS NULL.
    Index(
        "ix_user_memory_tenant_user",
        "tenant_id", "user_id",
        postgresql_where=text("deleted_at IS NULL"),
    ),
    # Retrieval only ever wants `active`; the settings tab wants everything.
    Index(
        "ix_user_memory_active",
        "tenant_id", "user_id", "status",
        postgresql_where=text("deleted_at IS NULL"),
    ),
    # Exact-duplicate guard, per user. Partial on deleted_at so re-learning
    # something the user previously deleted is allowed (they may have deleted it
    # because it was stale, not because it was wrong forever).
    Index(
        "ix_user_memory_dedupe",
        "tenant_id", "user_id", "content_hash",
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    ),
    # "What did this chat teach us" — provenance drill-down and per-chat purge.
    Index("ix_user_memory_source_chat", "source_chat_id"),
)


# ---------------------------------------------------------------------------
# user_memory_settings (NC-519) — per-user opt-in for the memory layer.
#
# The platform's FIRST user-preferences table: today the Preferences tab writes
# localStorage only. Kept deliberately narrow for that reason — this is not a
# general-purpose user-settings bag, and it should not become one.
#
# ``enabled`` defaults TRUE: memory is opt-OUT, not opt-in. The gate that keeps
# an environment dark is the service-level ``unified_memory_enabled`` flag, which
# still ships False — so nothing is captured anywhere until an operator turns the
# feature on for that deployment. Within an enabled deployment, though, every
# user captures without having to find a settings page first.
#
# Note what this means and does not mean: a user who has never opened Settings →
# Memory has NO ROW here, and the read path resolves that absence to the same
# defaults, so "never asked" and "opted in" are deliberately indistinguishable.
# Incognito chats remain excluded regardless.
#
# Mirrors the shape of workspace_da_settings: scope column as PK, booleans,
# timestamps.
# ---------------------------------------------------------------------------
user_memory_settings = Table(
    "user_memory_settings",
    metadata,

    Column(
        "user_id",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),

    # Master switch. TRUE by default — memory is opt-OUT. Turning it off here is
    # what stops capture and injection for this user; the service-level
    # ``unified_memory_enabled`` flag is what keeps a whole environment dark.
    Column("enabled", Boolean, nullable=False, server_default=text("true")),
    # Per-kind opt-outs, for the user who wants preferences remembered but not
    # facts about their role. All TRUE so ``enabled`` alone is the only switch a
    # user has to find.
    Column("capture_facts", Boolean, nullable=False, server_default=text("true")),
    Column("capture_preferences", Boolean, nullable=False, server_default=text("true")),
    Column("capture_corrections", Boolean, nullable=False, server_default=text("true")),

    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
)


workspace = Table(
    "workspace",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=True),
    Column("status", PgEnum(WorkspaceStatusEnum, name="workspace_status"), nullable=False, server_default=WorkspaceStatusEnum.ACTIVE.name),
    # Multi-select pillar enablement. Replaces the single-value
    # orchestrator_config.router_mode as source-of-truth for "what
    # this workspace does." During the transition window the gateway
    # writes both; agent-platform still reads router_mode. A later
    # cleanup migration drops router_mode once readers catch up.
    Column(
        "enabled_pillars",
        ARRAY(PgEnum(PillarEnum, name="pillar")),
        nullable=False,
        server_default=text("'{}'::pillar[]"),
    ),
    # NC-500 — presentation, NOT capability. `enabled_pillars` says what
    # the workspace can do; this says whether the chat page offers the
    # member a choice about it. True (the default) hides the sidebar
    # pillar picker and pins chat to Unified, which spans every enabled
    # pillar anyway — the CXO case, where we configure the pillars and
    # the executive should never see the plumbing. An admin turns it off
    # to hand the picker back.
    Column(
        "hide_chat_pillars",
        Boolean,
        nullable=False,
        server_default=text("true"),
    ),
    # the workspace's monthly LLM ceiling in USD, and the default
    # ceiling for one member inside it. NULL means "use the platform default"
    # (``settings.workspace_monthly_usd_cap``), which is what every existing
    # workspace gets on upgrade: a cap nobody set is not a cap of zero.
    # Stored on the workspace rather than in a settings table because there
    # are exactly two numbers and they are read on the path of every LLM call.
    Column("monthly_llm_usd_cap", Numeric(10, 2), nullable=True),
    Column("monthly_llm_usd_cap_per_user", Numeric(10, 2), nullable=True),
    # The pacing ceiling: what one member may spend in one UTC day. NULL
    # derives it from the monthly figure (see app.services.llm_spend.derive),
    # so a workspace that sets nothing still cannot lose its month in a
    # morning.
    Column("daily_llm_usd_cap_per_user", Numeric(10, 2), nullable=True),
    # Share of the monthly cap held back for work no member asked for:
    # enrichment, scheduled workflows, chat titles. Percent, 0-100. NULL is
    # the platform default. Without a reserve the member allowances would sum
    # to the whole cap and background work would be spending money that was
    # already promised to people.
    Column("llm_background_reserve_pct", Numeric(5, 2), nullable=True),
    # Task key -> provider id, the admin's model routing. A task absent here
    # falls back to the platform's own default for that task, then to the
    # workspace's active provider. JSONB rather than a table because it is a
    # handful of keys read alongside the provider config that is being
    # fetched anyway, and a row per key would mean a repository, a migration
    # per new task, and a join on the hottest path in the product.
    Column(
        "llm_task_lanes",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    ),
    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    # Soft-delete-with-grace metadata (NEU-1805 § 1c). The retention
    # runner uses deletion_scheduled_for to decide when to physically
    # remove the row; the value is stored explicitly (rather than
    # computed from deleted_at + grace period) so a future change to
    # the grace constant doesn't silently shift existing pending
    # deletions.
    Column("deletion_scheduled_for", TIMESTAMP(timezone=True), nullable=True),
    # Audit-correlatable; FK SET NULL so a user can be anonymized
    # (GDPR Art. 17) without breaking workspace deletion history.
    Column(
        "deletion_initiated_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),

    # Partial unique index: name uniqueness applies only to active
    # workspaces. Soft-deleted workspaces don't block a new workspace
    # with the same name during the 30-day grace period — without
    # this, deleting "Engineering" would make the name unavailable
    # for 30 days even though the deletion may yet be reversed.
    Index(
        "ux_workspace_tenant_name_active",
        "tenant_id",
        "name",
        unique=True,
        postgresql_where=text("deleted_at IS NULL"),
    ),
    Index("ix_workspace_tenant", "tenant_id"),
    Index("ix_workspace_tenant_status", "tenant_id", "status"),
    Index(
        "ix_workspace_pending_deletion",
        "deletion_scheduled_for",
        postgresql_where=text("deleted_at IS NOT NULL AND deletion_scheduled_for IS NOT NULL"),
    ),
)

workspace_member = Table(
    "workspace_member",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("is_workspace_admin", Boolean, nullable=False, server_default=text("false")),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    # X-WORKSPACE-MEMBER-UX-1 P3 — first-visit timestamp drives the
    # cinematic-welcome trigger. NULL = hasn't visited yet (cinematic
    # plays on next landing). Per-membership-row rather than
    # per-user so a member removed and re-added gets a fresh welcome.
    Column("first_visited_at", TIMESTAMP(timezone=True), nullable=True),

    # this member's own monthly LLM ceiling in USD, raised by an
    # admin for someone the workspace default does not fit. NULL means the
    # workspace default applies, so the column is empty for almost everyone
    # and a grant reads as the exception it is.
    Column("monthly_llm_usd_cap", Numeric(10, 2), nullable=True),
    Column("daily_llm_usd_cap", Numeric(10, 2), nullable=True),

    UniqueConstraint("workspace_id", "user_id", name="ux_workspace_member_workspace_user"),
    Index("ix_workspace_member_workspace", "workspace_id"),
    Index("ix_workspace_member_user", "user_id"),
    Index("ix_workspace_member_workspace_admin", "workspace_id", "is_workspace_admin"),
)

# what one workspace spent on LLM calls, per member, per month.
#
# ONE table answers both questions the product asks. A member's spend is one
# row. The workspace's spend is the sum of its rows for that month, which is a
# few hundred rows at 500 members and is read behind a short Redis cache. A
# second workspace-level table would be a denormalisation that can disagree
# with the rows it summarises, and the disagreement would stay invisible until
# somebody was refused a turn they had not spent.
#
# ``user_id`` is NULL for work no person asked for: an enrichment run, a
# scheduled workflow, a chat title written after the user closed the tab.
# That cost is real and has to land somewhere visible rather than be dropped
# because there is nobody to attribute it to.
#
# Postgres is the ledger and not Redis, because the cap is the only thing
# between a runaway loop and the bill, and a cache flush must not reset it.
# The read is cached; the write never is.
workspace_llm_spend = Table(
    "workspace_llm_spend",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    # SET NULL rather than CASCADE: a member who leaves does not erase what
    # the workspace spent. Their rows survive as unattributed cost.
    Column("user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    # First day of the calendar month, UTC. A date rather than a month/year
    # pair, so range queries are ordinary date comparisons.
    Column("period", Date, nullable=False),

    Column("prompt_tokens", BigInteger, nullable=False, server_default=text("0")),
    Column("completion_tokens", BigInteger, nullable=False, server_default=text("0")),
    Column("cached_tokens", BigInteger, nullable=False, server_default=text("0")),
    Column("llm_calls", BigInteger, nullable=False, server_default=text("0")),
    # Numeric, never float: this accumulates millions of small additions, and
    # a float would drift away from the invoice it exists to predict.
    Column("cost_usd", Numeric(14, 6), nullable=False, server_default=text("0")),

    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    # The UPSERT target. NULLS NOT DISTINCT so the unattributed row (user_id
    # IS NULL) stays ONE row per workspace-month: under the default semantics
    # every NULL is distinct, the conflict clause would never fire, and
    # background work would insert a fresh row per LLM call.
    Index(
        "ux_workspace_llm_spend_period",
        "workspace_id",
        "user_id",
        "period",
        unique=True,
        postgresql_nulls_not_distinct=True,
    ),
    # The workspace total for a month, and the admin table's ordering.
    Index("ix_workspace_llm_spend_workspace_period", "workspace_id", "period"),
    # One member's own usage page, across workspaces.
    Index("ix_workspace_llm_spend_user_period", "user_id", "period"),
)


workspace_access_request = Table(
    "workspace_access_request",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("status", PgEnum(WorkspaceAccessStatusEnum, name="workspace_access_status"), nullable=False, server_default=WorkspaceAccessStatusEnum.PENDING.name),
    Column("requested_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("reviewed_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("reviewed_at", TIMESTAMP(timezone=True), nullable=True),
    Column("review_note", Text, nullable=True),

    Index("ix_workspace_access_request_workspace_status", "workspace_id", "status"),
    Index("ix_workspace_access_request_user_status", "user_id", "status"),
)

workspace_invitation = Table(
    "workspace_invitation",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("inviter", UUID(as_uuid=False), ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("email", String(320), nullable=False, comment="pii:email"),
    Column("is_workspace_admin", Boolean, nullable=False, server_default=text("false")),
    # Optional personal note from the inviter, included verbatim in the
    # invitation email and persisted so resend-invitation flows reuse the
    # same wording. Length is capped at the gateway boundary (Pydantic),
    # not at the column — the DB stays permissive. Tagged pii:freetext
    # because it may contain identifying info (names, role descriptions).
    Column("personal_message", Text, nullable=True, comment="pii:freetext"),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    Column("accepted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    Index("ix_workspace_invitation_workspace_email", "workspace_id", "email"),
    Index("ix_workspace_invitation_email", "email"),
    Index("ix_workspace_invitation_expires_at", "expires_at"),
    Index("ix_workspace_invitation_email_pending", "email", postgresql_where=text("accepted_at IS NULL AND deleted_at IS NULL")),
)

orchestrator_config = Table(
    "orchestrator_config",
    metadata,

    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("workspace_id", UUID(as_uuid=True), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, unique=True),

    Column("router_mode", PgEnum(RouterModeEnum, name="router_mode"), nullable=False, server_default=RouterModeEnum.AUTO.name),
    Column("router_classification_prompt", Text, nullable=True),
    Column("response_synthesis_prompt", Text, nullable=True),

    # Retrieval strategy configuration
    Column("retrieval_strategy", PgEnum(RetrievalStrategyEnum, name="retrieval_strategy"), nullable=False, server_default=RetrievalStrategyEnum.HYBRID.name),
    Column("retrieval_config", JSONB, nullable=False, server_default=text("'{\"top_k\": 3, \"semantic_weight\": 0.3}'::jsonb")),

    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    Index("ix_orchestrator_config_workspace", "workspace_id"),
)

runs = Table(
    "runs",
    metadata,

    Column("id", String(26), primary_key=True),  # ULID
    Column("message_id", UUID(as_uuid=False), ForeignKey("message.id", ondelete="CASCADE"), nullable=False),
    Column("session_id", UUID(as_uuid=False), ForeignKey("chat.id", ondelete="CASCADE"), nullable=True),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("status", PgEnum(RunStatus, name="run_status",values_callable=lambda x: [e.value for e in x]), nullable=False, server_default=text("'pending'")),
    Column("input_message", Text, nullable=False),
    Column("final_answer", Text, nullable=True),
    Column("sources", JSONB, nullable=True),  # Citation sources from enterprise_search

    # Workflow execution tracking
    Column("flow_run_id", String(50), nullable=True),  # Activepieces flow run ID for terminate support

    # HITL (Human-in-the-Loop) support
    Column("waiting_instance_id", String(50), nullable=True),  # Which agent instance is waiting
    Column("input_request", JSONB, nullable=True),  # {"question": "...", "form_schema": {...}}

    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    Index("ix_runs_message_id", "message_id"),
    Index("ix_runs_session_id", "session_id"),
    Index("ix_runs_tenant_id", "tenant_id"),
    Index("ix_runs_workspace_id", "workspace_id"),
    Index("ix_runs_user_id", "user_id"),
    Index("ix_runs_status", "status"),
)



react_conversations = Table(
    "react_conversations",
    metadata,

    Column("id", String(26), primary_key=True),  # ULID
    Column("run_id", String(26), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
    Column("instance_id", String(50), nullable=True),  # Sub-agent invocation ID (prefix + ULID)
    Column("delegation_level", Integer, nullable=False, server_default=text("0")),  # 0=main, 1=sub-agent
    Column("agent_name", String(100), nullable=False),
    Column("role", PgEnum(AgentMessageRole, name="agent_message_role",values_callable=lambda x: [e.value for e in x]), nullable=False),
    Column("content", Text, nullable=False),
    Column("tool_name", String(100), nullable=True),
    Column("tool_params", JSONB, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    Index("ix_react_conversations_run_id", "run_id"),
    Index("ix_react_conversations_instance_id", "instance_id"),
)

run_events = Table(
    "run_events",
    metadata,

    Column("id", String(26), primary_key=True),  # ULID
    Column("run_id", String(26), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
    Column("sequence", Integer, nullable=False, server_default=text("0")),  # Order within run for SSE resume
    Column("event_type", String(50), nullable=False),  # thinking, tool_call, observation, answer, error
    Column("agent_name", String(100), nullable=True),
    Column("instance_id", String(50), nullable=True),  # Sub-agent invocation ID (prefix + ULID)
    Column("data", JSONB, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    Index("ix_run_events_run_id", "run_id"),
    Index("ix_run_events_sequence", "run_id", "sequence"),
)


trace_spans = Table(
    "trace_spans",
    metadata,

    Column("id", String(26), primary_key=True),  # ULID
    Column("run_id", String(26), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
    Column("parent_span_id", String(26), ForeignKey("trace_spans.id", ondelete="CASCADE"), nullable=True),
    Column("sequence", Integer, nullable=False, server_default=text("0")),

    Column("span_type", PgEnum(SpanType, name="span_type", values_callable=lambda x: [e.value for e in x]), nullable=False),
    Column("name", String(200), nullable=False),
    Column("agent_name", String(100), nullable=True),
    Column("status", PgEnum(SpanStatus, name="span_status", values_callable=lambda x: [e.value for e in x]), nullable=False),

    Column("started_at", TIMESTAMP(timezone=True), nullable=False),
    Column("ended_at", TIMESTAMP(timezone=True), nullable=False),
    Column("latency_ms", Integer, nullable=False),

    Column("attributes", JSONB, nullable=True),

    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    Index("ix_trace_spans_run_id", "run_id"),
    Index("ix_trace_spans_run_type", "run_id", "span_type"),
    Index("ix_trace_spans_run_sequence", "run_id", "sequence"),
    Index("ix_trace_spans_parent", "parent_span_id"),
)


excel_datasets = Table(
    "excel_datasets",
    metadata,

    Column("id", String(26), primary_key=True),  # ULID
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("uploaded_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),

    Column("original_filename", String(500), nullable=False),
    Column("schema_name", String(200), nullable=False, unique=True),
    Column("minio_path", String(1000), nullable=False),

    Column("status", PgEnum(ExcelDatasetStatus, name="excel_dataset_status", values_callable=lambda x: [e.value for e in x]), nullable=False),
    Column("table_metadata", JSONB, nullable=True),
    Column("file_size_bytes", BigInteger, nullable=False),
    Column("error_details", Text, nullable=True),

    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    Index("ix_excel_datasets_workspace", "workspace_id"),
    Index("ix_excel_datasets_tenant", "tenant_id"),
)


# ---------------------------------------------------------------------------
# audit_log — append-only compliance event store (NEU-1804, slice C3a).
#
# Every meaningful mutation in the gateway writes a row here. Required by
# SOC 2 (CC6.6), HIPAA (§ 164.312(b)), and GDPR (Art 30, 32). The
# emitter helper lives in the gateway; this is just the storage.
#
# Hard rule: append-only. The BEFORE UPDATE/DELETE trigger below raises
# SQLSTATE 'AU001' so the immutability invariant holds at the database
# level — auditors won't accept "we promise we don't update it."
#
# See user-stories/user-lifecycle.md § "Audit log requirements" for the
# product-level specification and event-type catalog.
# ---------------------------------------------------------------------------

audit_log = Table(
    "audit_log",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    # FK is NO ACTION (default), not CASCADE: a tenant cannot be hard-deleted
    # while audit history references it. The retention runner clears audit_log
    # rows past their window first; tenant teardown happens after.
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id"), nullable=False),
    # Nullable so system-initiated events (cron jobs, runners) can record without an actor.
    # SET NULL: when a user is eventually hard-deleted (post-retention), preserve the
    # audit entry but null out the actor reference.
    Column("actor_user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),

    # Closed catalog — see gateway emitter. Stored as TEXT so the catalog can
    # evolve without alembic churn; PR review enforces additions to the catalog.
    Column("event_type", Text, nullable=False),
    Column("resource_type", Text, nullable=False),
    Column("resource_id", Text, nullable=False),

    # Event-specific structured payload. The emitter is responsible for
    # never putting raw PII into this column — references IDs only.
    # Renamed from `metadata` to avoid clashing with SA DeclarativeBase.metadata.
    Column("event_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),

    # Optional client-side context. PII-tagged so the C6 anonymization runner
    # can wipe these when the actor is erased.
    Column("ip_address", INET, nullable=True, comment="pii:ipaddress"),
    Column("user_agent", Text, nullable=True, comment="pii:freetext"),

    Column("occurred_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    # Tenant-scoped read path: latest events first.
    Index("ix_audit_log_tenant_occurred_at", "tenant_id", text("occurred_at DESC")),
    # Filter by event_type (e.g. show me all workspace.deleted in this tenant).
    Index("ix_audit_log_event_type", "event_type"),
    # "What did user X do" — partial index keeps it small (skips system events).
    Index(
        "ix_audit_log_actor_occurred_at",
        "actor_user_id",
        text("occurred_at DESC"),
        postgresql_where=text("actor_user_id IS NOT NULL"),
    ),
)


# Immutability trigger. Installed via SQLAlchemy event hooks so that
# both Base.metadata.create_all (used by tests) and the alembic
# migration (used in real DBs) end up with the same DDL on the table.
#
# Split into individual statements because asyncpg doesn't support
# multi-statement prepared statements.
_AUDIT_LOG_CREATE_FUNCTION = DDL(
    """
    CREATE OR REPLACE FUNCTION audit_log_block_mutation() RETURNS trigger AS $func$
    BEGIN
        RAISE EXCEPTION 'audit_log is append-only; UPDATE/DELETE blocked'
            USING ERRCODE = 'AU001';
    END;
    $func$ LANGUAGE plpgsql
    """
)
_AUDIT_LOG_DROP_TRIGGER = DDL(
    "DROP TRIGGER IF EXISTS audit_log_immutability ON audit_log"
)
_AUDIT_LOG_CREATE_TRIGGER = DDL(
    """
    CREATE TRIGGER audit_log_immutability
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_block_mutation()
    """
)
_AUDIT_LOG_DROP_FUNCTION = DDL(
    "DROP FUNCTION IF EXISTS audit_log_block_mutation()"
)

# After-create: function first, then trigger (idempotent — drop-if-exists first).
event.listen(audit_log, "after_create", _AUDIT_LOG_CREATE_FUNCTION.execute_if(dialect="postgresql"))
event.listen(audit_log, "after_create", _AUDIT_LOG_DROP_TRIGGER.execute_if(dialect="postgresql"))
event.listen(audit_log, "after_create", _AUDIT_LOG_CREATE_TRIGGER.execute_if(dialect="postgresql"))

# Before-drop: trigger first, then function.
event.listen(audit_log, "before_drop", _AUDIT_LOG_DROP_TRIGGER.execute_if(dialect="postgresql"))
event.listen(audit_log, "before_drop", _AUDIT_LOG_DROP_FUNCTION.execute_if(dialect="postgresql"))


# ─────────────────────────────────────────────────────────────────
# tenancy_ownership_transfer (NEU-X3)
# ─────────────────────────────────────────────────────────────────
#
# Two-step ownership transfer per user-stories/tenant-admin-actions.md
# § 4. Primary Owner initiates a transfer to a target Tenant Admin;
# the target accepts via an email link within 7 days; the atomic
# UPDATE swaps tenant.tenant_owner. The retention runner cancels
# expired pending transfers nightly.
tenancy_ownership_transfer = Table(
    "tenancy_ownership_transfer",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "tenant_id",
        UUID(as_uuid=False),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # SET NULL on user delete: the transfer record survives a GDPR
    # erasure of the actor; audit_log.actor_user_id captures the
    # identity at time-of-action, which is what auditors care about.
    Column(
        "from_user_id",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "to_user_id",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    # Random hex string used in the FE accept URL. Globally unique
    # so the URL alone identifies the transfer; eliminates the need
    # for the FE to know the tenant_id when handling /tenants/transfer/{token}.
    #
    # DEPRECATED at-rest (D-1): a plaintext capability token in the DB means any
    # read-only dump yields a live tenant-takeover URL. Kept NON-NULL for now so
    # existing consumers (gateway/workflow) that still write/read `token` don't
    # break — see token_hash/token_short below for the hardened path they must
    # migrate to. Once every consumer resolves by token_hash, a follow-up
    # migration can drop this column.
    Column("token", Text, nullable=False, unique=True),
    # Hardened at-rest shape mirroring share_link / dashboard_link_token:
    # store SHA-256(plaintext) here, never the secret itself; resolve the accept
    # URL by hashing the presented token and looking it up on ix_ownership_transfer_token_hash.
    # Nullable during the additive rollout: rows written by not-yet-updated
    # consumers carry NULL until backfilled. The mint response is the ONLY place
    # the plaintext should appear.
    Column("token_hash", String(64), nullable=True),
    # First chars of the plaintext — a non-secret handle for UI/audit display.
    Column("token_short", String(12), nullable=True),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    Column("accepted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("cancelled_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    # Only ONE pending transfer per tenant at a time. Without this
    # an Owner could fire off competing transfers and we'd race over
    # which token wins. accepted_at IS NULL AND cancelled_at IS NULL
    # captures "still pending" — the runner cancels expired ones.
    Index(
        "ux_ownership_transfer_pending_per_tenant",
        "tenant_id",
        unique=True,
        postgresql_where=text(
            "accepted_at IS NULL AND cancelled_at IS NULL"
        ),
    ),
    Index("ix_ownership_transfer_token", "token"),
    # Hash-at-rest resolve path (D-1): single-row lookup by SHA-256(token).
    # Partial + unique so many pre-rollout NULLs coexist while non-null hashes
    # stay globally unique.
    Index(
        "ix_ownership_transfer_token_hash",
        "token_hash",
        unique=True,
        postgresql_where=text("token_hash IS NOT NULL"),
    ),
    # Partial read index for the retention runner's expiry sweep.
    Index(
        "ix_ownership_transfer_pending_expires",
        "expires_at",
        postgresql_where=text(
            "accepted_at IS NULL AND cancelled_at IS NULL"
        ),
    ),
)


# ============================================================================
# Data Analytics — canonical metadata schema (NEU-1811 DA-P0).
#
# Seven tables encode the DA pillar's per-warehouse curated state. Spec:
# ``product-feature-roadmap/data-analytics/data-flow.md`` §4.8.
#
# Service ownership (feature.md F4):
#   * ``da_connection`` — connector-service owns lifecycle CRUD
#   * the six workspace_metadata_* / metric / join_hint / description_version
#     tables — agent-platform owns every write (metadata sync, LLM calls,
#     curation acceptance, etc.)
# ============================================================================


# ---------------------------------------------------------------------------
# da_connection — tenant-level Connection (Step 1 in data-flow.md).
#
# One row per tenant warehouse credential. Same physical warehouse can be
# represented by two rows (e.g. two Snowflake accounts on one tenant) — the
# unique key is (tenant_id, source_type, connection_name).
#
# Distinct from the legacy ``connections`` table above (which is the ES
# connector table — SharePoint / Drive workspace-scoped OAuth). The two
# entities have different semantics; co-locating them would be the kind
# of conflation called out in feature.md F4.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# da_catalog_schema / da_catalog_table / da_catalog_column — tenant-level
# facts about what's in the warehouse (DA-P1g refactor).
#
# Why these are tenant-scoped, not workspace-scoped: a column either IS
# or ISN'T PII; "users.email" has one true type regardless of which
# workspace is looking at it. Production catalog systems (Looker, dbt,
# Hex, Metabase) all separate the catalog (facts) from per-team curation
# (opinions). Workspace-level enrichment lives on the
# workspace_curation_da_* overlays below.
# ---------------------------------------------------------------------------

da_catalog_schema = Table(
    "da_catalog_schema",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    # DA-U2: DA connections now live on the unified `integration` table, so this
    # FK targets `integration.id`. The column keeps its legacy name
    # `da_connection_id` for now — renaming it to `integration_id` would cascade
    # into the connector-service + agent-platform readers, so that's deferred to
    # a coordinated cleanup once both are on integration (TD-DA-CATALOG-COLNAME).
    Column(
        "da_connection_id",
        UUID(as_uuid=False),
        ForeignKey("integration.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("schema_name", String(255), nullable=False),
    Column("schema_description", Text, nullable=True),
    # Compliance classification — see DA-P1i.3. Schema-level tags
    # propagate to every table + column inside (effective-at-read).
    Column(
        "is_pii",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "is_restricted",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column("last_synced_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    Index(
        "ux_da_catalog_schema_conn_name",
        "da_connection_id",
        "schema_name",
        unique=True,
    ),
    Index("ix_da_catalog_schema_conn", "da_connection_id"),
)


da_catalog_table = Table(
    "da_catalog_table",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "da_catalog_schema_id",
        UUID(as_uuid=False),
        ForeignKey("da_catalog_schema.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("table_name", String(255), nullable=False),
    Column(
        "table_type",
        PgEnum(
            DATableTypeEnum,
            name="da_table_type",
            values_callable=lambda enum: [e.value for e in enum],
            create_type=False,
        ),
        nullable=False,
        server_default=text("'table'"),
    ),
    Column("native_comment", Text, nullable=True),
    Column("row_count", BigInteger, nullable=True),
    # Table-level compliance classification — see DA-P1i.3. Propagates
    # to every column in this table (effective-at-read).
    Column(
        "is_pii",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "is_restricted",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column("last_synced_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    Index(
        "ux_da_catalog_table_schema_name",
        "da_catalog_schema_id",
        "table_name",
        unique=True,
    ),
    Index("ix_da_catalog_table_schema", "da_catalog_schema_id"),
)


# ---------------------------------------------------------------------------
# da_catalog_column — TWO-WRITER row with documented column ownership.
#
# Multiple services write to this row on different columns; this is the
# fine pattern (each column has a single owner). See
# `product-feature-roadmap/data-analytics/description-generation.md`
# discussion log 2026-05-12 — "Classification stays in connector-service".
#
# Column ownership:
#
#   * Sync (connector-service.ConnectionService.sync_catalog):
#       column_name, data_type, nullable, is_primary_key, is_foreign_key,
#       foreign_key_to, native_comment, ordinal_position, last_synced_at,
#       created_at, updated_at
#
#   * Classification (connector-service.ConnectionService
#     .patch_catalog_column_classification):
#       is_pii, is_restricted
#
# Hard invariant: sync's UPDATE branch MUST NOT touch is_pii / is_restricted
# (would race against classification). Sync writes are upserts that
# preserve classification state on existing rows.
# ---------------------------------------------------------------------------

da_catalog_column = Table(
    "da_catalog_column",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "da_catalog_table_id",
        UUID(as_uuid=False),
        ForeignKey("da_catalog_table.id", ondelete="CASCADE"),
        nullable=False,
    ),

    # DDL-derived facts
    Column("column_name", String(255), nullable=False),
    Column("data_type", String(255), nullable=False),
    Column("nullable", Boolean, nullable=False),
    Column(
        "is_primary_key",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "is_foreign_key",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    # List of {target_schema, target_table, target_column}.
    Column("foreign_key_to", JSONB, nullable=True),
    Column("native_comment", Text, nullable=True),
    Column("ordinal_position", Integer, nullable=False),

    # Compliance classification — tenant-owned, no workspace override
    # for is_pii at all; is_restricted can only be upgraded by workspace
    # via workspace_curation_da_column.is_restricted_override.
    Column(
        "is_pii",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "is_restricted",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),

    Column("last_synced_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    Index(
        "ux_da_catalog_column_table_name",
        "da_catalog_table_id",
        "column_name",
        unique=True,
    ),
    Index("ix_da_catalog_column_table", "da_catalog_table_id"),
)


# ---------------------------------------------------------------------------
# workspace_curation_da_table / workspace_curation_da_column — workspace
# opinion overlays on top of the tenant catalog (DA-P1g refactor).
#
# Thin rows: "this workspace exposes this catalog row to its users",
# plus per-workspace AI / admin descriptions, synonyms, sample values,
# etc. The same column can be described differently for different teams
# (sales workspace ≠ finance workspace), so enrichment lives here.
# Compliance classification (is_pii / is_restricted) lives on the
# catalog — a workspace cannot disagree about PII status.
# ---------------------------------------------------------------------------

workspace_curation_da_table = Table(
    "workspace_curation_da_table",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "da_catalog_table_id",
        UUID(as_uuid=False),
        ForeignKey("da_catalog_table.id", ondelete="CASCADE"),
        nullable=False,
    ),

    # Per-workspace opinion / context.
    #
    # DA-P1l.1.0 collapsed the two-field model (admin_seed_description +
    # ai_generated_description) into a single ``description`` field with
    # trust metadata below. See description-generation.md §M1, M2.
    Column("table_logical_name", String(255), nullable=True),
    Column("description", Text, nullable=True),
    # DA-P1k.1 — workspace-scoped alt names; same shape as the
    # equivalent ``workspace_curation_da_column.synonyms``. NULL =
    # not set; empty list semantically equivalent.
    Column("synonyms", JSONB, nullable=True),

    # Trust metadata (M2). origin records who wrote the current
    # description text — 'human' or 'ai'. Admin edits flip it to 'human'
    # and clear ai_accepted_at; Generate / Regenerate flip it to 'ai'
    # and stamp ai_last_generated_at. ai_accepted_at is the HITL gate:
    # chat (T2S) trusts an ai-origin description only when this is set.
    Column(
        "description_origin",
        String(8),
        nullable=False,
        server_default=text("'human'"),
    ),
    Column("ai_accepted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("ai_last_generated_at", TIMESTAMP(timezone=True), nullable=True),

    # Curation
    Column(
        "is_included",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "is_archived",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column("last_enriched_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    CheckConstraint(
        "description_origin IN ('human', 'ai')",
        name="ck_wcdt_description_origin",
    ),
    Index(
        "ux_wcdt_workspace_catalog",
        "workspace_id",
        "da_catalog_table_id",
        unique=True,
    ),
    Index("ix_wcdt_workspace", "workspace_id"),
    Index("ix_wcdt_catalog", "da_catalog_table_id"),
)


workspace_curation_da_column = Table(
    "workspace_curation_da_column",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "da_catalog_column_id",
        UUID(as_uuid=False),
        ForeignKey("da_catalog_column.id", ondelete="CASCADE"),
        nullable=False,
    ),

    # Per-workspace LLM context.
    #
    # DA-P1l.1.0 collapsed the two-field model into a single ``description``
    # field with trust metadata below. See description-generation.md §M1, M2.
    Column("column_logical_name", String(255), nullable=True),
    Column("description", Text, nullable=True),
    Column("synonyms", JSONB, nullable=True),
    Column("unit", String(64), nullable=True),
    Column("format_hint", String(64), nullable=True),
    Column("valid_aggregations", JSONB, nullable=True),

    # Trust metadata (M2). Same semantics as workspace_curation_da_table.
    Column(
        "description_origin",
        String(8),
        nullable=False,
        server_default=text("'human'"),
    ),
    Column("ai_accepted_at", TIMESTAMP(timezone=True), nullable=True),
    Column("ai_last_generated_at", TIMESTAMP(timezone=True), nullable=True),

    # Phase-2 enrichment. DA-P1l.1.0 lifted the sampling toggle to the
    # workspace level (workspace_da_settings.da_include_sample_values)
    # per M11 — per-column was redundant because catalog flags
    # (PII / Restricted) already hard-block sampling and is_included
    # already controls whether the column is curated at all.
    # sample_values can hold real PII from the warehouse — tagged so the
    # C6 anonymization runner can null these on user erasure.
    Column(
        "sample_values",
        JSONB,
        nullable=True,
        comment="pii:freetext",
    ),
    Column("cardinality_score", Float, nullable=True),
    Column("statistical_profile", JSONB, nullable=True),

    # Upgrade-only restricted override (compliance posture).
    Column(
        "is_restricted_override",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),

    # Curation
    Column(
        "is_included",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "is_archived",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column("last_enriched_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    CheckConstraint(
        "description_origin IN ('human', 'ai')",
        name="ck_wcdc_description_origin",
    ),
    Index(
        "ux_wcdc_workspace_catalog",
        "workspace_id",
        "da_catalog_column_id",
        unique=True,
    ),
    Index("ix_wcdc_workspace", "workspace_id"),
    Index("ix_wcdc_catalog", "da_catalog_column_id"),
)


# ---------------------------------------------------------------------------
# workspace_da_suggested_question — the stored pool of chat starter questions
# for one workspace (NC-570).
#
# Until this table existed, the chat empty state composed its DA cards from
# three string templates on the request path. The result was honest after
# NC-567, because nothing reached a sentence without a business name and a
# statistical profile behind it, but it was still assembled prose. A senior,
# non technical reader does not recognise "Break down Net revenue by Sales
# region in Sales orders" as a question they asked. Generation therefore moves
# into the enrichment run, where a language model writes the sentence against
# the same evidence, and the result is stored here.
#
# One row is one question. The row carries the catalog identity the serve
# boundary needs, so nothing has to be recovered from the finished sentence:
#
#   * da_catalog_table_id / da_catalog_schema_id — where the question comes
#     from. The permission filter walks column -> table -> schema, so it needs
#     the schema as well as the table.
#   * da_catalog_column_ids — every column the sentence names. This is what
#     makes the NC-568 filter possible: a member denied one column must not
#     read its business name off a suggested question. NOT NULL, because a
#     question that records no column cannot be proved safe and the filter
#     fails closed on an empty list.
#
# ``shape`` is load bearing and not decoration. It is the question's kind — a
# trend, a breakdown, a total, a ranking — and it carries the icon the client
# renders. The serve boundary groups the pool by shape and draws round the
# groups in turn, so four cards on one screen are four different kinds of
# question rather than one sentence repeated four times. Storing the icon
# alone would work today and lose the grouping the moment two shapes shared an
# icon, so the kind is stored and the icon is derived from it.
#
# ``origin`` matches the ``description_origin`` house style on the
# workspace_curation_da_* overlays: a short string with a check constraint
# rather than a native enum, so adding a value later is a constraint change
# and not a type migration. 'ai' is what the enrichment run writes; 'template'
# records a row put here by the deterministic composer, which keeps the door
# open for a workspace that will never run a model.
#
# Every foreign key cascades. A removed connection, schema or table takes its
# questions with it, because a question about a table that no longer exists is
# exactly the "names something that isn't there" failure this whole feature
# was written to remove. ``generated_by_run_id`` is the one exception: it is
# provenance, so a deleted enrichment run leaves the questions in place with a
# NULL run.
# ---------------------------------------------------------------------------

workspace_da_suggested_question = Table(
    "workspace_da_suggested_question",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "tenant_id",
        UUID(as_uuid=False),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # The DA connection is an ``integration`` row, and the column keeps the DA
    # domain name the rest of the catalog uses (see da_catalog_schema).
    Column(
        "da_connection_id",
        UUID(as_uuid=False),
        ForeignKey("integration.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "da_catalog_schema_id",
        UUID(as_uuid=False),
        ForeignKey("da_catalog_schema.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "da_catalog_table_id",
        UUID(as_uuid=False),
        ForeignKey("da_catalog_table.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # JSONB list[str] of da_catalog_column.id. A list and not a join table:
    # the value is read whole, never queried by element, and it is rewritten
    # with its question rather than edited.
    Column("da_catalog_column_ids", JSONB, nullable=False),

    Column("question_text", Text, nullable=False),
    Column("shape", String(32), nullable=False),
    Column(
        "origin",
        String(8),
        nullable=False,
        server_default=text("'ai'"),
    ),

    # Provenance. SET NULL so pruning old runs never deletes the pool.
    Column(
        "generated_by_run_id",
        UUID(as_uuid=False),
        ForeignKey("da_enrichment_run.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "generated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    CheckConstraint(
        "origin IN ('template', 'ai')",
        name="ck_wdsq_origin",
    ),
    # The serve path's only lookup: this workspace's pool, narrowed to the
    # connections it may currently query.
    Index("ix_wdsq_workspace_connection", "workspace_id", "da_connection_id"),
    # The write path's lookup: delete then insert per table.
    Index("ix_wdsq_table", "da_catalog_table_id"),
)


# ---------------------------------------------------------------------------
# workspace_da_settings — workspace-level DA settings (DA-P1l.1.0).
#
# Holds workspace-level toggles that govern AI description generation
# behaviour. See M11 in product-feature-roadmap/data-analytics/
# description-generation.md. One row per workspace, PK == FK to
# workspace(id). Row is lazy-created on first PATCH; absence means
# defaults apply.
#
# Future DA workspace settings (default model preference, cost cap,
# etc.) land here rather than as JSONB sprawl on the workspace row.
# ---------------------------------------------------------------------------

workspace_da_settings = Table(
    "workspace_da_settings",
    metadata,

    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        primary_key=True,
    ),

    # M11 toggles. Both default TRUE (fail-safe).
    #
    # da_include_sample_values: whether the TOP VALUES block appears in
    # column prompts. PII/Restricted columns are skipped regardless
    # (catalog hard-gate, M10).
    #
    # da_pii_redaction_enabled: whether to wrap LLM calls in GovernedLLM
    # (PII pattern redaction in-flight). Reduces description quality
    # when on — recommended only if workspace's LLM provider isn't a
    # trusted private tenant.
    Column(
        "da_include_sample_values",
        Boolean,
        nullable=False,
        server_default=text("true"),
    ),
    Column(
        "da_pii_redaction_enabled",
        Boolean,
        nullable=False,
        server_default=text("true"),
    ),

    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)


# ---------------------------------------------------------------------------
# da_enrichment_run (NC-103) — one row per triggered Reprofile / Regenerate
# run. The command record (scope × operation × target) + Temporal handle +
# rollup counters. Temporal owns execution truth; this projection is what the
# Data Curation page polls and re-attaches to across refreshes.
# ---------------------------------------------------------------------------
da_enrichment_run = Table(
    "da_enrichment_run",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "tenant_id",
        UUID(as_uuid=False),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # The DA connection is an ``integration`` row (unified integration
    # model). Mirrors da_catalog_schema.da_connection_id → integration.id;
    # named ``connection_id`` here to match the DA domain vocabulary.
    Column(
        "connection_id",
        UUID(as_uuid=False),
        ForeignKey("integration.id", ondelete="CASCADE"),
        nullable=False,
    ),

    # Discriminators — what this run targets and which stage(s) it runs.
    Column(
        "scope",
        PgEnum(
            DAEnrichmentScopeEnum,
            name="da_enrichment_scope",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    Column(
        "operation",
        PgEnum(
            DAEnrichmentOperationEnum,
            name="da_enrichment_operation",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    # Targets, selected by scope. connection-scope carries neither.
    Column(
        "schema_id",
        UUID(as_uuid=False),
        ForeignKey("da_catalog_schema.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column(
        "table_id",
        UUID(as_uuid=False),
        ForeignKey("da_catalog_table.id", ondelete="CASCADE"),
        nullable=True,
    ),

    # Lifecycle + rollup. status starts 'pending'; counters drive the
    # header progress bar without aggregating the item rows on read.
    Column(
        "status",
        PgEnum(
            DAEnrichmentRunStatusEnum,
            name="da_enrichment_run_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'pending'"),
    ),
    Column("total_tables", Integer, nullable=False, server_default=text("0")),
    Column("completed_tables", Integer, nullable=False, server_default=text("0")),
    Column("failed_tables", Integer, nullable=False, server_default=text("0")),
    Column("skipped_tables", Integer, nullable=False, server_default=text("0")),

    # Link back to the durable execution (truth lives in Temporal history).
    Column("temporal_workflow_id", Text, nullable=True),
    Column("temporal_run_id", Text, nullable=True),

    # Actor (NULL = system-initiated). SET NULL so a user delete doesn't
    # cascade away the audit trail of past runs.
    Column(
        "created_by_user_id",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("error", Text, nullable=True),

    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("finished_at", TIMESTAMP(timezone=True), nullable=True),

    # Active-run lookup for the curation page's re-attach-on-refresh.
    Index("ix_da_enrichment_run_workspace_status", "workspace_id", "status"),
    Index("ix_da_enrichment_run_connection_status", "connection_id", "status"),
    # NC-474 — the same lookup narrowed to one action. Profiling and description
    # generation run independently, so "is a Generate active here?" filters on
    # ``operation`` too. The two-column index above still serves the
    # reconciler's operation-blind sweep.
    Index(
        "ix_da_enrichment_run_connection_operation_status",
        "connection_id",
        "operation",
        "status",
    ),
)


# ---------------------------------------------------------------------------
# da_enrichment_table_item (NC-103) — per-table, two-stage progress for a run.
# profile_status / describe_status advance independently; NULL on a stage =
# that stage is not part of this run's operation. Drives the live
# "Profiling…" / "Generating…" / "Profiled ✓" badges per row.
# ---------------------------------------------------------------------------
da_enrichment_table_item = Table(
    "da_enrichment_table_item",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "run_id",
        UUID(as_uuid=False),
        ForeignKey("da_enrichment_run.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "da_catalog_table_id",
        UUID(as_uuid=False),
        ForeignKey("da_catalog_table.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # Denormalized so the UI renders rows without joining the catalog.
    Column("schema_name", String(255), nullable=False),
    Column("table_name", String(255), nullable=False),

    # Two stages. NULL = stage not applicable to this run's operation.
    Column(
        "profile_status",
        PgEnum(
            DAEnrichmentStageStatusEnum,
            name="da_enrichment_stage_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=True,
    ),
    Column(
        "describe_status",
        PgEnum(
            DAEnrichmentStageStatusEnum,
            name="da_enrichment_stage_status",
            values_callable=lambda enum: [e.value for e in enum],
            create_type=False,
        ),
        nullable=True,
    ),
    Column("columns_total", Integer, nullable=True),
    Column("columns_described", Integer, nullable=False, server_default=text("0")),
    Column("error", Text, nullable=True),

    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("finished_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    UniqueConstraint(
        "run_id", "da_catalog_table_id",
        name="uq_da_enrichment_table_item_run_table",
    ),
    Index("ix_da_enrichment_table_item_run", "run_id"),
)


# ---------------------------------------------------------------------------
# workspace_integration_settings — per-workspace connector governance policy
# (WF-CF-1b). Cross-pillar (NOT DA-specific): the workspace-admin switches
# that gate how members may use connectors here. One row per workspace,
# lazy-created on first write; NO ROW = defaults (fail-safe = permissive,
# matching workspace_da_settings).
# ---------------------------------------------------------------------------
workspace_integration_settings = Table(
    "workspace_integration_settings",
    metadata,
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # Whether members may connect their own (personal) integrations here.
    # Even when ON, a provider must also declare personal support in its
    # catalog (owner_support) for a personal connect to be offered.
    Column(
        "allow_personal_integrations",
        Boolean,
        nullable=False,
        server_default=text("true"),
    ),
    # Whether a workflow whose derived scope is personal / per-member may run
    # in this workspace (PRD §13). Declared now to avoid a re-migration.
    Column(
        "allow_personal_scoped_workflows",
        Boolean,
        nullable=False,
        server_default=text("true"),
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)


# ---------------------------------------------------------------------------
# workspace_da_access_grant — per-member ACL projection (X-DA-ACL-1).
#
# One row per (workspace_id, user_id, resource_type, resource_id)
# tuple. Stores explicit grants and denies on DA catalog resources
# at any depth (schema / table / column). The absence of a row at a
# given level means "inherit from parent" — resolution walks the
# resource tree from leaf upward, applying the closest explicit
# row. Resolution rule lives in the service (not the schema)
# because it needs the catalog tree, but the storage shape is
# minimal and indexed for the two UI read paths:
#
#   1. "All grants for member B in workspace W" → drives the
#      member-summary view in workspace-settings/members.
#   2. "All grants on resource R in workspace W" → drives the
#      Access drawer when an admin clicks the chip on a catalog row.
#
# Tenant Owner / Tenant Admin / Workspace Admin bypass entirely via
# the JWT projection — they never write grant rows against
# themselves. M10 PII / Restricted hard-blocks layer above this
# unconditionally.
# ---------------------------------------------------------------------------

workspace_da_access_grant = Table(
    "workspace_da_access_grant",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "user_id",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    ),

    # Which level of the catalog tree this grant targets. The
    # ``resource_id`` column carries the catalog row's UUID matching
    # the level (da_catalog_schema.id / da_catalog_table.id /
    # da_catalog_column.id). We deliberately don't FK ``resource_id``
    # to the three catalog tables — that would require a polymorphic
    # FK shape (one column, three possible targets) which Postgres
    # can't express natively. The service is responsible for
    # validating resource_id belongs to a row of the matching type
    # in the caller's workspace before insert.
    Column(
        "resource_type",
        PgEnum(
            DAAccessResourceTypeEnum,
            name="da_access_resource_type",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    Column("resource_id", UUID(as_uuid=False), nullable=False),

    # Explicit allow or deny. Inherit-from-parent is the *absence* of
    # a row at this level — never stored.
    Column(
        "effect",
        PgEnum(
            DAAccessEffectEnum,
            name="da_access_effect",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),

    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    # One effect per member per resource. Without this the UI couldn't
    # decide what 'current state' means for a cell in the matrix.
    UniqueConstraint(
        "workspace_id",
        "user_id",
        "resource_type",
        "resource_id",
        name="ux_workspace_da_access_grant_member_resource",
    ),
    # Member-summary lookup ("what does Bob have access to?").
    Index(
        "ix_workspace_da_access_grant_workspace_user",
        "workspace_id",
        "user_id",
    ),
    # Resource-drawer lookup ("who has access to this column?").
    Index(
        "ix_workspace_da_access_grant_workspace_resource",
        "workspace_id",
        "resource_type",
        "resource_id",
    ),
)


# ---------------------------------------------------------------------------
# metric — Entity 5 (§4.8).
#
# Workspace-scoped business metric. Independent HITL lifecycle (admin
# accepts/rejects AI suggestions). Partial unique on (workspace_id, name)
# WHERE is_archived = false — archiving a metric frees its name for reuse.
# ---------------------------------------------------------------------------

metric = Table(
    "metric",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=True),
    Column("sql_expression", Text, nullable=False),
    Column("filters", Text, nullable=True),
    # List of table_name strings the metric applies to.
    Column("applicable_tables", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    # List of column_name strings — dimensions the metric can be grouped by.
    Column("valid_dimensions", JSONB, nullable=True),
    Column(
        "source",
        PgEnum(
            DAMetricSourceEnum,
            name="da_metric_source",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'admin_authored'"),
    ),
    Column(
        "accepted",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "created_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "updated_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("last_used_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "is_archived",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    # Partial unique — archived rows don't block reusing the name.
    Index(
        "ux_metric_workspace_name_active",
        "workspace_id",
        "name",
        unique=True,
        postgresql_where=text("is_archived = false"),
    ),
    Index("ix_metric_workspace", "workspace_id"),
)


# ---------------------------------------------------------------------------
# join_hint — Entity 6 (§4.8).
#
# Workspace-scoped join hint. Cascades when either side table is removed
# (the hint becomes meaningless).
# ---------------------------------------------------------------------------

join_hint = Table(
    "join_hint",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "left_table_id",
        UUID(as_uuid=False),
        ForeignKey("workspace_curation_da_table.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # JSONB list[str] — composite join keys supported (e.g. ["tenant_id", "user_id"]).
    Column("left_columns", JSONB, nullable=False),
    Column(
        "right_table_id",
        UUID(as_uuid=False),
        ForeignKey("workspace_curation_da_table.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("right_columns", JSONB, nullable=False),
    Column(
        "join_type",
        PgEnum(
            DAJoinTypeEnum,
            name="da_join_type",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'inner'"),
    ),
    Column("semantic_description", Text, nullable=True),
    Column(
        "source",
        PgEnum(
            DAJoinHintSourceEnum,
            name="da_join_hint_source",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'admin_authored'"),
    ),
    Column(
        "accepted",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "created_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "is_archived",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),

    Index("ix_join_hint_workspace", "workspace_id"),
    Index("ix_join_hint_left_table", "left_table_id"),
    Index("ix_join_hint_right_table", "right_table_id"),
)


# ---------------------------------------------------------------------------
# description_version — Entity 8 (§4.8). Append-only history.
#
# Soft-FK pattern: ``parent_id`` references one of four parent tables; the
# ``scope`` column discriminates. Postgres doesn't natively support
# discriminated FKs, so the parent FK is service-enforced (agent-platform
# writes never insert mismatched (scope, parent_id) pairs).
#
# No ``updated_at`` — a correction is a new version, not an in-place edit.
# Service-layer enforcement; DB-level immutability trigger deferred unless
# audit pressure later demands it (see AUDIT.md for the call).
# ---------------------------------------------------------------------------

description_version = Table(
    "description_version",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "scope",
        PgEnum(
            DADescriptionScopeEnum,
            name="da_description_scope",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    # Soft FK — see note above. parent_id references whichever table the
    # `scope` value points at: workspace_metadata_table /
    # workspace_metadata_column / metric / join_hint.
    Column("parent_id", UUID(as_uuid=False), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column(
        "source",
        PgEnum(
            DADescriptionSourceEnum,
            name="da_description_source",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    Column("content", Text, nullable=False),
    Column(
        "generated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    # SET NULL so a user erasure doesn't destroy the version row itself.
    Column(
        "generated_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    # For ai_generated / ai_suggested versions: DDL + comments + seed +
    # samples + stats used at generation time. Reproducible + eval-replayable.
    # May contain sample_values → PII-tagged.
    Column(
        "inputs_snapshot",
        JSONB,
        nullable=True,
        comment="pii:freetext",
    ),

    # version_number is auto-incremented per (scope, parent_id) — only one
    # row at each version. Service layer computes the next number on insert.
    Index(
        "ux_description_version_parent_version",
        "scope",
        "parent_id",
        "version_number",
        unique=True,
    ),
    # Latest-first read path: "give me the current description for this column".
    Index(
        "ix_description_version_parent_latest",
        "scope",
        "parent_id",
        text("version_number DESC"),
    ),
)


# ---------------------------------------------------------------------------
# Dashboards (NEU-1811 DA-P3.1). Workspace-scoped authored surfaces
# composed of widgets that pull from the curated DA catalog. Draft +
# Publish lifecycle. Each dashboard has a 1:1 build chat (kind=
# 'dashboard_build') and an optional set of link-tokens for external
# share. Multi-schema by design — a single dashboard can compose
# widgets across every schema the workspace has enabled.
#
# Design source: this session's DA-P3 lock + data-analytics.md
# D3 / D5 / D6 / D7 / D11 / D12.
# ---------------------------------------------------------------------------

dashboard = Table(
    "dashboard",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "tenant_id",
        UUID(as_uuid=False),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # URL-friendly identifier. Unique within a workspace; route is
    # /dashboards/<slug>. Service layer enforces format + auto-derives
    # from name on create.
    Column("slug", String(255), nullable=False),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=True),
    # New dashboards start as drafts (Library renders them in Drafts
    # section). Publish flips to ``published`` + sets published_at.
    Column(
        "status",
        PgEnum(
            DashboardStatusEnum,
            name="dashboard_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'draft'"),
    ),
    Column(
        "visibility",
        PgEnum(
            DashboardVisibilityEnum,
            name="dashboard_visibility",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'workspace_members'"),
    ),
    # Back-pointer to the build chat. 1:1. SET NULL because the chat
    # can be purged independently (compliance) — the dashboard widgets
    # are the source of truth, the chat is the build history.
    Column(
        "build_chat_id",
        UUID(as_uuid=False),
        ForeignKey("chat.id", ondelete="SET NULL"),
        nullable=True,
    ),
    # SET NULL on user deletion — keep the dashboard, lose attribution.
    Column(
        "owner_id",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "created_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    # Pinned to the top of the sidebar's dashboard list. Mirrors chat.pinned so
    # both rails sort by the same rule; a user preference about their workspace,
    # which is why it is a column and not localStorage.
    Column("pinned", Boolean, nullable=False, server_default=text("false")),
    Column("published_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    # Library URL routing — /dashboards/<slug> per workspace.
    UniqueConstraint(
        "workspace_id",
        "slug",
        name="ux_dashboard_workspace_slug",
    ),
    # Library section filter — Drafts vs Published per workspace.
    Index(
        "ix_dashboard_workspace_status",
        "workspace_id",
        "status",
    ),
    # Tenant-scoped lookups (e.g. cross-workspace admin views).
    Index("ix_dashboard_tenant", "tenant_id"),
)


dashboard_widget = Table(
    "dashboard_widget",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "dashboard_id",
        UUID(as_uuid=False),
        ForeignKey("dashboard.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # 12-col grid position (locked Q1 in the DA-P3 design discussion).
    # x ∈ [0, 12), w ∈ [1, 12]; y unbounded above; h ∈ [1, 12]. Service
    # layer validates ranges + non-overlap.
    Column("position_x", Integer, nullable=False, server_default=text("0")),
    Column("position_y", Integer, nullable=False, server_default=text("0")),
    Column("position_w", Integer, nullable=False, server_default=text("4")),
    Column("position_h", Integer, nullable=False, server_default=text("2")),
    Column(
        "widget_type",
        PgEnum(
            DashboardWidgetTypeEnum,
            name="dashboard_widget_type",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    Column("title", String(255), nullable=False),
    Column("description", Text, nullable=True),
    # data_binding: relational { connection_id, schema_name, sql, params? }
    #            or document   { connection_id, database, collection, pipeline }
    #   A widget re-executes its query on every load. Restricting that query to
    #   SQL made dashboards a relational-only surface: a chart over a Mongo
    #   collection could be produced in chat but never kept. Both forms are
    #   validated by DashboardWidgetDataBinding, which enforces exactly one.
    # viz_spec: { chart_type, x_axis, y_axis, series?, format?, ... }
    # grounding_metadata: { tables[], columns[], curator, last_validated_at }
    # All JSONB so we can partial-update specific keys without
    # rewriting the blob and for fast JSONB-path queries.
    Column("data_binding", JSONB, nullable=False),
    Column("viz_spec", JSONB, nullable=False),
    Column("grounding_metadata", JSONB, nullable=True),
    # The build-chat message that proposed this widget. SET NULL on
    # message purge (compliance) — the widget itself is the ground
    # truth; chat history is the audit trail.
    # Which chat chart this widget was promoted from (pin-to-dashboard).
    #   Not derivable from created_by_message_id: native da_chart artifacts are
    #   persisted before the assistant message is finalized, so
    #   chat_artifact.message_id is NULL by design — and a message can hold
    #   several charts, so a message id cannot say WHICH one this came from.
    #   SET NULL on delete, like created_by_message_id: the widget outlives its
    #   provenance because the query it runs is its own.
    Column(
        "source_artifact_id",
        UUID(as_uuid=False),
        ForeignKey("chat_artifact.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "created_by_message_id",
        UUID(as_uuid=False),
        ForeignKey("message.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    # Canonical render-time query — every dashboard load hits this.
    Index("ix_dashboard_widget_dashboard", "dashboard_id"),
    # Reverse lookup: "which dashboards hold this chat chart?" — asked by the
    # chat card on render, so it needs to be an index and not a scan. Partial,
    # since the column is NULL for every build-agent-proposed widget.
    Index(
        "ix_dashboard_widget_source_artifact",
        "source_artifact_id",
        postgresql_where=text("source_artifact_id IS NOT NULL"),
    ),
)


dashboard_link_token = Table(
    "dashboard_link_token",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "dashboard_id",
        UUID(as_uuid=False),
        ForeignKey("dashboard.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # SHA-256 of the URL-safe token, hex-encoded (64 chars). The
    # plaintext token materialises exactly once — in the response of
    # the mint endpoint. From there on the DB only ever sees the hash;
    # a DB read can confirm a presented token matches a stored row
    # but cannot reconstruct the token. Same pattern Stripe / GitHub
    # PATs use for API credential storage at rest.
    Column("token_hash", String(64), nullable=False),
    # First 8 chars of the URL-safe plaintext, kept in the clear for
    # human identification in the share dialog ("link · xK4f2nM9").
    # 8 chars of url-safe base64 ≈ 48 bits of identifier entropy —
    # plenty for distinguishing a curator's own links, and gives away
    # nothing usable about the full secret. Same idea as GitHub PAT
    # list views showing ``ghp_xxxxXXXX``.
    Column("token_short", String(12), nullable=False),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=True),
    Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
    # WHO revoked it. NULL = un-revoked, or system-initiated revoke
    # (future bg-job sweeper). SET NULL on user delete so the audit
    # fact (this link was revoked at T) outlives the actor.
    Column(
        "revoked_by_user_id",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "created_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    # Bumped on every successful anonymous access — feeds the share
    # dialog's "viewed N times" caption and the audit log.
    Column(
        "accessed_count",
        Integer,
        nullable=False,
        server_default=text("0"),
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),

    # Temporal invariants. Cheap CHECK constraints that turn a class
    # of service-bug ("we wrote an already-expired row") into a
    # DB-level constraint error — production-grade defense-in-depth.
    CheckConstraint(
        "expires_at IS NULL OR expires_at > created_at",
        name="ck_dashboard_link_token_expires_after_created",
    ),
    CheckConstraint(
        "revoked_at IS NULL OR revoked_at >= created_at",
        name="ck_dashboard_link_token_revoked_after_created",
    ),

    # Public viewer lookup — UNIQUE on the HASH. Hash collisions for
    # SHA-256 are cryptographically improbable, but UNIQUE makes the
    # invariant explicit at the schema level and the resolve path
    # depends on it (single-row read on hash match).
    Index(
        "ux_dashboard_link_token_token_hash",
        "token_hash",
        unique=True,
    ),
    # Active-link partial index. The query that powers the Library's
    # "Shared · N" pill JOIN is:
    #
    #     ... WHERE revoked_at IS NULL
    #             AND (expires_at IS NULL OR expires_at > now())
    #
    # Postgres won't accept ``now()`` (STABLE, not IMMUTABLE) inside
    # an index predicate, so the index filters on the immutable half
    # only (``revoked_at IS NULL``) and the query layer applies the
    # ``expires_at`` residual at scan time. Standard share-link
    # pattern — Stripe API keys + GitHub PATs index this way.
    # Replaces the v1 ``ix_dashboard_link_token_dashboard`` which
    # covered every row including revoked ones.
    Index(
        "ix_dashboard_link_token_active",
        "dashboard_id",
        postgresql_where=text("revoked_at IS NULL"),
    ),
)

# ---------------------------------------------------------------------------
# dashboard_build_run — one asynchronous build-agent turn.
#
# The build turn used to run inside the HTTP request: a dropped browser tab, a
# rolling deploy or a proxy idle-timeout lost the whole turn even though the
# agent had done the work. A run row makes the turn a first-class background
# job — the POST returns a run id immediately, the agent executes detached, and
# the client (re)attaches to an SSE stream keyed by that id. Mirrors the
# unified-chat ``runs`` table, kept separate because the lifecycle, payload
# (a widget-proposal envelope, not an answer) and retention differ.
#
# ``status`` reuses the existing ``run_status`` PgEnum rather than minting a
# parallel type — the state machine is the same (pending → running →
# completed | failed | cancelled).
# ---------------------------------------------------------------------------

dashboard_build_run = Table(
    "dashboard_build_run",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "tenant_id",
        UUID(as_uuid=False),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "dashboard_id",
        UUID(as_uuid=False),
        ForeignKey("dashboard.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # The build chat this turn belongs to. SET NULL because chat rows can be
    # compliance-purged independently of the run's audit trail.
    Column(
        "build_chat_id",
        UUID(as_uuid=False),
        ForeignKey("chat.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "user_id",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "status",
        PgEnum(
            RunStatus,
            name="run_status",
            values_callable=lambda enum: [e.value for e in enum],
            create_type=False,   # owned by the ``runs`` table
        ),
        nullable=False,
        server_default=text("'pending'"),
    ),
    Column("user_message", Text, nullable=False),
    # The finished envelope ({kind, narration, proposed_widgets, options,
    # message_id}) — what the SSE ``result`` frame carries. Persisted so a
    # client that reconnects after the stream ended still gets the outcome.
    Column("result_envelope", JSONB, nullable=True),
    Column("error", Text, nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    # "What's running / what ran last on this dashboard" — the editor's
    # reattach query on mount.
    Index(
        "ix_dashboard_build_run_dashboard_created",
        "dashboard_id",
        "created_at",
    ),
)


# ---------------------------------------------------------------------------
# dashboard_proposal_state — what became of each widget proposal.
#
# Applied-state used to be inferred by matching a proposal's
# (widget_type, connection_id, sql) against the widgets on the canvas. Delete
# the widget and the match disappears, so the build chat offered "Apply" again
# — which reads as "apply to redo". Widget deletes are hard deletes, so no
# canvas-derived signal can survive one; this row is the record.
#
# Keyed by (message_id, proposal_index): the assistant build-chat message that
# carried the proposal envelope, plus the proposal's position in it. That pair
# is exactly what the FE already uses as a card key.
# ---------------------------------------------------------------------------

dashboard_proposal_state = Table(
    "dashboard_proposal_state",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "dashboard_id",
        UUID(as_uuid=False),
        ForeignKey("dashboard.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # The assistant message carrying the proposals envelope. CASCADE: if the
    # message is purged the cards are gone from the chat too, so their state
    # has nothing left to describe.
    Column(
        "message_id",
        UUID(as_uuid=False),
        ForeignKey("message.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("proposal_index", Integer, nullable=False),
    Column(
        "state",
        PgEnum(
            DashboardProposalStateEnum,
            # NOT ``dashboard_proposal_state`` — Postgres keeps types and
            # tables in one namespace, and the table below claims that name.
            name="dashboard_proposal_state_kind",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    # The widget this proposal produced. SET NULL on widget delete so the row
    # never dangles; ``state`` is flipped to ``removed`` by the delete path,
    # which is what preserves the "was applied once" fact.
    Column(
        "widget_id",
        UUID(as_uuid=False),
        ForeignKey("dashboard_widget.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),

    # One state per proposal — the upsert target.
    UniqueConstraint(
        "message_id",
        "proposal_index",
        name="ux_dashboard_proposal_state_message_index",
    ),
    # The editor loads every proposal state for a dashboard in one read.
    Index("ix_dashboard_proposal_state_dashboard", "dashboard_id"),
    # Delete-widget flips state by widget id.
    Index("ix_dashboard_proposal_state_widget", "widget_id"),
)


# ---------------------------------------------------------------------------
# integration — unified credential record (WF-VS1).
#
# ONE row per credential, shared across all three pillars (ES via the
# 'ingest' capability, DA via 'query', WF via 'act'). The Vault secret
# lives behind ``vault_secret_id`` — the row NEVER carries the secret.
#
# Established once at the tenant level (owner_kind='tenant', the
# corporate connector that workspaces enable) or owned by an individual
# (owner_kind='user', the personal tier). The CHECK constraint enforces
# the per-owner_kind invariant so a row can't be ambiguous about who
# owns it. ``identity_kind`` (orthogonal) records who the destination
# SaaS sees. See product-feature-roadmap/workflow-execution §5a, §9.
# ---------------------------------------------------------------------------

integration = Table(
    "integration",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "tenant_id",
        UUID(as_uuid=False),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    ),

    # Ownership tier. tenant → shared via enablement; user → personal.
    Column(
        "owner_kind",
        PgEnum(
            IntegrationOwnerKindEnum,
            name="integration_owner_kind",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    # Set ONLY for owner_kind='user' (the personal owner). NULL for tenant.
    Column(
        "owner_user_id",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=True,
    ),
    # Set for owner_kind='user' (the workspace the personal integration is
    # attached to) AND owner_kind='workspace' (the workspace that owns it).
    # NULL for tenant integrations — they aren't tied to one workspace;
    # workspaces opt in via enablement.
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=True,
    ),

    Column("provider", String(64), nullable=False),
    Column("display_name", String(255), nullable=False),
    # Pointer into Vault. The credential itself never lives in this row.
    # NULLABLE so local-only sources (auth_kind='none', e.g. member
    # uploads a PDF) can be stored without a placeholder secret.
    # UC-ES-DB-1.A — was NOT NULL before the ES upload collapse.
    Column("vault_secret_id", String(512), nullable=True),

    # Who the destination SaaS sees when this credential is used.
    Column(
        "identity_kind",
        PgEnum(
            IntegrationIdentityKindEnum,
            name="integration_identity_kind",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    Column("identity_label", String(255), nullable=True),

    Column(
        "auth_kind",
        PgEnum(
            IntegrationAuthKindEnum,
            name="integration_auth_kind",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    # OAuth scopes actually granted (audit + capability derivation).
    Column("oauth_scopes_granted", ARRAY(Text), nullable=True),
    # e.g. Jira site URL — needed to build API calls for instance-scoped
    # providers.
    Column("instance_url", String(512), nullable=True),
    # Provider account identity (Slack team_id, Jira cloud_id, etc.).
    Column("external_account_id", String(255), nullable=True),
    Column("external_account_name", String(255), nullable=True),

    # The cross-pillar axis: which pillars may use this integration.
    # Subset of {'ingest','query','act'} (stored as text[] to stay open
    # to new capabilities without an enum migration).
    Column("capabilities", ARRAY(Text), nullable=False),

    Column(
        "status",
        PgEnum(
            IntegrationStatusEnum,
            name="integration_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'active'"),
    ),
    Column("last_verified_at", TIMESTAMP(timezone=True), nullable=True),
    # Provider-specific non-secret extras. App-level validation forbids
    # credential-shaped keys here.
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),

    Column(
        "created_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=False,
    ),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    # The owner_kind invariant — a row can't be ambiguous about who owns it.
    #   tenant    → owner_user_id NULL, workspace_id NULL (shared via enablement)
    #   user      → owner_user_id SET,  workspace_id SET  (personal, in that ws)
    #   workspace → owner_user_id NULL, workspace_id SET  (workspace owns it)
    CheckConstraint(
        "(owner_kind = 'tenant' AND owner_user_id IS NULL AND workspace_id IS NULL) "
        "OR (owner_kind = 'user' AND owner_user_id IS NOT NULL AND workspace_id IS NOT NULL) "
        "OR (owner_kind = 'workspace' AND owner_user_id IS NULL AND workspace_id IS NOT NULL)",
        name="ck_integration_owner_kind_invariant",
    ),
    # A tenant can't connect the same provider account twice.
    UniqueConstraint(
        "tenant_id",
        "provider",
        "external_account_id",
        name="ux_integration_tenant_provider_account",
    ),
    # "All integrations for tenant T of provider P" — the create/list path.
    Index("ix_integration_tenant_provider", "tenant_id", "provider"),
    # "My personal integrations" — the personal-tier list path.
    Index("ix_integration_owner_user", "owner_user_id"),
)


# ---------------------------------------------------------------------------
# integration_workspace_enablement — per-workspace opt-in (WF-VS1).
#
# A tenant integration is unusable by a workspace until an enablement
# row exists. Enablement scopes capabilities DOWN (a subset of the
# integration's capabilities — enforced in the service). Carries a
# per-workspace display-name override and independent lifecycle so one
# workspace can disable without affecting others.
# ---------------------------------------------------------------------------

integration_workspace_enablement = Table(
    "integration_workspace_enablement",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "integration_id",
        UUID(as_uuid=False),
        ForeignKey("integration.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # Subset of integration.capabilities granted to this workspace.
    Column("capabilities_enabled", ARRAY(Text), nullable=False),
    # Audience (NC-637) — who in this workspace may use the placed capabilities.
    #   'all_members'      every member of the workspace (an explicit deny grant
    #                      still excludes one)
    #   'selected_members' only members holding an explicit allow grant
    # Placement admits the workspace; this narrows it. Text, not a PgEnum, so a
    # third mode never needs a type migration — the same call
    # integration_member_grant.capability already makes.
    Column(
        "member_access",
        String(32),
        nullable=False,
        server_default=text("'all_members'"),
    ),
    Column("display_name_override", String(255), nullable=True),
    Column(
        "status",
        PgEnum(
            IntegrationEnablementStatusEnum,
            name="integration_enablement_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'active'"),
    ),
    Column(
        "enabled_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=False,
    ),
    Column("enabled_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    # A workspace enables a given tenant integration at most once.
    UniqueConstraint(
        "integration_id",
        "workspace_id",
        name="ux_integration_enablement_integration_workspace",
    ),
    # "What's enabled in workspace W" — the workspace integrations page.
    Index("ix_integration_enablement_workspace", "workspace_id"),
)


# ---------------------------------------------------------------------------
# integration_member_grant — per-member ACL (WF-VS1).
#
# Same cardinality/shape as workspace_da_access_grant: a flat
# per-(member, integration, capability) grid with deny-wins-anywhere
# resolution applied in the service. Default for a member is no access
# (no row); admins bypass via the JWT projection. ``capability`` is
# stored as text (includes the '*' wildcard) to stay open as
# capabilities grow.
# ---------------------------------------------------------------------------

integration_member_grant = Table(
    "integration_member_grant",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "user_id",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "integration_id",
        UUID(as_uuid=False),
        ForeignKey("integration.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # 'ingest' | 'query' | 'act' | '*' (wildcard = all capabilities).
    Column("capability", String(32), nullable=False),
    Column(
        "effect",
        PgEnum(
            IntegrationGrantEffectEnum,
            name="integration_grant_effect",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    Column(
        "created_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=False,
    ),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    # One effect per member per integration per capability.
    UniqueConstraint(
        "workspace_id",
        "user_id",
        "integration_id",
        "capability",
        name="ux_integration_member_grant_member_integration_cap",
    ),
    # "All grants for member B in workspace W" — member-summary view.
    Index("ix_integration_member_grant_workspace_user", "workspace_id", "user_id"),
    # "Who can use integration I" — the integration members drawer.
    Index("ix_integration_member_grant_integration", "integration_id"),
)


# ---------------------------------------------------------------------------
# integration_sync_job — one record-source sync run (RECORD-SYNC-TEMPORAL-1).
#
# Top-level row for an ES-Ingestion RecordSourceSyncWorkflow execution.
# The workflow heartbeats indexed_count / error_count / pages_completed.
# Per-doc progress lives on the ``files`` row (processing_status), same
# shape as file-source — so Indexed Content polls files for line-items
# and this table for run-level rollup ("synced 1234 issues across 25
# pages, 3 errors, completed 2m ago").
# ---------------------------------------------------------------------------

integration_sync_job = Table(
    "integration_sync_job",
    metadata,

    Column(
        "id",
        UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "tenant_id",
        UUID(as_uuid=False),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "integration_id",
        UUID(as_uuid=False),
        ForeignKey("integration.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # Per-provider unit id (Jira project key, Confluence space key, ...).
    # Opaque here; the per-provider connector primitive interprets it.
    Column("container_id", String(255), nullable=False),
    Column(
        "status",
        PgEnum(
            IntegrationSyncJobStatusEnum,
            name="integration_sync_job_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'pending'"),
    ),
    # Temporal handles. workflow_id is the deterministic key
    # (``sync:{job_id}`` — same shape as ``file:{file_id}``);
    # run_id is Temporal-assigned per attempt.
    Column("temporal_workflow_id", String(255), nullable=True),
    Column("temporal_run_id", String(255), nullable=True),
    Column("indexed_count", Integer, nullable=False, server_default=text("0")),
    Column("error_count", Integer, nullable=False, server_default=text("0")),
    Column("pages_completed", Integer, nullable=False, server_default=text("0")),
    Column(
        "started_by",
        UUID(as_uuid=False),
        ForeignKey("user.id"),
        nullable=False,
    ),
    Column("started_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("last_heartbeat_at", TIMESTAMP(timezone=True), nullable=True),
    Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
    Column("error_detail", JSONB, nullable=True),

    # "what's running right now?" — the Indexed Content polling query.
    Index("ix_integration_sync_job_workspace_status", "workspace_id", "status"),
    # "last sync for (integration, container)" — Content Sources card stamp.
    Index(
        "ix_integration_sync_job_integration_container_started",
        "integration_id",
        "container_id",
        text("started_at DESC"),
    ),
)


# ---------------------------------------------------------------------------
# integration_da_config — DA capability's per-connection config (DA-U1).
#
# The Data Analytics unification sidecar: DA warehouse connections live on the
# unified `integration` table like every other connector, but the DA-specific
# governance fact — the tenant schema allowlist — doesn't belong on the generic
# row. It lives here, 1:1 with the integration (integration_id IS the PK).
# Replaces da_connection.allowed_schemas; same NULL=unrestricted semantics.
# Mirrors the shape a future integration_es_config will take for ingest.
# ---------------------------------------------------------------------------

integration_da_config = Table(
    "integration_da_config",
    metadata,

    Column(
        "integration_id",
        UUID(as_uuid=False),
        ForeignKey("integration.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # Tenant-level schema allowlist (was da_connection.allowed_schemas):
    #   NULL      → unrestricted; every warehouse schema is visible/queryable.
    #   list[str] → allowlist; only these schemas surface + run via execute_query.
    Column("allowed_schemas", JSONB, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
)


# ---------------------------------------------------------------------------
# workflow — workspace-scoped workflow definitions (WF-VS2).
#
# The Workflow Execution pillar's definition store: one row per workflow the
# low-code builder produces. ``graph`` (JSONB) holds the node/edge definition
# the GenericGraphWorkflow interprets; Temporal owns *execution* state (event
# histories), this table owns the *definition*. created_by is metadata, not
# ownership — a workflow is workspace-owned and outlives its author, so the FK
# is SET NULL + nullable (unlike integration.created_by, which mismatches
# nullability and ondelete; tracked as TD-WF-INTEGRATION-CREATED-BY).
# ---------------------------------------------------------------------------

workflow = Table(
    "workflow",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column(
        "tenant_id",
        UUID(as_uuid=False),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "workspace_id",
        UUID(as_uuid=False),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    ),

    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=True),

    # The node/edge definition the GenericGraphWorkflow interprets.
    Column("graph", JSONB, nullable=False, server_default=text("'{}'::jsonb")),

    Column(
        "status",
        PgEnum(
            WorkflowStatusEnum,
            name="workflow_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'draft'"),
    ),

    # The revision chat discovery and triggers resolve. NULL until first publish.
    # SET NULL rather than CASCADE: losing a revision must not delete the workflow.
    Column(
        "published_revision_id",
        UUID(as_uuid=False),
        ForeignKey("workflow_revision.id", ondelete="SET NULL"),
        nullable=True,
    ),

    Column(
        "created_by",
        UUID(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    # "Workflows in workspace W of tenant T" — the builder list path.
    Index("ix_workflow_tenant_workspace", "tenant_id", "workspace_id"),
)


# ---------------------------------------------------------------------------
# workflow_revision — an immutable published revision (ITOps merge §5).
#
# Publication freezes the draft's graph and its input contract here and points
# workflow.published_revision_id at the row; editing the draft never touches a
# revision. Runs record which revision they used, so history stays readable
# after a republish.
# ---------------------------------------------------------------------------

workflow_revision = Table(
    "workflow_revision",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("workflow_id", UUID(as_uuid=False), ForeignKey("workflow.id", ondelete="CASCADE"), nullable=False),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("revision_number", Integer, nullable=False),
    Column("graph", JSONB, nullable=False),

    # The published input contract: which values are fixed and which the
    # caller supplies, with defaults. S2's configurable targets and parameters.
    Column("input_schema", JSONB, nullable=False, server_default=text("'[]'::jsonb")),

    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    UniqueConstraint("workflow_id", "revision_number", name="uq_workflow_revision_number"),
    Index("ix_workflow_revision_workflow", "workflow_id"),
)


# ---------------------------------------------------------------------------
# Workflow Execution pillar (WF-M1) — the run record.
#
# A workflow becomes runnable + auditable here. ``workflow_run`` is one row per
# execution (who triggered, when, total duration, outcome); ``workflow_run_step``
# is one row per node per execution (its input, output, status, attempts, and
# time taken). Full node payloads live in ``workflow_run_step`` — the record of
# truth, redactable per pii_fields — and audit_log only references them.
# ---------------------------------------------------------------------------

workflow_run = Table(
    "workflow_run",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),

    # Denormalised scope (mirrors workflow) so tenant/workspace audit roll-ups
    # don't need a join. Both cascade with their parent.
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    # Nullable: a one-off run (spec S1) carries no library workflow behind it,
    # only its own graph_snapshot below.
    Column("workflow_id", UUID(as_uuid=False), ForeignKey("workflow.id", ondelete="CASCADE"), nullable=True),

    # workflow_version_id stays a bare UUID until M6 adds workflow_version.
    Column("workflow_version_id", UUID(as_uuid=False), nullable=True),
    # trigger_id now references workflow_trigger (M3a.2). SET NULL — deleting a
    # trigger keeps the run history, just unlinks it.
    Column(
        "trigger_id",
        UUID(as_uuid=False),
        ForeignKey("workflow_trigger.id", ondelete="SET NULL"),
        nullable=True,
    ),

    Column(
        "status",
        PgEnum(
            WorkflowRunStatusEnum,
            name="workflow_run_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'queued'"),
    ),

    # Who triggered THIS run. The actor is absent for cron / anonymous webhook
    # (SET NULL); the audit principal is always known — author for cron, actor
    # otherwise — and is RESTRICT, never nulled, so the audit chain holds.
    Column("actor_user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column(
        "actor_kind",
        PgEnum(
            WorkflowActorKindEnum,
            name="workflow_actor_kind",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),
    Column("audit_principal_user_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),

    Column("temporal_run_id", Text, nullable=True),
    Column("trigger_payload", JSONB, nullable=True),
    Column("error_message", Text, nullable=True),

    # The frozen graph this run actually executed. Required for a one-off run
    # (no library workflow behind it) and kept for every run so history survives
    # a draft edit or a republish. S1.
    Column("graph_snapshot", JSONB, nullable=True),

    # created = when triggered; started = when execution began; finished = end.
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("finished_at", TIMESTAMP(timezone=True), nullable=True),

    # A run must have a graph to execute: its library workflow or its own snapshot.
    CheckConstraint("workflow_id IS NOT NULL OR graph_snapshot IS NOT NULL", name="ck_workflow_run_has_graph"),

    # Run-history list path: runs of a workflow, newest first.
    Index("ix_workflow_run_workflow_created", "workflow_id", "created_at"),
    # Tenant/workspace governance roll-up.
    Index("ix_workflow_run_tenant_workspace", "tenant_id", "workspace_id"),
)


workflow_run_step = Table(
    "workflow_run_step",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("run_id", UUID(as_uuid=False), ForeignKey("workflow_run.id", ondelete="CASCADE"), nullable=False),

    # Node identity within the run's graph.
    Column("step_id", Text, nullable=False),
    Column("node_kind", Text, nullable=False),

    Column(
        "status",
        PgEnum(
            WorkflowRunStepStatusEnum,
            name="workflow_run_step_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'pending'"),
    ),

    # Full node input/output — the record of truth (redacted per pii_fields in M8).
    Column("input_json", JSONB, nullable=True),
    Column("output_json", JSONB, nullable=True),

    # Temporal retry count for this node.
    Column("attempts", Integer, nullable=False, server_default=text("0")),

    # Which pii_fields redaction flags were applied (filled in M8).
    Column("pii_classification", ARRAY(Text), nullable=True),
    Column("error_message", Text, nullable=True),

    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("finished_at", TIMESTAMP(timezone=True), nullable=True),

    # Steps of a run — the per-run inspector path.
    Index("ix_workflow_run_step_run", "run_id"),
)


# ---------------------------------------------------------------------------
# Workflow Execution pillar (WF-M3a.2) — triggers.
#
# A stored trigger is how a workflow fires WITHOUT a manual Run click. A webhook
# trigger carries a unique ``token`` whose public URL (POST /triggers/{token})
# starts a run with the request body as the trigger node's payload; cron/event
# triggers carry their settings in ``config``. ``node_id`` binds the trigger to
# the trigger node in the workflow's graph.
# ---------------------------------------------------------------------------

workflow_trigger = Table(
    "workflow_trigger",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),

    # Denormalised scope (mirrors workflow) — cascades with its parents.
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("workflow_id", UUID(as_uuid=False), ForeignKey("workflow.id", ondelete="CASCADE"), nullable=False),

    # The trigger node in the graph this binds to.
    Column("node_id", Text, nullable=False),

    Column(
        "kind",
        PgEnum(
            WorkflowTriggerKindEnum,
            name="workflow_trigger_kind",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
    ),

    # Public webhook token (unguessable) — null for cron/event. Unique so the
    # public fire path resolves the workflow in one indexed lookup.
    #
    # DEPRECATED at-rest (D-2): this is a bearer capability — a DB dump grants
    # the ability to fire any workflow via POST /triggers/{token}. Kept for now
    # so the gateway/workflow services that still write/read `token` don't break;
    # the hardened token_hash/token_short path below is what they must migrate to.
    Column("token", Text, nullable=True),
    # Hash-at-rest shape mirroring share_link / dashboard_link_token: store
    # SHA-256(plaintext) here and resolve the public fire path by hashing the
    # presented token (uq_workflow_trigger_token_hash). Nullable during the
    # additive rollout; the plaintext should surface only in the mint response.
    Column("token_hash", String(64), nullable=True),
    # First chars of the plaintext — a non-secret handle for the builder UI.
    Column("token_short", String(12), nullable=True),

    # Kind-specific settings (cron expression, webhook auth mode, …).
    Column("config", JSONB, nullable=False, server_default=text("'{}'::jsonb")),

    Column(
        "status",
        PgEnum(
            WorkflowTriggerStatusEnum,
            name="workflow_trigger_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'active'"),
    ),

    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),

    # Triggers of a workflow — the builder + management list path.
    Index("ix_workflow_trigger_workflow", "workflow_id"),
    # O(1) public webhook resolution; partial so multiple token-less (cron) rows
    # don't collide on NULL.
    Index(
        "uq_workflow_trigger_token",
        "token",
        unique=True,
        postgresql_where=text("token IS NOT NULL"),
    ),
    # Hash-at-rest resolve path (D-2): O(1) public webhook resolution by
    # SHA-256(token). Partial + unique so token-less (cron) rows and pre-rollout
    # NULLs don't collide while non-null hashes stay unique.
    Index(
        "uq_workflow_trigger_token_hash",
        "token_hash",
        unique=True,
        postgresql_where=text("token_hash IS NOT NULL"),
    ),
)


# ---------------------------------------------------------------------------
# execution_proposal — an agent-proposed execution awaiting a human decision
# (ITOps merge S4, §4.1).
#
# The proposal is the unit of approval: it freezes the exact graph, the resolved
# inputs and the targets, and the decision binds to their digest. A changed
# procedure or target is a NEW proposal, never a re-decision of this one.
# Credentials never land here; connector binding IDs do.
# ---------------------------------------------------------------------------

execution_proposal = Table(
    "execution_proposal",
    metadata,

    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),

    # NULL for a one-off the agent composed; set when it came from a revision.
    Column("workflow_id", UUID(as_uuid=False), ForeignKey("workflow.id", ondelete="SET NULL"), nullable=True),
    Column("revision_id", UUID(as_uuid=False), ForeignKey("workflow_revision.id", ondelete="SET NULL"), nullable=True),

    # The conversation that proposed it, so chat and the inbox show one item.
    Column("chat_id", UUID(as_uuid=False), ForeignKey("chat.id", ondelete="SET NULL"), nullable=True),

    Column("graph", JSONB, nullable=False),
    Column("inputs", JSONB, nullable=False, server_default=text("'{}'::jsonb")),

    # Human-readable preview of every side-effecting branch, for the card.
    Column("preview", JSONB, nullable=False, server_default=text("'{}'::jsonb")),

    # sha256 over the canonical graph + inputs. The decision binds to this.
    Column("digest", Text, nullable=False),

    Column(
        "status",
        PgEnum(
            ExecutionProposalStatusEnum,
            name="execution_proposal_status",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        server_default=text("'pending'"),
    ),

    Column("requested_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("decided_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("decided_at", TIMESTAMP(timezone=True), nullable=True),

    # The run the approval started, once one exists. NULL while pending.
    Column("run_id", UUID(as_uuid=False), ForeignKey("workflow_run.id", ondelete="SET NULL"), nullable=True),

    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),

    # The approval inbox path: pending proposals in this workspace.
    Index("ix_execution_proposal_pending", "workspace_id", "status"),
    # One live proposal per procedure: the same graph and inputs in a workspace
    # attach to the open card instead of adding a second one (plan §16 dedup).
    Index(
        "uq_execution_proposal_open_digest",
        "workspace_id",
        "digest",
        unique=True,
        postgresql_where=text("status IN ('pending', 'approved')"),
    ),
)


# ===========================================================================
# Agent Studio (plans/AGENT-STUDIO-PLAN.md) — Agents, Teams, Runs.
#
# An Agent is a reusable specialist definition (charter, allowed tools, input
# and output schema, limits). A Team is the deployable unit: an orchestrator
# config plus a roster of pinned AgentVersions. A Run executes one TeamVersion
# on Temporal and dispatches AgentTasks; every AgentTask returns a structured
# Envelope. All runs share a per-run MinIO workspace, never transcripts.
#
# Statuses are String + CHECK (the user_memory rationale): every one of these
# sets is expected to grow and a CHECK extends in one line where a PgEnum
# ADD VALUE cannot be rolled back.
#
# The whole draft config lives in ``config`` JSONB. Only the fields the
# database must index, join or constrain are promoted to columns; the shape of
# ``config`` is owned by neutrino_database.models.studio_schemas.
# ===========================================================================

STUDIO_RUN_STATUSES = (
    "planning", "dispatching", "waiting_approval", "paused", "finishing",
    "completed", "failed", "cancelled",
)
STUDIO_TASK_STATUSES = (
    "pending", "running", "waiting_approval", "completed", "error",
    "budget_exhausted", "stalled", "schema_invalid", "cancelled", "approval_rejected",
)
STUDIO_TRIGGER_KINDS = ("chat", "studio", "api", "schedule", "event", "test")
STUDIO_APPROVAL_OUTCOMES = ("allowed_once", "rejected", "cancelled", "unavailable")


def _in(col: str, values) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


studio_agent = Table(
    "studio_agent",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("description", Text, nullable=True),
    # Draft config: charter, model, allowed_tools, input_schema, output_schema,
    # limits, deny_list, memory_enabled, code_exec_enabled. Shape: AgentConfig.
    Column("config", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    # Platform template library (decision 16): a template is an agent owned by
    # the platform; cloning copies config into the customer's workspace.
    Column("is_template", Boolean, nullable=False, server_default=text("false")),
    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    CheckConstraint("length(name) > 0", name="ck_studio_agent_name_not_blank"),
    Index("ix_studio_agent_workspace", "tenant_id", "workspace_id", postgresql_where=text("deleted_at IS NULL")),
    Index("ix_studio_agent_name", "workspace_id", "name", unique=True, postgresql_where=text("deleted_at IS NULL")),
)


studio_agent_version = Table(
    "studio_agent_version",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("agent_id", UUID(as_uuid=False), ForeignKey("studio_agent.id", ondelete="CASCADE"), nullable=False),
    Column("version", Integer, nullable=False),
    # Immutable snapshot of studio_agent.config at publish time.
    Column("config", JSONB, nullable=False),
    # passed — every saved test case passed; overridden — published anyway,
    # override_reason says why (decision 15). Recorded, never silent.
    Column("test_gate_status", String(16), nullable=False),
    Column("override_reason", Text, nullable=True),
    Column("published_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("published_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("agent_id", "version", name="uq_studio_agent_version"),
    CheckConstraint("version >= 1", name="ck_studio_agent_version_positive"),
    CheckConstraint(_in("test_gate_status", ("passed", "overridden")), name="ck_studio_agent_version_gate"),
    CheckConstraint(
        "test_gate_status <> 'overridden' OR override_reason IS NOT NULL",
        name="ck_studio_agent_version_override_reason",
    ),
)


studio_team = Table(
    "studio_team",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("description", Text, nullable=True),
    # Draft config: orchestrator {model, limits}, guardrails, roster
    # [{agent_id, agent_version_id, alias}], input_schema, output_schema,
    # runs_as, approver_ids, notification_targets, approval_policy,
    # memory_enabled, promoted_outputs. Shape: TeamConfig.
    Column("config", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    # Promoted to a column because the executor, the redaction pipeline and the
    # promotion path all branch on it without wanting to parse config.
    Column("sensitive", Boolean, nullable=False, server_default=text("false")),
    # Workspaces whose members may run the published team (decision 16).
    Column("published_to", ARRAY(UUID(as_uuid=False)), nullable=False, server_default=text("'{}'::uuid[]")),
    Column("is_template", Boolean, nullable=False, server_default=text("false")),
    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    CheckConstraint("length(name) > 0", name="ck_studio_team_name_not_blank"),
    Index("ix_studio_team_workspace", "tenant_id", "workspace_id", postgresql_where=text("deleted_at IS NULL")),
    Index("ix_studio_team_name", "workspace_id", "name", unique=True, postgresql_where=text("deleted_at IS NULL")),
)


studio_team_version = Table(
    "studio_team_version",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", UUID(as_uuid=False), ForeignKey("studio_team.id", ondelete="CASCADE"), nullable=False),
    Column("version", Integer, nullable=False),
    Column("config", JSONB, nullable=False),
    # [{alias, agent_id, agent_version_id}] — the exact agent snapshots this
    # team version runs. Runs pin this, so replay is exact (decision 25).
    Column("roster_pins", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("test_gate_status", String(16), nullable=False),
    Column("override_reason", Text, nullable=True),
    Column("published_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("published_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("team_id", "version", name="uq_studio_team_version"),
    CheckConstraint("version >= 1", name="ck_studio_team_version_positive"),
    CheckConstraint(_in("test_gate_status", ("passed", "overridden")), name="ck_studio_team_version_gate"),
    CheckConstraint(
        "test_gate_status <> 'overridden' OR override_reason IS NOT NULL",
        name="ck_studio_team_version_override_reason",
    ),
)


studio_api_key = Table(
    "studio_api_key",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(200), nullable=False),
    # Teams this key may start. Empty means none — a key is never wildcard.
    Column("team_ids", ARRAY(UUID(as_uuid=False)), nullable=False, server_default=text("'{}'::uuid[]")),
    # sha256 of the plaintext; the plaintext is shown once at creation and
    # never stored. ``prefix`` (nsk_ + 8 chars) is what the UI lists.
    Column("key_hash", String(64), nullable=False, unique=True),
    Column("prefix", String(16), nullable=False),
    Column("rate_limit_per_min", Integer, nullable=False, server_default=text("60")),
    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
    Column("last_used_at", TIMESTAMP(timezone=True), nullable=True),
    CheckConstraint("rate_limit_per_min > 0", name="ck_studio_api_key_rate_positive"),
    Index("ix_studio_api_key_workspace", "tenant_id", "workspace_id", postgresql_where=text("revoked_at IS NULL")),
)


studio_event_trigger = Table(
    "studio_event_trigger",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", UUID(as_uuid=False), ForeignKey("studio_team.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(200), nullable=False),
    # poll — a Temporal workflow calls a connector list action on an interval;
    # webhook — the gateway receiver signals the same workflow (decision 26).
    Column("source", String(8), nullable=False),
    # The connector (integration) the poll reads from; NULL for a generic webhook.
    Column("integration_id", UUID(as_uuid=False), ForeignKey("integration.id", ondelete="SET NULL"), nullable=True),
    # {action, interval_s, filter, item_key_field, input_mapping,
    #  webhook_provider, secret_hash}. Never a plaintext secret.
    Column("config", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("enabled", Boolean, nullable=False, server_default=text("true")),
    Column("temporal_workflow_id", String(255), nullable=True),
    # {status, last_poll_at, last_error, consecutive_failures} for the health chip.
    Column("health", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    CheckConstraint(_in("source", ("poll", "webhook")), name="ck_studio_event_trigger_source"),
    Index("ix_studio_event_trigger_team", "team_id"),
)


studio_schedule = Table(
    "studio_schedule",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", UUID(as_uuid=False), ForeignKey("studio_team.id", ondelete="CASCADE"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("cron", String(100), nullable=False),
    Column("timezone", String(64), nullable=False, server_default=text("'UTC'")),
    Column("input", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("temporal_schedule_id", String(255), nullable=True),
    Column("enabled", Boolean, nullable=False, server_default=text("true")),
    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Index("ix_studio_schedule_team", "team_id"),
)


studio_run = Table(
    "studio_run",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", UUID(as_uuid=False), ForeignKey("studio_team.id", ondelete="CASCADE"), nullable=False),
    # NULL only for a test run of an unpublished draft (the draft config is
    # frozen into ``team_config`` instead).
    Column("team_version_id", UUID(as_uuid=False), ForeignKey("studio_team_version.id", ondelete="SET NULL"), nullable=True),
    # The exact team config this run executed, whether from a version or a
    # draft test run. Replay reads this, never the live draft.
    Column("team_config", JSONB, nullable=False),
    Column("status", String(32), nullable=False, server_default=text("'planning'")),
    Column("is_test", Boolean, nullable=False, server_default=text("false")),
    # Trigger attribution (decision 4 / 27). One of the four ids is set.
    Column("trigger_kind", String(16), nullable=False),
    Column("trigger_actor_id", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("api_key_id", UUID(as_uuid=False), ForeignKey("studio_api_key.id", ondelete="SET NULL"), nullable=True),
    # No FK: studio_trigger_event points back here (run_id) and one side of
    # the cycle has to be a plain column. The event row is the one that owns
    # the relationship; this is a convenience pointer for the console.
    Column("trigger_event_id", UUID(as_uuid=False), nullable=True),
    Column("input", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("output", JSONB, nullable=True),
    # The orchestrator's current task DAG: [{alias, agent_version_id, brief,
    # depends_on, task_id}]. Rewritten on every re-plan; history is in run_events.
    Column("plan", JSONB, nullable=True),
    Column("workspace_prefix", Text, nullable=False),
    # Fork lineage (decision 32). SET NULL so a fork survives its parent's purge.
    Column("parent_run_id", UUID(as_uuid=False), ForeignKey("studio_run.id", ondelete="SET NULL"), nullable=True),
    Column("fork_point_task_id", UUID(as_uuid=False), nullable=True),
    # {tokens_in, tokens_out, tool_calls, wall_s, usd, sandbox_s} used vs cap.
    Column("budgets", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("error", Text, nullable=True),
    Column("temporal_workflow_id", String(255), nullable=True, unique=True),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("ended_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    CheckConstraint(_in("status", STUDIO_RUN_STATUSES), name="ck_studio_run_status"),
    CheckConstraint(_in("trigger_kind", STUDIO_TRIGGER_KINDS), name="ck_studio_run_trigger_kind"),
    CheckConstraint("parent_run_id IS NULL OR parent_run_id <> id", name="ck_studio_run_no_self_parent"),
    Index("ix_studio_run_team_created", "tenant_id", "team_id", "created_at"),
    Index("ix_studio_run_status", "tenant_id", "status"),
    Index("ix_studio_run_parent", "parent_run_id"),
)


studio_agent_task = Table(
    "studio_agent_task",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", UUID(as_uuid=False), ForeignKey("studio_run.id", ondelete="CASCADE"), nullable=False),
    Column("agent_id", UUID(as_uuid=False), ForeignKey("studio_agent.id", ondelete="SET NULL"), nullable=True),
    Column("agent_version_id", UUID(as_uuid=False), ForeignKey("studio_agent_version.id", ondelete="SET NULL"), nullable=True),
    # Frozen agent config for this task (replay-exact even if the version row goes).
    Column("agent_config", JSONB, nullable=False),
    Column("alias", String(100), nullable=False),
    Column("attempt", Integer, nullable=False, server_default=text("1")),
    # Brief: {objective, context, input, workspace_paths, constraints}.
    Column("brief", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("status", String(32), nullable=False, server_default=text("'pending'")),
    # Envelope fields (decision 31). Non-completed never reads as success.
    Column("exit_reason", Text, nullable=True),
    Column("output", JSONB, nullable=True),
    Column("raw_text", Text, nullable=True),
    Column("schema_errors", JSONB, nullable=True),
    # <= 4 KB, scrubbed of tool inputs and credentials before it is written.
    Column("diagnostic", Text, nullable=True),
    Column("files_written", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("depends_on", ARRAY(UUID(as_uuid=False)), nullable=False, server_default=text("'{}'::uuid[]")),
    Column("budgets", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("sandbox_id", String(255), nullable=True),
    Column("temporal_workflow_id", String(255), nullable=True),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("ended_at", TIMESTAMP(timezone=True), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    CheckConstraint(_in("status", STUDIO_TASK_STATUSES), name="ck_studio_agent_task_status"),
    CheckConstraint("attempt >= 1", name="ck_studio_agent_task_attempt_positive"),
    CheckConstraint("diagnostic IS NULL OR length(diagnostic) <= 4096", name="ck_studio_agent_task_diagnostic_cap"),
    Index("ix_studio_agent_task_run_status", "run_id", "status"),
)


studio_approval = Table(
    "studio_approval",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", UUID(as_uuid=False), ForeignKey("studio_run.id", ondelete="CASCADE"), nullable=False),
    # NULL for a mandatory gate the orchestrator raised between tasks.
    Column("task_id", UUID(as_uuid=False), ForeignKey("studio_agent_task.id", ondelete="CASCADE"), nullable=True),
    # {integration_id, action, payload, effect, summary} — the exact call that
    # will be made. ``payload_hash`` is re-checked at execution (decision 29):
    # a changed payload is refused, not sent.
    Column("action", JSONB, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("approver_ids", ARRAY(UUID(as_uuid=False)), nullable=False, server_default=text("'{}'::uuid[]")),
    # NULL while pending. Closed, fail-closed set (decision 8).
    Column("outcome", String(16), nullable=True),
    Column("decided_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("decided_at", TIMESTAMP(timezone=True), nullable=True),
    Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
    # sha256 of the single-use token in the signed email link.
    Column("token_hash", String(64), nullable=True, unique=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    CheckConstraint(
        f"outcome IS NULL OR {_in('outcome', STUDIO_APPROVAL_OUTCOMES)}",
        name="ck_studio_approval_outcome",
    ),
    CheckConstraint(
        "outcome IS NULL OR outcome = 'unavailable' OR decided_at IS NOT NULL",
        name="ck_studio_approval_decided_at",
    ),
    Index("ix_studio_approval_pending", "tenant_id", "created_at", postgresql_where=text("outcome IS NULL")),
    Index("ix_studio_approval_run", "run_id"),
)


studio_trigger_event = Table(
    "studio_trigger_event",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", UUID(as_uuid=False), ForeignKey("studio_team.id", ondelete="CASCADE"), nullable=False),
    Column("trigger_id", UUID(as_uuid=False), ForeignKey("studio_event_trigger.id", ondelete="CASCADE"), nullable=False),
    Column("source", String(8), nullable=False),
    # Stable per item (drive item id, message id, issue key). The unique index
    # below is the dedupe: a second sighting is a no-op insert.
    Column("item_key", Text, nullable=False),
    Column("payload", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("received_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("run_id", UUID(as_uuid=False), ForeignKey("studio_run.id", ondelete="SET NULL"), nullable=True),
    Column("error", Text, nullable=True),
    CheckConstraint(_in("source", ("poll", "webhook")), name="ck_studio_trigger_event_source"),
    UniqueConstraint("team_id", "item_key", name="uq_studio_trigger_event_item"),
    Index("ix_studio_trigger_event_trigger", "trigger_id", "received_at"),
)


studio_test_case = Table(
    "studio_test_case",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    # Polymorphic subject: an agent or a team. No FK, the service resolves it;
    # deletion of the subject soft-deletes and the index keeps lookups cheap.
    Column("subject_kind", String(8), nullable=False),
    Column("subject_id", UUID(as_uuid=False), nullable=False),
    Column("name", String(200), nullable=False),
    Column("input", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    # [{path, op, expected}] evaluated against the output after schema validation.
    Column("assertions", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("last_result", String(16), nullable=False, server_default=text("'never_run'")),
    Column("last_run_id", UUID(as_uuid=False), ForeignKey("studio_run.id", ondelete="SET NULL"), nullable=True),
    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    Column("deleted_at", TIMESTAMP(timezone=True), nullable=True),
    CheckConstraint(_in("subject_kind", ("agent", "team")), name="ck_studio_test_case_subject_kind"),
    CheckConstraint(_in("last_result", ("passed", "failed", "never_run")), name="ck_studio_test_case_last_result"),
    Index("ix_studio_test_case_subject", "subject_kind", "subject_id", postgresql_where=text("deleted_at IS NULL")),
)


studio_workspace_file = Table(
    "studio_workspace_file",
    metadata,
    Column("id", UUID(as_uuid=False), primary_key=True, default=uuid.uuid4),
    Column("tenant_id", UUID(as_uuid=False), ForeignKey("tenant.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", UUID(as_uuid=False), ForeignKey("studio_run.id", ondelete="CASCADE"), nullable=False),
    # Relative to studio_run.workspace_prefix.
    Column("path", Text, nullable=False),
    Column("size_bytes", BigInteger, nullable=False, server_default=text("0")),
    Column("content_type", String(255), nullable=True),
    Column("writer_task_id", UUID(as_uuid=False), ForeignKey("studio_agent_task.id", ondelete="SET NULL"), nullable=True),
    # Promotion (decision 11): set when the file became a durable artefact;
    # ``indexed`` only if the builder also opted it into Knowledge Studio.
    Column("promoted_artifact_id", UUID(as_uuid=False), ForeignKey("chat_artifact.id", ondelete="SET NULL"), nullable=True),
    Column("indexed", Boolean, nullable=False, server_default=text("false")),
    Column("created_at", TIMESTAMP(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    UniqueConstraint("run_id", "path", name="uq_studio_workspace_file_path"),
    CheckConstraint("size_bytes >= 0", name="ck_studio_workspace_file_size"),
    CheckConstraint("NOT indexed OR promoted_artifact_id IS NOT NULL", name="ck_studio_workspace_file_indexed_promoted"),
)
