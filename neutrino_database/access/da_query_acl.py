"""Can this user read every table and column a query reads? (NC-730)

The one copy of the DA query-authorization rule. Two services ask it:

  * agent-platform, before a public share link serves a stored widget
    query on its author's behalf;
  * connector-service, at the execution boundary, before any SQL or
    aggregation pipeline reaches a customer datasource.

Grant semantics (X-DA-ACL-1.5d) — deny wins anywhere in the chain,
else allow anywhere wins, else the workspace-membership default. The
M10 catalog flags (PII / Restricted, plus the workspace's
``is_restricted_override`` escalation) hard-block above all grants.

**Fails closed.** Every uncertainty is a refusal: no targets, a name
that resolves to no catalog row, a name that resolves to more than one,
an unknown projection whose table has no catalogued columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from neutrino_database.models.enums import (
    DAAccessEffectEnum,
    DAAccessResourceTypeEnum,
)
from neutrino_database.models.orm import (
    DACatalogColumn,
    DACatalogSchema,
    DACatalogTable,
    WorkspaceCurationDAColumn,
    WorkspaceDAAccessGrant,
    WorkspaceMember,
)


@dataclass(frozen=True)
class QueryTarget:
    """One table (or collection) a query reads, named the way the query
    named it.

    ``schema_name`` is None when the query left the table unqualified —
    the caller supplies the schema the executor resolves it against as
    the fallback. For a document store the schema is the database and
    the table is the collection.
    """

    schema_name: Optional[str]
    table_name: str


def walk_grants(
    grants: dict[tuple[str, str], str],
    *,
    chain: Sequence[tuple[str, str]],
    member_default: bool,
) -> bool:
    """Deny anywhere in ``chain`` wins, else allow anywhere wins, else
    ``member_default``.

    ``chain`` is leaf-first ``(resource_type_value, resource_id)`` pairs;
    the keys are raw VARCHAR values, not enum members, because that is
    what the driver returns for both columns.

    M10 is NOT part of this. It is a catalog fact rather than a grant,
    and the callers apply it before walking.
    """
    allow = DAAccessEffectEnum.ALLOW.value
    saw_allow = False
    for resource_type, resource_id in chain:
        effect = grants.get((resource_type, resource_id))
        if effect is None:
            continue
        if effect != allow:
            return False
        saw_allow = True
    return True if saw_allow else member_default


async def is_workspace_member(
    session: AsyncSession, *, workspace_id: str, user_id: str
) -> bool:
    row = (
        await session.execute(
            select(WorkspaceMember.id).where(
                WorkspaceMember.workspace_id == str(workspace_id),
                WorkspaceMember.user_id == str(user_id),
            )
        )
    ).scalar_one_or_none()
    return row is not None


def _fold(name: str, case_sensitive: bool) -> str:
    name = name.strip()
    return name if case_sensitive else name.lower()


async def can_user_read_query_targets(
    session: AsyncSession,
    *,
    workspace_id: str,
    user_id: Optional[str],
    connection_id: str,
    targets: Sequence[QueryTarget],
    fallback_schema_name: Optional[str] = None,
    columns: Optional[Sequence[str]] = None,
    apply_grants: bool = True,
    require_catalogued: bool = True,
    case_sensitive: bool = False,
) -> bool:
    """Can ``user_id`` read every table (and column) in ``targets``?

    ``columns`` is the set of column names the query touches anywhere —
    projection, filter, join key. ``None`` means the projection could
    not be determined (``SELECT *``, a whole-row reference, a document
    pipeline), in which case EVERY catalogued column of every target
    must be readable. Names are matched against every target carrying
    them; a qualifier-blind match over-requires when two joined tables
    share a column name, which is the safe direction.

    ``apply_grants=False`` is the role bypass: Tenant Owner / Tenant
    Admin / Workspace Admin skip the grant walk, but M10 still applies
    to them — the Manage Access UI promises admins that PII / Restricted
    flags block at query time.

    ``require_catalogued=False`` lets a name with no catalog row pass —
    there are no flags to apply to it. Only meaningful for the admin
    bypass; a member reading an uncatalogued table is a refusal.

    ``case_sensitive=True`` matches names exactly. Document stores need
    it: ``Salaries`` and ``salaries`` are different collections. SQL
    callers fold, because unquoted identifiers fold and the catalog
    stores what the source reported — and a folded name that matches
    more than one catalog row is refused rather than guessed.
    """
    if not targets:
        return False
    if apply_grants and not user_id:
        return False

    require_every_column = columns is None
    wanted = {c.strip().lower() for c in (columns or ()) if c and c.strip()}

    pairs: set[tuple[str, str]] = set()
    for target in targets:
        schema_name = target.schema_name or fallback_schema_name
        if not schema_name or not target.table_name:
            return False
        pairs.add(
            (
                _fold(schema_name, case_sensitive),
                _fold(target.table_name, case_sensitive),
            )
        )

    # 1) The catalog rows for those names, scoped to this connection —
    #    schema names are not unique across connections.
    if case_sensitive:
        schema_key = DACatalogSchema.schema_name
        table_key = DACatalogTable.table_name
    else:
        schema_key = func.lower(DACatalogSchema.schema_name)
        table_key = func.lower(DACatalogTable.table_name)
    rows = (
        await session.execute(
            select(
                DACatalogTable.id,
                DACatalogTable.is_pii,
                DACatalogTable.is_restricted,
                DACatalogSchema.id.label("schema_id"),
                DACatalogSchema.is_pii.label("schema_is_pii"),
                DACatalogSchema.is_restricted.label("schema_is_restricted"),
                schema_key.label("schema_key"),
                table_key.label("table_key"),
            )
            .join(
                DACatalogSchema,
                DACatalogSchema.id == DACatalogTable.da_catalog_schema_id,
            )
            .where(
                DACatalogSchema.da_connection_id == str(connection_id),
                schema_key.in_({s for s, _ in pairs}),
                table_key.in_({t for _, t in pairs}),
            )
        )
    ).all()
    matched: dict[tuple[str, str], Any] = {}
    for r in rows:
        key = (r.schema_key, r.table_key)
        if key not in pairs:
            continue
        if key in matched:
            # Two catalog rows fold to one name ("Orders" and "orders").
            # Which one the datasource reads depends on quoting the
            # check cannot see, so neither is authorized.
            return False
        matched[key] = r
    if require_catalogued and len(matched) != len(pairs):
        return False
    if not matched:
        return True

    table_ids = [str(r.id) for r in matched.values()]
    schema_ids = {str(r.schema_id) for r in matched.values()}

    # 2) Their columns, with the workspace's restriction escalation.
    column_rows = (
        await session.execute(
            select(
                DACatalogColumn.id,
                DACatalogColumn.da_catalog_table_id,
                DACatalogColumn.column_name,
                DACatalogColumn.is_pii,
                DACatalogColumn.is_restricted,
                WorkspaceCurationDAColumn.is_restricted_override,
            )
            .outerjoin(
                WorkspaceCurationDAColumn,
                (WorkspaceCurationDAColumn.da_catalog_column_id == DACatalogColumn.id)
                & (WorkspaceCurationDAColumn.workspace_id == str(workspace_id)),
            )
            .where(DACatalogColumn.da_catalog_table_id.in_(table_ids))
        )
    ).all()
    columns_by_table: dict[str, list[Any]] = {}
    for row in column_rows:
        columns_by_table.setdefault(str(row.da_catalog_table_id), []).append(row)

    # 3) This user's grants on any resource in play, and the
    #    inherit-from-membership default — only when grants apply.
    grants: dict[tuple[str, str], str] = {}
    member_default = True
    if apply_grants:
        resource_ids = (
            list(schema_ids) + table_ids + [str(r.id) for r in column_rows]
        )
        grant_rows = (
            await session.execute(
                select(
                    WorkspaceDAAccessGrant.resource_type,
                    WorkspaceDAAccessGrant.resource_id,
                    WorkspaceDAAccessGrant.effect,
                ).where(
                    WorkspaceDAAccessGrant.workspace_id == str(workspace_id),
                    WorkspaceDAAccessGrant.user_id == str(user_id),
                    WorkspaceDAAccessGrant.resource_id.in_(resource_ids),
                )
            )
        ).all()
        # resource_type / effect come back as raw VARCHAR.
        grants = {
            (g.resource_type, str(g.resource_id)): g.effect for g in grant_rows
        }
        member_default = await is_workspace_member(
            session, workspace_id=str(workspace_id), user_id=str(user_id)
        )

    col_t = DAAccessResourceTypeEnum.COLUMN.value
    tbl_t = DAAccessResourceTypeEnum.TABLE.value
    sch_t = DAAccessResourceTypeEnum.SCHEMA.value

    for row in matched.values():
        table_id = str(row.id)
        table_chain = [(tbl_t, table_id), (sch_t, str(row.schema_id))]
        if (
            bool(row.is_pii)
            or bool(row.is_restricted)
            or bool(row.schema_is_pii)
            or bool(row.schema_is_restricted)
        ):
            return False
        if apply_grants and not walk_grants(
            grants, chain=table_chain, member_default=member_default
        ):
            return False

        table_columns = columns_by_table.get(table_id, [])
        if require_every_column and not table_columns:
            # Nothing to check is not the same as nothing to hide.
            return False

        for column in table_columns:
            if (
                not require_every_column
                and str(column.column_name).lower() not in wanted
            ):
                continue
            if (
                bool(column.is_pii)
                or bool(column.is_restricted)
                or bool(column.is_restricted_override)
            ):
                return False
            if apply_grants and not walk_grants(
                grants,
                chain=[(col_t, str(column.id))] + table_chain,
                member_default=member_default,
            ):
                return False

    return True
