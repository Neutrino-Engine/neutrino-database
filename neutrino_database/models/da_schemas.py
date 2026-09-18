"""Canonical Pydantic models for the Data Analytics metadata layer.

Mirror of the SQL schema in ``tables.py`` and the ORM wrappers in
``orm.py`` (NEU-1811 DA-P0). Spec:
``product-feature-roadmap/data-analytics/data-flow.md`` §4.8.

These are the boundary serialization models that flow between
connector-service, agent-platform, and the frontend. Per F4 in
``data-analytics/feature.md``:

  * connector-service uses ``DAConnection`` for tenant-level Connection
    lifecycle CRUD.
  * agent-platform uses ``WorkspaceMetadata`` and its sub-entities for
    metadata sync, T2S prompt rendering, and dashboard surfaces.

Per-service API request/response DTOs (e.g. credentials-masked responses,
input validators, computed-field extensions) live in their respective
service repos and project from these canonical types — they are NOT here.

Serialization conventions (per data-flow.md §4.8):

  * Same model for API, T2S prompt rendering, frontend.
  * ``model_dump_json()`` returns the canonical JSON shape.
  * Null / empty fields can be skipped at the call-site via
    ``exclude_none=True`` so the rendered payload is sparse-where-empty
    + rich-where-populated. The default keeps them so callers reading
    "what does the canonical shape look like" see every field.
  * ``model_validate(orm_instance)`` converts ORM rows to schemas via
    ``from_attributes=True`` on every model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from neutrino_database.models.enums import (
    DAConnectionStatusEnum,
    DADescriptionScopeEnum,
    DADescriptionSourceEnum,
    DAJoinHintSourceEnum,
    DAJoinTypeEnum,
    DAMetricSourceEnum,
    DASourceTypeEnum,
    DATA_BINDING_FORMS,
    DATableTypeEnum,
    DashboardStatusEnum,
    DashboardVisibilityEnum,
    DashboardWidgetTypeEnum,
    DataBindingKindEnum,
)


# Shared base ----------------------------------------------------------------


class _DABase(BaseModel):
    """Common config for all DA canonical schemas.

    ``from_attributes=True`` enables conversion from SQLAlchemy ORM rows
    via ``Schema.model_validate(orm_row)``. ``use_enum_values=False`` keeps
    enums as enum instances so consumers can do enum-equality checks
    instead of string-equality on the wire format.
    """
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=False,
        # Allow population by both field name and any aliases (used when
        # API DTOs in service repos extend / project these).
        populate_by_name=True,
    )


# Nested value types ---------------------------------------------------------


class ForeignKeyTarget(_DABase):
    """One element of ``Column.foreign_key_to`` — composite FKs supported
    by allowing multiple ForeignKeyTarget rows per column.
    """
    target_schema: str
    target_table: str
    target_column: str


class Synonym(_DABase):
    """Entity 7 (§4.8) — nested as a JSONB list inside ``Column.synonyms``.

    Stored as JSONB rather than its own table because churn is light and
    per-item HITL (source + accepted) is still expressible here.
    """
    term: str
    source: DAMetricSourceEnum  # admin_authored / ai_suggested / ai_accepted_by_admin
    accepted: bool = False


class StatisticalProfile(_DABase):
    """Phase-2 stats — shape stored as JSONB on ``Column.statistical_profile``.

    Compact on purpose: T2S rarely needs mean/median/stdev; analytics
    workflows do, but those are deferred to v2 per the "Deliberately
    NOT stored" table in §4.8.
    """
    null_proportion: Optional[float] = None
    unique_proportion: Optional[float] = None
    min_value: Optional[str] = None
    max_value: Optional[str] = None


# ---------------------------------------------------------------------------
# Tenant-level Connection (Step 1 of data-flow.md)
# ---------------------------------------------------------------------------


class DAConnection(_DABase):
    """The tenant-level DA Connection — the trust relationship + warehouse
    credentials. Connector-service owns lifecycle CRUD (F4).

    Note: ``credentials`` is included in the canonical model. Service-level
    API responses MUST project it out (or mask it). The canonical type is
    "what's stored"; service DTOs decide "what crosses the wire."
    """
    id: UUID
    tenant_id: UUID
    source_type: DASourceTypeEnum
    connection_name: str
    credentials: dict  # KMS-wrapped; opaque to consumers
    status: DAConnectionStatusEnum
    # Tenant-level schema allowlist (NEU-1811 DA-P1f). None = unrestricted;
    # list[str] = whitelist of allowed schema names.
    allowed_schemas: Optional[list[str]] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Workspace metadata layer (Entities 2–4, 7 in §4.8)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tenant catalog (facts) — discovered by connector-service, shared across
# every workspace in the tenant.
# ---------------------------------------------------------------------------


class DACatalogColumn(_DABase):
    """Tenant-level column fact + compliance classification.

    DDL-derived facts (name, type, nullability, PK/FK, native_comment,
    ordinal) plus catalog-owned classification (is_pii / is_restricted).
    Per-workspace LLM context (descriptions, synonyms, sample values)
    lives on WorkspaceCurationDAColumn — facts up, opinions down.
    """
    id: UUID
    da_catalog_table_id: UUID

    # DDL-derived facts
    column_name: str
    data_type: str
    nullable: bool
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_to: Optional[list[ForeignKeyTarget]] = None
    native_comment: Optional[str] = None
    ordinal_position: int

    # Compliance classification — tenant-owned, no workspace override
    # for is_pii at all. is_restricted can only be upgraded via
    # WorkspaceCurationDAColumn.is_restricted_override.
    is_pii: bool = False
    is_restricted: bool = False

    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DACatalogTable(_DABase):
    """Tenant-level table fact within a catalog schema.

    Carries the table-level half of hierarchical classification
    (DA-P1i.3): when ``is_pii`` or ``is_restricted`` is true, every
    column in this table is effectively classified regardless of
    column-level flags.
    """
    id: UUID
    da_catalog_schema_id: UUID

    table_name: str
    table_type: DATableTypeEnum
    native_comment: Optional[str] = None
    row_count: Optional[int] = None
    is_pii: bool = False
    is_restricted: bool = False

    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Children — assembled by the service layer when the consumer wants
    # the hierarchical view.
    columns: list[DACatalogColumn] = Field(default_factory=list)


class DACatalogSchema(_DABase):
    """Tenant-level schema fact within a Connection.

    Carries the schema-level half of hierarchical classification
    (DA-P1i.3): when ``is_pii`` or ``is_restricted`` is true, every
    table + column inside is effectively classified.
    """
    id: UUID
    da_connection_id: UUID

    schema_name: str
    schema_description: Optional[str] = None
    is_pii: bool = False
    is_restricted: bool = False
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    tables: list[DACatalogTable] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Workspace curation overlays (opinions) — layered on top of the catalog.
# ---------------------------------------------------------------------------


class WorkspaceCurationDAColumn(_DABase):
    """Workspace overlay on a catalog column.

    Holds per-workspace LLM context — single ``description`` field + trust
    metadata, synonyms, sample values, valid aggregations — plus the
    upgrade-only ``is_restricted_override``. No PII override field: PII
    is strictly catalog-owned for compliance consistency.

    DA-P1l.1.0: replaces the two-field model (admin_seed_description +
    ai_generated_description) with a single field + origin / accept
    trust metadata. See description-generation.md §M1, M2.
    """
    id: UUID
    workspace_id: UUID
    da_catalog_column_id: UUID

    # Per-workspace LLM context — single description field
    column_logical_name: Optional[str] = None
    description: Optional[str] = None
    synonyms: Optional[list[Synonym]] = None
    unit: Optional[str] = None
    format_hint: Optional[str] = None
    valid_aggregations: Optional[list[str]] = None

    # Trust metadata (M2). description_origin is 'human' | 'ai'.
    # ai_accepted_at is set only when an ai-origin description has been
    # accepted by the admin — chat reads ai-origin descriptions only
    # when this is non-null.
    description_origin: str = "human"
    ai_accepted_at: Optional[datetime] = None
    ai_last_generated_at: Optional[datetime] = None

    # Phase-2 enrichment (sample values + stats). The sampling toggle
    # itself is workspace-level in workspace_da_settings (M11).
    sample_values: Optional[list] = None
    cardinality_score: Optional[float] = None
    statistical_profile: Optional[StatisticalProfile] = None

    # Upgrade-only restricted override
    is_restricted_override: bool = False

    # Curation
    is_included: bool = False
    is_archived: bool = False
    last_enriched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class WorkspaceCurationDATable(_DABase):
    """Workspace overlay on a catalog table.

    DA-P1l.1.0: single ``description`` field + trust metadata; see
    ``WorkspaceCurationDAColumn`` for the same shape.
    """
    id: UUID
    workspace_id: UUID
    da_catalog_table_id: UUID

    # Per-workspace opinion / context — single description field
    table_logical_name: Optional[str] = None
    description: Optional[str] = None

    # Trust metadata (M2)
    description_origin: str = "human"
    ai_accepted_at: Optional[datetime] = None
    ai_last_generated_at: Optional[datetime] = None

    # Curation
    is_included: bool = False
    is_archived: bool = False
    last_enriched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Children — assembled by the service layer.
    columns: list[WorkspaceCurationDAColumn] = Field(default_factory=list)
    join_hints_from_here: list["JoinHint"] = Field(default_factory=list)


class WorkspaceDASettings(_DABase):
    """Workspace-level Data Analytics settings (DA-P1l.1.0, M11).

    One row per workspace, lazy-created on first PATCH. Holds the two
    AI description-generation toggles today; future DA workspace settings
    accumulate here.

    Both toggles default TRUE (fail-safe). Admin opts down deliberately
    via the workspace settings UI.
    """
    workspace_id: UUID

    # M11 toggles
    da_include_sample_values: bool = True
    da_pii_redaction_enabled: bool = True

    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Independent entities (5, 6, 8) — separate tables, separate lifecycles
# ---------------------------------------------------------------------------


class Metric(_DABase):
    """Entity 5 — workspace-scoped business metric. HITL via ``accepted``."""
    id: UUID
    workspace_id: UUID
    name: str
    description: Optional[str] = None
    sql_expression: str
    filters: Optional[str] = None
    applicable_tables: list[str] = Field(default_factory=list)
    valid_dimensions: Optional[list[str]] = None
    source: DAMetricSourceEnum
    accepted: bool = False
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    last_used_at: Optional[datetime] = None
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime


class JoinHint(_DABase):
    """Entity 6 — workspace-scoped join hint between two curated tables."""
    id: UUID
    workspace_id: UUID
    left_table_id: UUID
    left_columns: list[str]
    right_table_id: UUID
    right_columns: list[str]
    join_type: DAJoinTypeEnum
    semantic_description: Optional[str] = None
    source: DAJoinHintSourceEnum
    accepted: bool = False
    created_by: Optional[UUID] = None
    is_archived: bool = False
    created_at: datetime


class DescriptionVersion(_DABase):
    """Entity 8 — append-only version row.

    Soft-FK: ``parent_id`` points at one of four parent tables depending
    on ``scope``. The service layer (agent-platform) enforces that the
    (scope, parent_id) pair is consistent — Postgres doesn't natively
    support discriminated FKs.
    """
    id: UUID
    scope: DADescriptionScopeEnum
    parent_id: UUID
    version_number: int
    source: DADescriptionSourceEnum
    content: str
    generated_at: datetime
    generated_by: Optional[UUID] = None
    # Open-ended dict — shape varies by source (AI-generated entries carry
    # DDL + comments + seed + samples + stats; admin-edited entries are
    # typically empty here; native_comment entries also empty).
    inputs_snapshot: Optional[dict] = None


# ---------------------------------------------------------------------------
# Root container — the canonical workspace metadata blob
# ---------------------------------------------------------------------------


class WorkspaceMetadata(_DABase):
    """Root container for a workspace's full DA metadata.

    Assembled by the service layer (agent-platform): joins
    ``da_catalog_schema / table / column`` (tenant facts) with
    ``workspace_curation_da_table / column`` (workspace opinions) for
    the workspace in question, plus its metrics and join hints. The
    same model is the "boundary serialization" contract from
    data-flow.md §4.8 — used for T2S prompt rendering, API responses,
    and frontend consumption.

    Note that ``DACatalogSchema`` is the top-level grouping because
    schemas are discovered facts; only the curated tables / columns
    nested under it carry workspace opinions.
    """
    workspace_id: UUID
    workspace_name: str
    last_synced_at: Optional[datetime] = None
    catalog_schemas: list[DACatalogSchema] = Field(default_factory=list)
    curated_tables: list[WorkspaceCurationDATable] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)


# Forward-reference resolution. WorkspaceCurationDATable holds a list of
# JoinHint, which is declared earlier in the file as a forward reference
# string; rebuild so the annotation resolves to the class object.
WorkspaceCurationDATable.model_rebuild()


# ---------------------------------------------------------------------------
# Dashboards (NEU-1811 DA-P3.1). The authored-surface layer above the
# DA catalog. Workspace-scoped; Draft / Published lifecycle; widgets
# compose freely across the workspace's enabled schemas.
# ---------------------------------------------------------------------------


class DashboardWidgetPosition(_DABase):
    """12-col grid position for one widget on a dashboard canvas.

    x ∈ [0, 12); w ∈ [1, 12]; y unbounded above; h ∈ [1, 12]. Service
    layer validates ranges + non-overlap. Defaults in the schema
    correspond to a 4×2 tile at the top-left.
    """
    x: int = 0
    y: int = 0
    w: int = 4
    h: int = 2


class DashboardWidgetDataBinding(_DABase):
    """How a widget gets its data — one query, in whichever language its
    connection speaks.

    A widget is a QUERY, not a snapshot: it re-executes on every dashboard
    load. Originally that query could only be SQL, which quietly made a
    dashboard a relational-only surface — a chart over a Mongo collection could
    be produced in chat but never kept, purely because of where its data lived.
    That distinction is invisible in the question the user asked, so it does not
    decide whether the answer can be saved.

    ``kind`` names the form; ``DATA_BINDING_FORMS`` in models.enums says what
    each form requires and which connector-service route executes it. Adding a
    datasource — Iceberg, Trino, whatever — is a member on
    ``DataBindingKindEnum`` plus a row in that table: this model needs no new
    branch, and every consumer that dispatches on ``kind`` keeps working. The
    tag exists precisely so no reader has to guess a binding's type from which
    fields happen to be set, which is the thing that would have to be re-taught
    in N places per new source.

    Read-only enforcement and schema scope live downstream at
    connector-service for every route in the table, so no form is more
    privileged than another.

    ``query_ref_id`` is reserved for the future saved-query indirection
    (TD-DASH-SAVED-QUERIES-1); when set, the query is derived from it instead
    of stored verbatim.
    """
    connection_id: UUID

    # Absent on widgets written before the tag existed; inferred below.
    kind: Optional[DataBindingKindEnum] = None

    # ── relational form ──────────────────────────────────────────────
    schema_name: Optional[str] = None
    sql: Optional[str] = None

    # ── document form ────────────────────────────────────────────────
    database: Optional[str] = None
    collection: Optional[str] = None
    # A list of aggregation stages. Stored verbatim and forwarded opaquely;
    # connector-service's mongo_guard rejects a write stage, exactly as it does
    # for a pipeline sent from chat.
    pipeline: Optional[list[dict]] = None

    # Optional bind params for parameterised widgets (e.g. filter UI).
    params: Optional[dict] = None
    query_ref_id: Optional[UUID] = None

    @property
    def execute_route(self) -> str:
        """The connector-service route suffix that runs this binding.

        One lookup, shared by the authed widget fetch and the anonymous
        share-link executor, so they cannot drift on which endpoint runs which
        binding.
        """
        return str(DATA_BINDING_FORMS[self.resolved_kind]["execute_route"])

    @property
    def execute_body(self) -> dict:
        """The request body for ``execute_route``.

        Built from ``body_fields`` rather than by a per-kind branch, so a new
        datasource is still one table row. Not the same as the required fields:
        a relational binding needs ``schema_name`` to be valid, but the execute
        route does not take it.
        """
        fields = DATA_BINDING_FORMS[self.resolved_kind]["body_fields"]
        return {f: getattr(self, f) for f in fields}  # type: ignore[union-attr]

    @property
    def resolved_kind(self) -> DataBindingKindEnum:
        """``kind``, or the inferred kind for a legacy binding."""
        return self.kind or DataBindingKindEnum.RELATIONAL

    @model_validator(mode="after")
    def _complete_for_its_kind(self) -> "DashboardWidgetDataBinding":
        """Tag the binding if untagged, then check the fields its kind needs.

        Inference is for stored rows only: every binding written before the tag
        existed is relational, because that was the only form there was. New
        writers pass ``kind`` explicitly.

        A binding carrying more than one form's query is rejected rather than
        resolved by precedence — the forms select different executors, so such a
        binding is a widget whose behaviour depends on which check runs first.
        Unconstructible is cheaper than deterministic.
        """
        present = {
            k
            for k, spec in DATA_BINDING_FORMS.items()
            if any(
                getattr(self, f, None) is not None
                for f in spec["required"]  # type: ignore[union-attr]
            )
        }
        if len(present) > 1:
            named = ", ".join(sorted(k.value for k in present))
            raise ValueError(
                f"data_binding carries more than one query form ({named}); "
                "a widget runs one query"
            )

        if self.kind is None:
            if not present:
                raise ValueError(
                    "data_binding has no query; expected one of: "
                    + ", ".join(
                        f"{k.value} ({', '.join(s['required'])})"  # type: ignore[arg-type]
                        for k, s in DATA_BINDING_FORMS.items()
                    )
                )
            object.__setattr__(self, "kind", next(iter(present)))

        missing = [
            f
            for f in DATA_BINDING_FORMS[self.kind]["required"]  # type: ignore[index,union-attr]
            if getattr(self, f, None) is None
        ]
        if missing:
            raise ValueError(
                f"a {self.kind.value} binding requires " + ", ".join(missing)
            )
        return self


class DashboardWidgetVizSpec(_DABase):
    """Chart-shape spec mirrored on the FE renderer. Free-form-ish
    (kept as dict-like since chart types have diverging shapes), but
    a few canonical fields are first-class.
    """
    chart_type: Optional[str] = None
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    series: Optional[str] = None
    format: Optional[dict] = None
    extras: Optional[dict] = None


class DashboardWidgetGrounding(_DABase):
    """Provenance the build agent records when proposing a widget —
    surfaces on the dashboard's trust footer + library card.
    """
    tables: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    curator: Optional[str] = None
    last_validated_at: Optional[datetime] = None


class DashboardWidget(_DABase):
    """A single widget on a dashboard."""
    id: UUID
    dashboard_id: UUID
    position_x: int
    position_y: int
    position_w: int
    position_h: int
    widget_type: DashboardWidgetTypeEnum
    title: str
    description: Optional[str] = None
    data_binding: dict
    viz_spec: dict
    grounding_metadata: Optional[dict] = None
    created_by_message_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class Dashboard(_DABase):
    """Workspace-scoped authored dashboard. Drafts in the Library are
    these rows with ``status='draft'``; Published are flipped.
    """
    id: UUID
    tenant_id: UUID
    workspace_id: UUID
    slug: str
    name: str
    description: Optional[str] = None
    status: DashboardStatusEnum
    visibility: DashboardVisibilityEnum
    pinned: bool = False
    # The build chat that authored this dashboard (1:1). May be NULL
    # if the chat row was compliance-purged independently.
    build_chat_id: Optional[UUID] = None
    owner_id: Optional[UUID] = None
    created_by: Optional[UUID] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DashboardWithWidgets(_DABase):
    """Render-time payload — dashboard + its widgets in one fetch.
    Used by the FE editor + viewer + public link viewer.
    """
    dashboard: Dashboard
    widgets: list[DashboardWidget] = Field(default_factory=list)


class DashboardLinkToken(_DABase):
    """Canonical row shape for ``dashboard_link_token`` (DA-P3.4).

    Internal use only — services that read this know the storage
    contract: ``token_hash`` is SHA-256(plaintext-token) hex-encoded,
    ``token_short`` is the first 8 chars of the plaintext for UI
    identification. **Do not return this model directly from public
    endpoints** — use ``DashboardLinkTokenResponse`` (no hash leak)
    or ``DashboardLinkTokenMintResponse`` (carries the plaintext
    exactly once, only from the mint endpoint).
    """
    id: UUID
    dashboard_id: UUID
    token_hash: str
    token_short: str
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by_user_id: Optional[UUID] = None
    created_by: Optional[UUID] = None
    accessed_count: int = 0
    created_at: datetime


class DashboardLinkTokenResponse(_DABase):
    """Boundary DTO for the share dialog's "list active links" view.

    Carries only non-secret fields: ``id``, ``token_short`` (for human
    identification), lifecycle timestamps, creator, view counter. Never
    leaks ``token_hash`` (the at-rest hash, useless to clients but
    still credential-shaped) and never leaks the plaintext (only the
    mint response holds that).
    """
    id: UUID
    dashboard_id: UUID
    token_short: str
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by_user_id: Optional[UUID] = None
    created_by: Optional[UUID] = None
    accessed_count: int = 0
    created_at: datetime


class DashboardLinkTokenMintRequest(_DABase):
    """Curator's mint request.

    ``expires_at`` is optional (None = no expiry — recipient can view
    until the link is explicitly revoked). The share dialog surfaces a
    picker (None / 7d / 30d / 90d / Custom); explicit picker choice
    raises compliance posture without forcing every link to expire.
    """
    expires_at: Optional[datetime] = None


class DashboardLinkTokenMintResponse(_DABase):
    """One-shot mint response — the plaintext ``token`` materialises
    here and only here.

    The FE shows it to the curator once (with copy-to-clipboard); a
    page refresh later returns ``DashboardLinkTokenResponse`` without
    it. Same UX pattern as Stripe API key creation + GitHub PAT
    creation. Wrap the row metadata + the share URL so the FE doesn't
    have to reconstruct the URL from the token.
    """
    link: DashboardLinkTokenResponse
    token: str
    share_url: str
