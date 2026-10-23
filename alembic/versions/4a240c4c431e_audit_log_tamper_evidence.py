"""audit_log tamper evidence: TRUNCATE blocked + per-tenant hash chain (G-19).

* BEFORE TRUNCATE statement trigger raises AU001. UPDATE/DELETE were already
  blocked by audit_log_immutability (only the actor ON DELETE SET NULL passes).
* chain_seq / prev_hash / row_hash, filled by a BEFORE INSERT trigger. One chain
  per tenant, extended under a per-tenant advisory xact lock. actor_user_id is
  left out of the hash so the allowed SET NULL keeps the chain valid.
* audit_log_verify_chain(tenant_id) returns the first broken row, or NULL.

Existing rows are chained in (tenant_id, occurred_at, id) order, one UPDATE per
row under an ACCESS EXCLUSIVE lock: audit inserts wait for the whole backfill.

Break-glass (superuser only): SET LOCAL session_replication_role = replica.

Revision ID: 4a240c4c431e
Revises: e1b5a7c9d3f6
Create Date: 2026-10-22
"""
from alembic import op

revision = "4a240c4c431e"
down_revision = "e1b5a7c9d3f6"
branch_labels = None
depends_on = None

_ROW_HASH = """
CREATE OR REPLACE FUNCTION audit_log_row_hash(r audit_log) RETURNS text AS $func$
    SELECT encode(sha256(convert_to(concat_ws('|',
        quote_nullable(r.prev_hash), r.chain_seq, r.id, r.tenant_id,
        quote_nullable(r.event_type), quote_nullable(r.resource_type),
        quote_nullable(r.resource_id), quote_nullable(r.event_metadata::text),
        quote_nullable(r.ip_address::text), quote_nullable(r.user_agent),
        to_char(r.occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US')
    ), 'UTF8')), 'hex')
$func$ LANGUAGE sql STABLE
"""

_CHAIN = """
CREATE OR REPLACE FUNCTION audit_log_chain() RETURNS trigger AS $func$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('audit_log_chain'), hashtext(NEW.tenant_id::text));
    SELECT a.chain_seq + 1, a.row_hash INTO NEW.chain_seq, NEW.prev_hash
      FROM audit_log a WHERE a.tenant_id = NEW.tenant_id
     ORDER BY a.chain_seq DESC LIMIT 1;
    IF NOT FOUND THEN
        NEW.chain_seq := 1;
        NEW.prev_hash := NULL;
    END IF;
    NEW.row_hash := audit_log_row_hash(NEW);
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql
"""

_BLOCK_TRUNCATE = """
CREATE OR REPLACE FUNCTION audit_log_block_truncate() RETURNS trigger AS $func$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only; TRUNCATE blocked'
        USING ERRCODE = 'AU001';
END;
$func$ LANGUAGE plpgsql
"""

_VERIFY = """
CREATE OR REPLACE FUNCTION audit_log_verify_chain(p_tenant_id uuid) RETURNS uuid AS $func$
    SELECT c.id FROM (
        SELECT a.id, a.chain_seq, a.prev_hash, a.row_hash,
               audit_log_row_hash(a) AS expected_hash,
               lag(a.row_hash) OVER w AS previous_row_hash,
               row_number() OVER w AS n
          FROM audit_log a WHERE a.tenant_id = p_tenant_id
        WINDOW w AS (ORDER BY a.chain_seq)
    ) c
    WHERE c.row_hash IS DISTINCT FROM c.expected_hash
       OR c.prev_hash IS DISTINCT FROM c.previous_row_hash
       OR c.chain_seq <> c.n
    ORDER BY c.chain_seq LIMIT 1
$func$ LANGUAGE sql STABLE
"""

_BACKFILL = """
DO $$
DECLARE
    r audit_log;
    cur_tenant uuid;
    prev text;
    seq bigint;
BEGIN
    FOR r IN SELECT * FROM audit_log ORDER BY tenant_id, occurred_at, id LOOP
        IF cur_tenant IS DISTINCT FROM r.tenant_id THEN
            cur_tenant := r.tenant_id;
            prev := NULL;
            seq := 0;
        END IF;
        seq := seq + 1;
        r.chain_seq := seq;
        r.prev_hash := prev;
        prev := audit_log_row_hash(r);
        UPDATE audit_log SET chain_seq = r.chain_seq, prev_hash = r.prev_hash, row_hash = prev
         WHERE id = r.id;
    END LOOP;
END $$
"""


def upgrade() -> None:
    op.execute("ALTER TABLE audit_log ADD COLUMN chain_seq bigint")
    op.execute("ALTER TABLE audit_log ADD COLUMN prev_hash text")
    op.execute("ALTER TABLE audit_log ADD COLUMN row_hash text")
    op.execute(_ROW_HASH)

    op.execute("ALTER TABLE audit_log DISABLE TRIGGER audit_log_immutability")
    op.execute(_BACKFILL)
    op.execute("ALTER TABLE audit_log ENABLE TRIGGER audit_log_immutability")

    op.execute("ALTER TABLE audit_log ALTER COLUMN chain_seq SET NOT NULL")
    op.execute("ALTER TABLE audit_log ALTER COLUMN row_hash SET NOT NULL")
    op.execute(
        "CREATE UNIQUE INDEX ux_audit_log_tenant_chain_seq "
        "ON audit_log (tenant_id, chain_seq)"
    )

    op.execute(_CHAIN)
    op.execute(
        "CREATE TRIGGER audit_log_chain BEFORE INSERT ON audit_log "
        "FOR EACH ROW EXECUTE FUNCTION audit_log_chain()"
    )
    op.execute(_BLOCK_TRUNCATE)
    op.execute(
        "CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_log_block_truncate()"
    )
    op.execute(_VERIFY)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS audit_log_verify_chain(uuid)")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_truncate ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_block_truncate()")
    op.execute("DROP TRIGGER IF EXISTS audit_log_chain ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_chain()")
    op.execute("DROP FUNCTION IF EXISTS audit_log_row_hash(audit_log)")
    op.execute("DROP INDEX IF EXISTS ux_audit_log_tenant_chain_seq")
    op.execute("ALTER TABLE audit_log DROP COLUMN IF EXISTS row_hash")
    op.execute("ALTER TABLE audit_log DROP COLUMN IF EXISTS prev_hash")
    op.execute("ALTER TABLE audit_log DROP COLUMN IF EXISTS chain_seq")
