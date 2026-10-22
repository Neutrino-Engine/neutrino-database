from sqlalchemy import (
    Table, Column, Integer, String, Text, TIMESTAMP, Index, Float, ForeignKey, BigInteger, Enum as PgEnum,
    UniqueConstraint
)

from neutrino_database.models.base import metadata
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY
from sqlalchemy import Boolean
from sqlalchemy.sql import func, text
import uuid

providers = Table(
    "providers",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("workspace_id", UUID(as_uuid=False), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False),
    Column("provider_category", String(50), nullable=False),
    Column("service_type", String(50), nullable=False),
    Column("display_name", String(255), nullable=False),
    Column("encrypted_value", Text, nullable=False),
    Column("encryption_method", String(50), nullable=False, server_default=text("'AES-256-GCM'")),
    Column("connection_config", JSONB, nullable=False, server_default=text("'{}'")),
    Column("model_config", JSONB, nullable=False, server_default=text("'{}'")),
    Column("is_active", Boolean, nullable=False, server_default=text("true")),
    Column("is_deleted", Boolean, nullable=False, server_default=text("false")),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    Column("created_by", UUID(as_uuid=False), ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    # Partial: a soft-deleted provider must not block re-adding the same one.
    Index("ux_llm_provider", "workspace_id", "service_type", "display_name",
          unique=True, postgresql_where=text("is_deleted = false")),
    Index("ix_llm_providers_workspace", "workspace_id"),
    Index("ix_llm_providers_service_active", "service_type", "is_active"),
    Index("ix_llm_providers_workspace_service", "workspace_id", "service_type"),
)