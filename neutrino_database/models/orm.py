from neutrino_database.models.credentials.api_keys import providers
from neutrino_database.models.enums import (
    AgentMessageRole,
    ChatKindEnum,
    DAAccessEffectEnum,
    DAAccessResourceTypeEnum,
    DADescriptionScopeEnum,
    DADescriptionSourceEnum,
    DAEnrichmentOperationEnum,
    DAEnrichmentRunStatusEnum,
    DAEnrichmentScopeEnum,
    DAEnrichmentStageStatusEnum,
    DAJoinHintSourceEnum,
    DAJoinTypeEnum,
    DAMetricSourceEnum,
    DATableTypeEnum,
    DashboardProposalStateEnum,
    DashboardStatusEnum,
    DashboardVisibilityEnum,
    DashboardWidgetTypeEnum,
    ExcelDatasetStatus,
    IdpProviderEnum,
    IntegrationAuthKindEnum,
    IntegrationEnablementStatusEnum,
    IntegrationGrantEffectEnum,
    IntegrationIdentityKindEnum,
    IntegrationOwnerKindEnum,
    IntegrationStatusEnum,
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
    WorkflowStatusEnum,
    WorkflowRunStatusEnum,
    WorkflowActorKindEnum,
    WorkflowRunStepStatusEnum,
    WorkflowTriggerKindEnum,
    WorkflowTriggerStatusEnum,
    WorkspaceAccessStatusEnum,
    WorkspaceStatusEnum,
)
from neutrino_database.models import tables
from neutrino_database.models.base import Base
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Mapped, relationship


class LockLease(Base):
    """ORM wrapper for mutex_locks table"""
    __table__ = tables.lock_lease

    # Type hints
    name: Mapped[str]
    owner_id: Mapped[Optional[str]]
    lease_until: Mapped[Optional[datetime]]
    fencing_token: Mapped[int]


class RotationMutex(Base):
    """ORM wrapper for rotation_mutex table"""
    __table__ = tables.rotation_mutex

    # Type hints
    id: Mapped[bool]
    held_by: Mapped[Optional[str]]
    held_since: Mapped[Optional[datetime]]


class SigningKey(Base):
    """ORM wrapper for signing_keys table"""
    __table__ = tables.signing_key

    # Type hints
    kid: Mapped[str]
    public_pem: Mapped[str]
    private_pem: Mapped[str]
    status: Mapped[KeyStatusEnum]
    not_before: Mapped[Optional[datetime]]
    not_after: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]


class TenantAuthzStore(Base):
    """ORM wrapper for tenant_authz_store table"""
    __table__ = tables.tenant_authz_store

    # Type hints
    id: Mapped[str]
    tenant_id: Mapped[str]
    store_id: Mapped[str]
    model_id: Mapped[str]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    # Relationship to Tenant
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="authz_store")


class Tenant(Base):
    """ORM wrapper for tenant table"""
    __table__ = tables.tenant

    # Type hints for all columns
    id: Mapped[str]
    name: Mapped[str]
    org_external_id: Mapped[str]
    status: Mapped[TenantStatusEnum]
    allowed_modules: Mapped[Optional[list]]
    status_updated_at: Mapped[Optional[datetime]]
    status_updated_by: Mapped[Optional[str]]
    status_reason: Mapped[Optional[str]]
    tenant_owner: Mapped[Optional[str]]
    onboarding_completed_at: Mapped[Optional[datetime]]
    max_workspaces: Mapped[int]
    allowed_invitation_domains: Mapped[List[str]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    deleted_at: Mapped[Optional[datetime]]

    # Relationships
    owner: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="Tenant.tenant_owner",
        back_populates="owned_tenants"
    )

    authz_store: Mapped[Optional["TenantAuthzStore"]] = relationship(
        "TenantAuthzStore",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan"
    )

    users: Mapped[List["User"]] = relationship(
        "User",
        foreign_keys="User.tenant_id",
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    roles: Mapped[List["Role"]] = relationship(
        "Role",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )

    workspaces: Mapped[List["Workspace"]] = relationship(
        "Workspace",
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    invitations: Mapped[List["UserInvitation"]] = relationship(
        "UserInvitation",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )

    identities: Mapped[List["TenantIdentity"]] = relationship(
        "TenantIdentity",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )

    chats: Mapped[List["Chat"]] = relationship(
        "Chat",
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    runs: Mapped[List["Run"]] = relationship(
        "Run",
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class User(Base):
    """ORM wrapper for user table"""
    __table__ = tables.user

    # Type hints for all columns
    id: Mapped[str]
    tenant_id: Mapped[str]
    email: Mapped[str]
    display_name: Mapped[Optional[str]]
    status: Mapped[UserStatusEnum]
    first_login_at: Mapped[Optional[datetime]]
    last_login_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    deleted_at: Mapped[Optional[datetime]]
    default_workspace_id: Mapped[Optional[str]]
    username: Mapped[Optional[str]]
    password_hash: Mapped[Optional[str]]
    must_change_password: Mapped[bool]
    password_changed_at: Mapped[Optional[datetime]]
    # NEU-X8 — touched on promote / demote / transfer-accept; auth
    # middleware force-renews stale JWTs by comparing this against iat.
    permissions_changed_at: Mapped[Optional[datetime]]

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        foreign_keys="User.tenant_id",
        back_populates="users"
    )

    owned_tenants: Mapped[List["Tenant"]] = relationship(
        "Tenant",
        foreign_keys="Tenant.tenant_owner",
        back_populates="owner"
    )

    default_workspace: Mapped[Optional["Workspace"]] = relationship(
        "Workspace",
        foreign_keys="User.default_workspace_id",
        back_populates="default_for_users"
    )

    sso_identities: Mapped[List["SSOIdentity"]] = relationship(
        "SSOIdentity",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    members: Mapped[List["Member"]] = relationship(
        "Member",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    chats: Mapped[List["Chat"]] = relationship(
        "Chat",
        foreign_keys="Chat.created_by",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    messages: Mapped[List["Message"]] = relationship(
        "Message",
        foreign_keys="Message.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    invitations_sent: Mapped[List["UserInvitation"]] = relationship(
        "UserInvitation",
        foreign_keys="UserInvitation.inviter",
        back_populates="inviter_user",
        cascade="all, delete-orphan"
    )

    created_workspaces: Mapped[List["Workspace"]] = relationship(
        "Workspace",
        foreign_keys="Workspace.created_by",
        back_populates="creator"
    )

    workspace_memberships: Mapped[List["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    workspace_access_requests: Mapped[List["WorkspaceAccessRequest"]] = relationship(
        "WorkspaceAccessRequest",
        foreign_keys="WorkspaceAccessRequest.user_id",
        back_populates="user"
    )

    reviewed_access_requests: Mapped[List["WorkspaceAccessRequest"]] = relationship(
        "WorkspaceAccessRequest",
        foreign_keys="WorkspaceAccessRequest.reviewed_by",
        back_populates="reviewer"
    )

    workspace_invitations_sent: Mapped[List["WorkspaceInvitation"]] = relationship(
        "WorkspaceInvitation",
        foreign_keys="WorkspaceInvitation.inviter",
        back_populates="inviter_user"
    )

    runs: Mapped[List["Run"]] = relationship(
        "Run",
        foreign_keys="Run.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    created_providers: Mapped[List["Provider"]] = relationship(
        "Provider",
        foreign_keys="Provider.created_by",
        back_populates="creator"
    )

class PlatformUser(Base):
    """ORM wrapper for platform_user table (NC-494).

    A cross-tenant operator. Has no ``tenant_id`` and no relationship to
    ``Tenant`` — that absence is the point: nothing about this row is scoped
    to a tenant, so no tenant-scoped query can ever return one.
    """
    __table__ = tables.platform_user

    id: Mapped[str]
    email: Mapped[str]
    display_name: Mapped[Optional[str]]
    status: Mapped[PlatformUserStatusEnum]
    password_hash: Mapped[str]
    must_change_password: Mapped[bool]
    password_changed_at: Mapped[Optional[datetime]]
    last_login_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    deleted_at: Mapped[Optional[datetime]]


class TenantIdentity(Base):
    """ORM wrapper for tenant_identity table"""
    __table__ = tables.tenant_identity

    # Type hints for all columns
    id: Mapped[str]
    tenant_id: Mapped[str]
    provider: Mapped[IdpProviderEnum]
    provider_org_id: Mapped[str]
    created_at: Mapped[datetime]

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="identities"
    )


class SSOIdentity(Base):
    """ORM wrapper for sso_identity table"""
    __table__ = tables.sso_identity

    # Type hints for all columns
    id: Mapped[str]
    user_id: Mapped[str]
    provider: Mapped[IdpProviderEnum]
    provider_user_id: Mapped[str]
    provider_org_id: Mapped[str]
    last_login_at: Mapped[Optional[datetime]]
    raw_profile: Mapped[Optional[dict]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="sso_identities"
    )


class Member(Base):
    """ORM wrapper for member table"""
    __table__ = tables.member

    # Type hints for all columns
    id: Mapped[str]
    user_id: Mapped[Optional[str]]
    email: Mapped[Optional[str]]
    name: Mapped[Optional[str]]
    provider: Mapped[IdpProviderEnum]
    provider_user_id: Mapped[str]
    provider_org_id: Mapped[str]
    source: Mapped[MemberSourceEnum]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="members"
    )


class Role(Base):
    """ORM wrapper for role table"""
    __table__ = tables.role

    # Type hints for all columns
    id: Mapped[str]
    tenant_id: Mapped[str]
    key: Mapped[str]
    name: Mapped[str]
    description: Mapped[Optional[str]]

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="roles"
    )


class AppPermission(Base):
    """ORM wrapper for app_permission table"""
    __table__ = tables.app_permission

    # Type hints for all columns
    id: Mapped[str]
    key: Mapped[str]
    name: Mapped[str]
    description: Mapped[Optional[str]]


class UserInvitation(Base):
    """ORM wrapper for user_invitation table"""
    __table__ = tables.user_invitation

    # Type hints for all columns
    id: Mapped[str]
    tenant_id: Mapped[str]
    inviter: Mapped[str]
    email: Mapped[str]
    expires_at: Mapped[datetime]
    accepted_at: Mapped[Optional[datetime]]
    deleted_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="invitations"
    )

    inviter_user: Mapped["User"] = relationship(
        "User",
        foreign_keys="UserInvitation.inviter",
        back_populates="invitations_sent"
    )


class Chat(Base):
    """ORM wrapper for chat table"""
    __table__ = tables.chat

    # Type hints for all columns
    id: Mapped[str]
    tenant_id: Mapped[str]
    # X-CHAT-WS-1 — workspace this thread belongs to. NOT NULL; FK
    # CASCADE to workspace. Every query path filters on this column
    # against ``principal.workspace_id`` so switching workspaces
    # switches conversation context cleanly.
    workspace_id: Mapped[str]
    created_by: Mapped[Optional[str]]
    title: Mapped[Optional[str]]
    incognito: Mapped[bool]
    pinned: Mapped[bool]
    # D6 — chat thread kind. ``ad_hoc`` (default) for Q&A;
    # ``dashboard_build`` for build conversations linked to a Dashboard.
    kind: Mapped[ChatKindEnum]
    # 1:1 back-pointer to the Dashboard this chat is building. NULL
    # for ad_hoc chats; CASCADE on dashboard delete.
    dashboard_id: Mapped[Optional[str]]
    # TD-DA-PILLAR-PERSIST — pillar this chat was initiated on. NULL for
    # Unified (AUTO, spans all pillars) and legacy pre-column rows.
    pillar: Mapped[Optional[PillarEnum]]
    # DA data scope (only set when pillar == DATA_ANALYTICS). Mirrors the
    # FE text_to_sql_config so a reopened DA chat restores its schema.
    # NC-474 — ``da_connection_id`` is the authoritative pin; the name is kept
    # for display and for resolving chats created before the column existed.
    da_connection_id: Mapped[Optional[str]]
    da_connection_name: Mapped[Optional[str]]
    da_schema_name: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    deleted_at: Mapped[Optional[datetime]]

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="chats"
    )

    user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="Chat.created_by",
        back_populates="chats"
    )

    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    runs: Mapped[List["Run"]] = relationship(
        "Run",
        foreign_keys="Run.session_id",
        back_populates="chat",
        cascade="all, delete-orphan"
    )


class Message(Base):
    """ORM wrapper for message table"""
    __table__ = tables.message

    # Type hints for all columns
    id: Mapped[str]
    tenant_id: Mapped[str]
    chat_id: Mapped[str]
    user_id: Mapped[Optional[str]]
    role: Mapped[MessageRoleEnum]
    content: Mapped[str]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    deleted_at: Mapped[Optional[datetime]]

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="messages"
    )

    chat: Mapped["Chat"] = relationship(
        "Chat",
        back_populates="messages"
    )

    user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="Message.user_id",
        back_populates="messages"
    )

    runs: Mapped[List["Run"]] = relationship(
        "Run",
        back_populates="message",
        cascade="all, delete-orphan"
    )

class Workspace(Base):
    """ORM wrapper for workspace table"""
    __table__ = tables.workspace

    # Type hints for all columns
    id: Mapped[str]
    tenant_id: Mapped[str]
    name: Mapped[str]
    description: Mapped[Optional[str]]
    status: Mapped[WorkspaceStatusEnum]
    enabled_pillars: Mapped[List[PillarEnum]]
    hide_chat_pillars: Mapped[bool]
    created_by: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    deleted_at: Mapped[Optional[datetime]]
    deletion_scheduled_for: Mapped[Optional[datetime]]
    deletion_initiated_by: Mapped[Optional[str]]

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="workspaces"
    )

    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="Workspace.created_by",
        back_populates="created_workspaces"
    )

    default_for_users: Mapped[List["User"]] = relationship(
        "User",
        foreign_keys="User.default_workspace_id",
        back_populates="default_workspace"
    )

    members: Mapped[List["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )

    access_requests: Mapped[List["WorkspaceAccessRequest"]] = relationship(
        "WorkspaceAccessRequest",
        foreign_keys="WorkspaceAccessRequest.workspace_id",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )

    invitations: Mapped[List["WorkspaceInvitation"]] = relationship(
        "WorkspaceInvitation",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )

    orchestrator_config: Mapped[Optional["OrchestratorConfig"]] = relationship(
        "OrchestratorConfig",
        back_populates="workspace",
        uselist=False,
        cascade="all, delete-orphan"
    )

    runs: Mapped[List["Run"]] = relationship(
        "Run",
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    providers: Mapped[List["Provider"]] = relationship(
        "Provider",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )


class WorkspaceMember(Base):
    """ORM wrapper for workspace_member table"""
    __table__ = tables.workspace_member

    # Type hints for all columns
    id: Mapped[str]
    workspace_id: Mapped[str]
    user_id: Mapped[str]
    is_workspace_admin: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    first_visited_at: Mapped[Optional[datetime]]

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="members"
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="workspace_memberships"
    )


class WorkspaceAccessRequest(Base):
    """ORM wrapper for workspace_access_request table"""
    __table__ = tables.workspace_access_request

    # Type hints for all columns
    id: Mapped[str]
    workspace_id: Mapped[str]
    user_id: Mapped[str]
    status: Mapped[WorkspaceAccessStatusEnum]
    requested_at: Mapped[datetime]
    reviewed_by: Mapped[Optional[str]]
    reviewed_at: Mapped[Optional[datetime]]
    review_note: Mapped[Optional[str]]

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        foreign_keys="WorkspaceAccessRequest.workspace_id",
        back_populates="access_requests"
    )

    user: Mapped["User"] = relationship(
        "User",
        foreign_keys="WorkspaceAccessRequest.user_id",
        back_populates="workspace_access_requests"
    )

    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="WorkspaceAccessRequest.reviewed_by",
        back_populates="reviewed_access_requests"
    )


class WorkspaceInvitation(Base):
    """ORM wrapper for workspace_invitation table"""
    __table__ = tables.workspace_invitation

    # Type hints for all columns
    id: Mapped[str]
    workspace_id: Mapped[str]
    inviter: Mapped[str]
    email: Mapped[str]
    is_workspace_admin: Mapped[bool]
    personal_message: Mapped[Optional[str]]
    expires_at: Mapped[datetime]
    accepted_at: Mapped[Optional[datetime]]
    deleted_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="invitations"
    )

    inviter_user: Mapped["User"] = relationship(
        "User",
        foreign_keys="WorkspaceInvitation.inviter",
        back_populates="workspace_invitations_sent"
    )


class OrchestratorConfig(Base):
    """ORM wrapper for orchestrator_config table"""
    __table__ = tables.orchestrator_config

    # Type hints for all columns
    id: Mapped[str]
    workspace_id: Mapped[str]
    router_mode: Mapped[RouterModeEnum]
    router_classification_prompt: Mapped[Optional[str]]
    response_synthesis_prompt: Mapped[Optional[str]]
    retrieval_strategy: Mapped[RetrievalStrategyEnum]
    retrieval_config: Mapped[dict]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="orchestrator_config"
    )

class Run(Base):
    """Top level run record for each agent request."""
    __table__ = tables.runs

    # Type hints for all columns
    id: Mapped[str]
    message_id: Mapped[str]
    session_id: Mapped[Optional[str]]
    tenant_id: Mapped[str]
    workspace_id: Mapped[str]
    user_id: Mapped[Optional[str]]
    status: Mapped[RunStatus]
    input_message: Mapped[str]
    final_answer: Mapped[Optional[str]]
    sources: Mapped[Optional[dict]]
    flow_run_id: Mapped[Optional[str]]
    waiting_instance_id: Mapped[Optional[str]]
    input_request: Mapped[Optional[dict]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    # Relationships
    message: Mapped["Message"] = relationship(
        "Message",
        foreign_keys="Run.message_id",
        back_populates="runs"
    )

    chat: Mapped[Optional["Chat"]] = relationship(
        "Chat",
        foreign_keys="Run.session_id",
        back_populates="runs"
    )

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        foreign_keys="Run.tenant_id",
        back_populates="runs"
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        foreign_keys="Run.workspace_id",
        back_populates="runs"
    )

    user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="Run.user_id",
        back_populates="runs"
    )

    conversations: Mapped[List["ReactConversation"]] = relationship(
        "ReactConversation",
        back_populates="run",
        cascade="all, delete-orphan"
    )

    events: Mapped[List["RunEvent"]] = relationship(
        "RunEvent",
        back_populates="run",
        cascade="all, delete-orphan"
    )

    trace_spans: Mapped[List["TraceSpan"]] = relationship(
        "TraceSpan",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ReactConversation(Base):
    """ReAct messages within a run, supports delegation levels."""
    __table__ = tables.react_conversations

    # Type hints for all columns
    id: Mapped[str]
    run_id: Mapped[str]
    instance_id: Mapped[Optional[str]]
    delegation_level: Mapped[int]
    agent_name: Mapped[str]
    role: Mapped[AgentMessageRole]
    content: Mapped[str]
    tool_name: Mapped[Optional[str]]
    tool_params: Mapped[Optional[dict]]
    created_at: Mapped[datetime]

    # Relationships
    run: Mapped["Run"] = relationship(
        "Run",
        back_populates="conversations"
    )


class RunEvent(Base):
    """Events for SSE streaming and audit trail."""
    __table__ = tables.run_events

    # Type hints for all columns
    id: Mapped[str]
    run_id: Mapped[str]
    sequence: Mapped[int]
    event_type: Mapped[str]
    agent_name: Mapped[Optional[str]]
    instance_id: Mapped[Optional[str]]
    data: Mapped[Optional[dict]]
    created_at: Mapped[datetime]

    # Relationships
    run: Mapped["Run"] = relationship(
        "Run",
        back_populates="events"
    )

class TraceSpan(Base):
    """Observability span for LLM calls, tool calls, and agent runs."""
    __table__ = tables.trace_spans

    id: Mapped[str]
    run_id: Mapped[str]
    parent_span_id: Mapped[Optional[str]]
    sequence: Mapped[int]
    span_type: Mapped[SpanType]
    name: Mapped[str]
    agent_name: Mapped[Optional[str]]
    status: Mapped[SpanStatus]
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime]
    latency_ms: Mapped[int]
    attributes: Mapped[Optional[dict]]
    created_at: Mapped[datetime]

    run: Mapped["Run"] = relationship(
        "Run",
        back_populates="trace_spans",
    )


class ExcelDataset(Base):
    """Uploaded Excel dataset tracked for text-to-SQL."""
    __table__ = tables.excel_datasets

    id: Mapped[str]
    workspace_id: Mapped[str]
    tenant_id: Mapped[str]
    uploaded_by: Mapped[Optional[str]]
    original_filename: Mapped[str]
    schema_name: Mapped[str]
    minio_path: Mapped[str]
    status: Mapped[ExcelDatasetStatus]
    table_metadata: Mapped[Optional[dict]]
    file_size_bytes: Mapped[int]
    error_details: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        foreign_keys="ExcelDataset.workspace_id",
    )

    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        foreign_keys="ExcelDataset.tenant_id",
    )

    uploader: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="ExcelDataset.uploaded_by",
    )


class Provider(Base):  # ← Singular, not Providers
    """ORM wrapper for providers table"""
    __table__ = providers

    id: Mapped[str]
    workspace_id: Mapped[str]
    provider_category: Mapped[str]  # ← ADD THIS NEW FIELD
    service_type: Mapped[str]
    display_name: Mapped[str]
    encrypted_value: Mapped[str]
    encryption_method: Mapped[str]
    connection_config: Mapped[Optional[dict]]  # ← Make Optional
    model_config: Mapped[Optional[dict]]  # ← Make Optional
    is_active: Mapped[bool]
    is_deleted: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    created_by: Mapped[Optional[str]]

    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="providers"
    )

    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="Provider.created_by",  # ← Changed from LLMProvider
        back_populates="created_providers"  # ← Changed from created_llm_providers
    )


class AuditLog(Base):
    """ORM wrapper for audit_log — append-only compliance event store.

    UPDATE and DELETE on this table raise SQLSTATE AU001 via the
    audit_log_immutability Postgres trigger (installed in tables.py).
    Use INSERT only.

    See user-stories/user-lifecycle.md § "Audit log requirements".
    """
    __table__ = tables.audit_log

    id: Mapped[str]
    tenant_id: Mapped[str]
    actor_user_id: Mapped[Optional[str]]
    event_type: Mapped[str]
    resource_type: Mapped[str]
    resource_id: Mapped[str]
    event_metadata: Mapped[dict]
    ip_address: Mapped[Optional[str]]
    user_agent: Mapped[Optional[str]]
    occurred_at: Mapped[datetime]


class TenancyOwnershipTransfer(Base):
    """ORM wrapper for tenancy_ownership_transfer (NEU-X3).

    A pending row exists from the moment the Owner clicks "Transfer
    ownership" until the target accepts, the Owner cancels, the
    7-day window expires, or the retention runner sweeps the row.
    Only one pending row per tenant at any time (partial unique
    index in tables.py).

    See user-stories/tenant-admin-actions.md § 4 (Primary Ownership
    transfer) for the lifecycle.
    """

    __table__ = tables.tenancy_ownership_transfer

    id: Mapped[str]
    tenant_id: Mapped[str]
    from_user_id: Mapped[Optional[str]]
    to_user_id: Mapped[Optional[str]]
    # Plaintext capability token (D-1, deprecated at-rest — kept for consumer
    # backward compat). Prefer resolving via token_hash below.
    token: Mapped[str]
    # SHA-256(plaintext) + non-secret short handle. Nullable during the additive
    # hash-at-rest rollout; mirrors DashboardLinkToken/ShareLink.
    token_hash: Mapped[Optional[str]]
    token_short: Mapped[Optional[str]]
    expires_at: Mapped[datetime]
    accepted_at: Mapped[Optional[datetime]]
    cancelled_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]


# ===========================================================================
# Data Analytics — ORM wrappers (NEU-1811 DA-P0).
#
# Seven tables encoding the DA pillar's per-warehouse curated state. See
# tables.py for the canonical schema and the inline service-ownership
# comment block (feature.md F4). Pydantic boundary models live alongside
# in da_schemas.py — these ORM classes are for SQLAlchemy session use
# (filters, inserts, joins) inside connector-service and agent-platform.
# ===========================================================================


class DACatalogSchema(Base):
    """Tenant-level fact: a schema discovered in a connected warehouse.

    Shared across every workspace in the tenant (the schema exists
    regardless of who curates it). Re-synced by connector-service's
    discovery pass; workspaces layer opinions on top via
    workspace_curation_da_* overlays.
    """

    __table__ = tables.da_catalog_schema

    id: Mapped[str]
    da_connection_id: Mapped[str]
    schema_name: Mapped[str]
    schema_description: Mapped[Optional[str]]
    is_pii: Mapped[bool]
    is_restricted: Mapped[bool]
    last_synced_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class DACatalogTable(Base):
    """Tenant-level fact: a table within a catalog schema.

    No workspace opinion fields here — those live on
    workspace_curation_da_table. Only DDL-derived facts (table_name,
    table_type, native_comment, row_count).
    """

    __table__ = tables.da_catalog_table

    id: Mapped[str]
    da_catalog_schema_id: Mapped[str]
    table_name: Mapped[str]
    table_type: Mapped[DATableTypeEnum]
    native_comment: Mapped[Optional[str]]
    row_count: Mapped[Optional[int]]
    is_pii: Mapped[bool]
    is_restricted: Mapped[bool]
    last_synced_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class DACatalogColumn(Base):
    """Tenant-level fact: a column within a catalog table.

    Holds DDL + compliance classification (is_pii / is_restricted).
    Classification is shared across workspaces — same column has the
    same PII status everywhere. Per-workspace LLM context lives on
    workspace_curation_da_column.
    """

    __table__ = tables.da_catalog_column

    id: Mapped[str]
    da_catalog_table_id: Mapped[str]
    column_name: Mapped[str]
    data_type: Mapped[str]
    nullable: Mapped[bool]
    is_primary_key: Mapped[bool]
    is_foreign_key: Mapped[bool]
    foreign_key_to: Mapped[Optional[list]]
    native_comment: Mapped[Optional[str]]
    ordinal_position: Mapped[int]
    is_pii: Mapped[bool]
    is_restricted: Mapped[bool]
    last_synced_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class WorkspaceCurationDATable(Base):
    """Workspace's opinion layered on a catalog table.

    Thin row: which catalog table this workspace exposes + per-workspace
    ``description`` (single field, two editors — see description-generation.md
    §M1) + trust metadata. One row per (workspace_id, da_catalog_table_id).
    """

    __table__ = tables.workspace_curation_da_table

    id: Mapped[str]
    workspace_id: Mapped[str]
    da_catalog_table_id: Mapped[str]
    table_logical_name: Mapped[Optional[str]]
    description: Mapped[Optional[str]]
    synonyms: Mapped[Optional[list]]
    description_origin: Mapped[str]
    ai_accepted_at: Mapped[Optional[datetime]]
    ai_last_generated_at: Mapped[Optional[datetime]]
    is_included: Mapped[bool]
    is_archived: Mapped[bool]
    last_enriched_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class WorkspaceCurationDAColumn(Base):
    """Workspace's opinion layered on a catalog column.

    Holds per-workspace LLM context (single ``description`` field + trust
    metadata, synonyms, sample values, valid aggregations) plus an
    upgrade-only ``is_restricted_override``. No PII override field — PII
    is strictly catalog-owned for compliance consistency.
    """

    __table__ = tables.workspace_curation_da_column

    id: Mapped[str]
    workspace_id: Mapped[str]
    da_catalog_column_id: Mapped[str]
    column_logical_name: Mapped[Optional[str]]
    description: Mapped[Optional[str]]
    synonyms: Mapped[Optional[list]]
    unit: Mapped[Optional[str]]
    format_hint: Mapped[Optional[str]]
    valid_aggregations: Mapped[Optional[list]]
    description_origin: Mapped[str]
    ai_accepted_at: Mapped[Optional[datetime]]
    ai_last_generated_at: Mapped[Optional[datetime]]
    sample_values: Mapped[Optional[list]]
    cardinality_score: Mapped[Optional[float]]
    statistical_profile: Mapped[Optional[dict]]
    is_restricted_override: Mapped[bool]
    is_included: Mapped[bool]
    is_archived: Mapped[bool]
    last_enriched_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class WorkspaceDASuggestedQuestion(Base):
    """One stored chat starter question for a workspace (NC-570).

    Written by the enrichment run and read by the chat empty state. The row
    carries the finished sentence plus the catalog identity behind it, so the
    serve boundary never has to recover a question's provenance by reading
    names back out of the prose.

    ``shape`` is the question's kind — trend, breakdown, total, ranking — and
    it is load bearing rather than decoration. It carries the icon the client
    renders, AND the serve boundary groups the pool by it so one screen shows
    four kinds of question instead of one sentence four times.

    ``da_catalog_column_ids`` is the NC-568 contract: every column the
    sentence names, so a member denied a column never reads its business name
    off a card. It is NOT NULL because the filter fails closed, and a question
    that records no column can never be proved safe.
    """

    __table__ = tables.workspace_da_suggested_question

    id: Mapped[str]
    workspace_id: Mapped[str]
    tenant_id: Mapped[str]
    da_connection_id: Mapped[str]
    da_catalog_schema_id: Mapped[str]
    da_catalog_table_id: Mapped[str]
    da_catalog_column_ids: Mapped[list]
    question_text: Mapped[str]
    shape: Mapped[str]
    origin: Mapped[str]
    generated_by_run_id: Mapped[Optional[str]]
    generated_at: Mapped[datetime]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class WorkspaceDASettings(Base):
    """Workspace-level Data Analytics settings (DA-P1l.1.0).

    One row per workspace, lazy-created on first PATCH. Holds toggles
    that govern AI description generation behaviour — see M11 in
    ``product-feature-roadmap/data-analytics/description-generation.md``.

    Future DA workspace settings (default model preference, cost cap,
    etc.) land here rather than as JSONB sprawl on the workspace row.
    """

    __table__ = tables.workspace_da_settings

    workspace_id: Mapped[str]
    da_include_sample_values: Mapped[bool]
    da_pii_redaction_enabled: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class DAEnrichmentRun(Base):
    """One triggered DA catalog enrichment run (NC-103).

    The command record for a Reprofile / Regenerate the Data Curation page
    fires: scope × operation × target, the Temporal execution handle, and
    rollup counters that drive the header progress bar. Temporal owns
    execution truth; this row is the projection the FE polls and re-attaches
    to across refreshes.
    """

    __table__ = tables.da_enrichment_run

    id: Mapped[str]
    tenant_id: Mapped[str]
    workspace_id: Mapped[str]
    connection_id: Mapped[str]
    scope: Mapped[DAEnrichmentScopeEnum]
    operation: Mapped[DAEnrichmentOperationEnum]
    schema_id: Mapped[Optional[str]]
    table_id: Mapped[Optional[str]]
    status: Mapped[DAEnrichmentRunStatusEnum]
    total_tables: Mapped[int]
    completed_tables: Mapped[int]
    failed_tables: Mapped[int]
    skipped_tables: Mapped[int]
    temporal_workflow_id: Mapped[Optional[str]]
    temporal_run_id: Mapped[Optional[str]]
    created_by_user_id: Mapped[Optional[str]]
    error: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    started_at: Mapped[Optional[datetime]]
    finished_at: Mapped[Optional[datetime]]


class DAEnrichmentTableItem(Base):
    """Per-table, two-stage progress for a ``DAEnrichmentRun`` (NC-103).

    ``profile_status`` and ``describe_status`` advance independently — NULL
    on a stage means it is not part of the run's operation. Drives the live
    "Profiling…" / "Generating…" / "Profiled ✓" badge on each curation row;
    ``columns_described`` / ``columns_total`` give the "7/12 cols" detail.
    """

    __table__ = tables.da_enrichment_table_item

    id: Mapped[str]
    run_id: Mapped[str]
    da_catalog_table_id: Mapped[str]
    schema_name: Mapped[str]
    table_name: Mapped[str]
    profile_status: Mapped[Optional[DAEnrichmentStageStatusEnum]]
    describe_status: Mapped[Optional[DAEnrichmentStageStatusEnum]]
    columns_total: Mapped[Optional[int]]
    columns_described: Mapped[int]
    error: Mapped[Optional[str]]
    started_at: Mapped[Optional[datetime]]
    finished_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class WorkspaceIntegrationSettings(Base):
    """Workspace-level connector governance policy (WF-CF-1b).

    One row per workspace, lazy-created on first write; absence = defaults
    (permissive, fail-safe). Cross-pillar — the workspace-admin switches that
    gate how members use connectors here (e.g. whether personal connections
    are allowed).
    """

    __table__ = tables.workspace_integration_settings

    workspace_id: Mapped[str]
    allow_personal_integrations: Mapped[bool]
    allow_personal_scoped_workflows: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class WorkspaceDAAccessGrant(Base):
    """Per-member ACL row on a DA catalog resource (X-DA-ACL-1).

    One row per ``(workspace_id, user_id, resource_type, resource_id)``
    grants or denies access at a specific level of the schema → table
    → column tree. Absence of a row at a level = "inherit from
    parent". Resolution rule lives in the service (see
    ``WorkspaceDAAccessService.resolve_effective_access`` in
    agent-platform).

    Tenant Owner / Tenant Admin / Workspace Admin bypass entirely via
    the JWT projection. M10 PII / Restricted catalog flags hard-block
    above this unconditionally.
    """

    __table__ = tables.workspace_da_access_grant

    id: Mapped[str]
    workspace_id: Mapped[str]
    user_id: Mapped[str]
    resource_type: Mapped[DAAccessResourceTypeEnum]
    resource_id: Mapped[str]
    effect: Mapped[DAAccessEffectEnum]
    created_by: Mapped[str]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class Metric(Base):
    """Workspace-scoped business metric.

    HITL lifecycle: AI suggestions land with ``accepted=false`` until an
    admin accepts. Partial unique on (workspace_id, name) WHERE not
    archived — archiving a metric frees its name for reuse.
    """

    __table__ = tables.metric

    id: Mapped[str]
    workspace_id: Mapped[str]
    name: Mapped[str]
    description: Mapped[Optional[str]]
    sql_expression: Mapped[str]
    filters: Mapped[Optional[str]]
    applicable_tables: Mapped[list]
    valid_dimensions: Mapped[Optional[list]]
    source: Mapped[DAMetricSourceEnum]
    accepted: Mapped[bool]
    created_by: Mapped[Optional[str]]
    updated_by: Mapped[Optional[str]]
    last_used_at: Mapped[Optional[datetime]]
    is_archived: Mapped[bool]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class JoinHint(Base):
    """Workspace-scoped join hint between two curated tables.

    Cascades when either side table is removed (the hint becomes
    meaningless). HITL: AI-suggested hints land with ``accepted=false``.
    """

    __table__ = tables.join_hint

    id: Mapped[str]
    workspace_id: Mapped[str]
    left_table_id: Mapped[str]
    left_columns: Mapped[list]
    right_table_id: Mapped[str]
    right_columns: Mapped[list]
    join_type: Mapped[DAJoinTypeEnum]
    semantic_description: Mapped[Optional[str]]
    source: Mapped[DAJoinHintSourceEnum]
    accepted: Mapped[bool]
    created_by: Mapped[Optional[str]]
    is_archived: Mapped[bool]
    created_at: Mapped[datetime]


class DescriptionVersion(Base):
    """Append-only version history for descriptions across 4 scopes.

    Soft-FK pattern: ``parent_id`` points at one of
    ``workspace_metadata_table`` / ``workspace_metadata_column`` /
    ``metric`` / ``join_hint`` — discriminated by ``scope``. Service layer
    enforces parent_id matches the scope.

    No ``updated_at`` — corrections are new versions, not in-place edits.
    """

    __table__ = tables.description_version

    id: Mapped[str]
    scope: Mapped[DADescriptionScopeEnum]
    parent_id: Mapped[str]
    version_number: Mapped[int]
    source: Mapped[DADescriptionSourceEnum]
    content: Mapped[str]
    generated_at: Mapped[datetime]
    generated_by: Mapped[Optional[str]]
    inputs_snapshot: Mapped[Optional[dict]]


# ---------------------------------------------------------------------------
# Dashboards (NEU-1811 DA-P3.1).
# ---------------------------------------------------------------------------


class Dashboard(Base):
    """Workspace-scoped authored dashboard. Draft / Published lifecycle;
    workspace_members / restricted / link_only visibility. 1:1 build
    chat (``build_chat_id`` → chat where kind=dashboard_build). Widgets
    composed across every schema the workspace has DA-enabled.
    """

    __table__ = tables.dashboard

    id: Mapped[str]
    tenant_id: Mapped[str]
    workspace_id: Mapped[str]
    slug: Mapped[str]
    name: Mapped[str]
    description: Mapped[Optional[str]]
    status: Mapped[DashboardStatusEnum]
    visibility: Mapped[DashboardVisibilityEnum]
    pinned: Mapped[bool]
    build_chat_id: Mapped[Optional[str]]
    owner_id: Mapped[Optional[str]]
    created_by: Mapped[Optional[str]]
    published_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class DashboardWidget(Base):
    """A single widget on a dashboard. 12-col grid position
    (x/y/w/h). Inline SQL data binding (Q2 lock in design). viz_spec
    + grounding_metadata carry the chart shape + provenance the build
    agent recorded when proposing this widget.
    """

    __table__ = tables.dashboard_widget

    id: Mapped[str]
    dashboard_id: Mapped[str]
    position_x: Mapped[int]
    position_y: Mapped[int]
    position_w: Mapped[int]
    position_h: Mapped[int]
    widget_type: Mapped[DashboardWidgetTypeEnum]
    title: Mapped[str]
    description: Mapped[Optional[str]]
    data_binding: Mapped[dict]
    viz_spec: Mapped[dict]
    grounding_metadata: Mapped[Optional[dict]]
    created_by_message_id: Mapped[Optional[str]]
    source_artifact_id: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class DashboardLinkToken(Base):
    """Anonymous shareable URL token for one dashboard. Production-grade
    shape (DA-P3.4): the URL-safe plaintext token materialises exactly
    once (in the mint response); the DB stores SHA-256 of it in
    ``token_hash`` plus a non-secret ``token_short`` prefix for UI
    identification. ``revoked_at`` / ``revoked_by_user_id`` close the
    audit trail.
    """

    __table__ = tables.dashboard_link_token

    id: Mapped[str]
    dashboard_id: Mapped[str]
    token_hash: Mapped[str]
    token_short: Mapped[str]
    expires_at: Mapped[Optional[datetime]]
    revoked_at: Mapped[Optional[datetime]]
    revoked_by_user_id: Mapped[Optional[str]]
    created_by: Mapped[Optional[str]]
    accessed_count: Mapped[int]
    created_at: Mapped[datetime]

class DashboardBuildRun(Base):
    """One asynchronous build-agent turn. The POST that starts a turn returns
    this row's id immediately and the agent runs detached, so a dropped
    connection, a refresh or a rolling deploy no longer loses the turn: the
    client re-attaches by run id, and ``result_envelope`` holds the outcome for
    anyone who reconnects after the stream ended.
    """

    __table__ = tables.dashboard_build_run

    id: Mapped[str]
    tenant_id: Mapped[str]
    workspace_id: Mapped[str]
    dashboard_id: Mapped[str]
    build_chat_id: Mapped[Optional[str]]
    user_id: Mapped[Optional[str]]
    status: Mapped[RunStatus]
    user_message: Mapped[str]
    result_envelope: Mapped[Optional[dict]]
    error: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class DashboardProposalState(Base):
    """What became of one widget proposal (applied / removed / dismissed),
    keyed by the build-chat message that carried it plus the proposal's index.

    Exists because widget deletes are hard deletes: without this row, a
    proposal whose widget was deleted looks identical to one that was never
    applied, and the build chat offers "Apply" again.
    """

    __table__ = tables.dashboard_proposal_state

    id: Mapped[str]
    dashboard_id: Mapped[str]
    message_id: Mapped[str]
    proposal_index: Mapped[int]
    state: Mapped[DashboardProposalStateEnum]
    widget_id: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


# ---------------------------------------------------------------------------
# Unified integration hierarchy (WF-VS1).
# ---------------------------------------------------------------------------


class Integration(Base):
    """Unified credential record shared across ES + DA + WF.

    ONE row per credential. The Vault secret lives behind
    ``vault_secret_id`` — never in this row. Established once at the
    tenant level (owner_kind='tenant') or owned by an individual
    (owner_kind='user'). ``identity_kind`` records who the destination
    SaaS sees. ``capabilities`` (text[]) is the cross-pillar axis:
    ES uses 'ingest', DA 'query', WF 'act'.
    """

    __table__ = tables.integration

    id: Mapped[str]
    tenant_id: Mapped[str]
    owner_kind: Mapped[IntegrationOwnerKindEnum]
    owner_user_id: Mapped[Optional[str]]
    workspace_id: Mapped[Optional[str]]
    provider: Mapped[str]
    display_name: Mapped[str]
    vault_secret_id: Mapped[str]
    identity_kind: Mapped[IntegrationIdentityKindEnum]
    identity_label: Mapped[Optional[str]]
    auth_kind: Mapped[IntegrationAuthKindEnum]
    oauth_scopes_granted: Mapped[Optional[List[str]]]
    instance_url: Mapped[Optional[str]]
    external_account_id: Mapped[Optional[str]]
    external_account_name: Mapped[Optional[str]]
    capabilities: Mapped[List[str]]
    status: Mapped[IntegrationStatusEnum]
    last_verified_at: Mapped[Optional[datetime]]
    # NB: the JSONB ``metadata`` column is auto-instrumented from
    # ``__table__``; we don't add a bare ``metadata`` annotation here
    # because it would shadow SQLAlchemy's reserved Declarative attr.
    created_by: Mapped[str]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class IntegrationWorkspaceEnablement(Base):
    """Per-workspace opt-in for a tenant integration.

    A tenant integration is unusable by a workspace until an enablement
    row exists. ``capabilities_enabled`` is a subset of the parent
    integration's capabilities (scope-down enforced in the service).
    """

    __table__ = tables.integration_workspace_enablement

    id: Mapped[str]
    integration_id: Mapped[str]
    workspace_id: Mapped[str]
    capabilities_enabled: Mapped[List[str]]
    display_name_override: Mapped[Optional[str]]
    status: Mapped[IntegrationEnablementStatusEnum]
    enabled_by: Mapped[str]
    enabled_at: Mapped[datetime]


class IntegrationMemberGrant(Base):
    """Per-member ACL on an integration capability (deny-wins-anywhere).

    One row per ``(workspace_id, user_id, integration_id, capability)``.
    Absence of a row = no explicit grant (default deny for members;
    admins bypass via JWT projection). Resolution rule lives in the
    service (mirrors ``WorkspaceDAAccessService``).
    """

    __table__ = tables.integration_member_grant

    id: Mapped[str]
    workspace_id: Mapped[str]
    user_id: Mapped[str]
    integration_id: Mapped[str]
    capability: Mapped[str]
    effect: Mapped[IntegrationGrantEffectEnum]
    created_by: Mapped[str]
    created_at: Mapped[datetime]


class IntegrationDAConfig(Base):
    """DA capability's per-connection config — 1:1 with an integration (DA-U1).

    Keeps the generic ``integration`` row free of pillar-specific columns:
    the tenant schema allowlist (``allowed_schemas``) lives here. Replaces
    ``da_connection.allowed_schemas``; NULL = unrestricted.
    """

    __table__ = tables.integration_da_config

    integration_id: Mapped[str]
    allowed_schemas: Mapped[Optional[list]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class Workflow(Base):
    """Workspace-scoped workflow definition (WF-VS2).

    The low-code builder's output. ``graph`` (JSONB) holds the node/edge
    definition the GenericGraphWorkflow interprets at run time; Temporal owns
    *execution* state, this row owns the *definition*. created_by is metadata
    (SET NULL on user delete), not ownership — the workflow is workspace-owned.
    """

    __table__ = tables.workflow

    id: Mapped[str]
    tenant_id: Mapped[str]
    workspace_id: Mapped[str]
    name: Mapped[str]
    description: Mapped[Optional[str]]
    graph: Mapped[dict]
    status: Mapped[WorkflowStatusEnum]
    created_by: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]


class WorkflowRun(Base):
    """One workflow execution (WF-M1) — the governance record of a run.

    Captures who triggered the run (``actor_user_id`` / ``actor_kind``, with
    ``audit_principal_user_id`` always set), when (``created_at`` =
    triggered, ``started_at`` = execution began) and the total duration to
    ``finished_at``. ``workflow_version_id`` / ``trigger_id`` are unconstrained
    UUIDs until M6 / M4 add their tables. Temporal owns the step-by-step event
    history; this row + ``WorkflowRunStep`` are the queryable, auditable record.
    """

    __table__ = tables.workflow_run

    id: Mapped[str]
    tenant_id: Mapped[str]
    workspace_id: Mapped[str]
    workflow_id: Mapped[str]
    workflow_version_id: Mapped[Optional[str]]
    trigger_id: Mapped[Optional[str]]
    status: Mapped[WorkflowRunStatusEnum]
    actor_user_id: Mapped[Optional[str]]
    actor_kind: Mapped[WorkflowActorKindEnum]
    audit_principal_user_id: Mapped[str]
    temporal_run_id: Mapped[Optional[str]]
    trigger_payload: Mapped[Optional[dict]]
    error_message: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    started_at: Mapped[Optional[datetime]]
    finished_at: Mapped[Optional[datetime]]


class WorkflowRunStep(Base):
    """One executed node within a run (WF-M1) — its I/O, status, and timing.

    ``input_json`` / ``output_json`` hold the node's full payloads (the record
    of truth, redacted per the action's pii_fields in M8); ``attempts`` exposes
    the Temporal retry count; ``started_at`` / ``finished_at`` give the per-node
    time taken. Cascade-deleted with its parent run.
    """

    __table__ = tables.workflow_run_step

    id: Mapped[str]
    run_id: Mapped[str]
    step_id: Mapped[str]
    node_kind: Mapped[str]
    status: Mapped[WorkflowRunStepStatusEnum]
    input_json: Mapped[Optional[dict]]
    output_json: Mapped[Optional[dict]]
    attempts: Mapped[int]
    pii_classification: Mapped[Optional[List[str]]]
    error_message: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    started_at: Mapped[Optional[datetime]]
    finished_at: Mapped[Optional[datetime]]


class WorkflowTrigger(Base):
    """How a workflow fires without a manual Run click (WF-M3a.2).

    A webhook trigger carries a unique ``token`` whose public URL
    (``POST /triggers/{token}``) starts a run with the request body as the
    trigger node's payload; cron/event triggers carry their settings in
    ``config``. ``node_id`` binds the trigger to the trigger node in the
    workflow's graph. Cascade-deleted with its workflow.
    """

    __table__ = tables.workflow_trigger

    id: Mapped[str]
    tenant_id: Mapped[str]
    workspace_id: Mapped[str]
    workflow_id: Mapped[str]
    node_id: Mapped[str]
    kind: Mapped[WorkflowTriggerKindEnum]
    # Plaintext webhook token (D-2, deprecated at-rest — kept for consumer
    # backward compat). Prefer resolving via token_hash below.
    token: Mapped[Optional[str]]
    # SHA-256(plaintext) + non-secret short handle. Nullable during the additive
    # hash-at-rest rollout; mirrors DashboardLinkToken/ShareLink.
    token_hash: Mapped[Optional[str]]
    token_short: Mapped[Optional[str]]
    config: Mapped[dict]
    status: Mapped[WorkflowTriggerStatusEnum]
    created_by: Mapped[Optional[str]]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
