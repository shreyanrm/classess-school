-- =============================================================================
-- 0005_audit.sql
-- Immutable, append-only audit log for privileged / break-glass actions.
--
-- INVARIANTS:
--   - Append-only + immutable (same trigger pattern as platform.events).
--   - Records WHO did WHAT to WHICH target, WHEN, with structured metadata.
--   - actor / target are opaque references (canonical_uuid or service-role id /
--     resource id). No PII is written here; identifying detail stays in pii_vault.
--   - Vault reads, role grants, consent overrides, and any break-glass access
--     are expected to append a row here.
--
-- Idempotent.
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit.audit_log (
  audit_id     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Who performed the action. Opaque: a canonical_uuid or a service-role
  -- principal id. No PII.
  actor        text        NOT NULL,

  -- What was done, e.g. 'pii_vault.read','membership.grant','consent.revoke',
  -- 'breakglass.access'.
  action       text        NOT NULL,

  -- What it was done to, e.g. a canonical_uuid, table, or resource id. Opaque.
  target       text,

  occurred_at  timestamptz NOT NULL DEFAULT now(),

  -- Structured context: reason, ticket, ip-hash, policy decision, etc.
  -- Must not contain PII.
  metadata     jsonb       NOT NULL DEFAULT '{}'::jsonb,

  CONSTRAINT audit_metadata_is_object CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS audit_log_actor_time_idx
  ON audit.audit_log (actor, occurred_at);
CREATE INDEX IF NOT EXISTS audit_log_action_time_idx
  ON audit.audit_log (action, occurred_at);
CREATE INDEX IF NOT EXISTS audit_log_target_idx
  ON audit.audit_log (target);

-- ---------------------------------------------------------------------------
-- Immutability triggers. Reuse platform.deny_mutation() defined in 0004.
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS audit_log_no_update ON audit.audit_log;
CREATE TRIGGER audit_log_no_update
  BEFORE UPDATE ON audit.audit_log
  FOR EACH ROW EXECUTE FUNCTION platform.deny_mutation();

DROP TRIGGER IF EXISTS audit_log_no_delete ON audit.audit_log;
CREATE TRIGGER audit_log_no_delete
  BEFORE DELETE ON audit.audit_log
  FOR EACH ROW EXECUTE FUNCTION platform.deny_mutation();

COMMENT ON TABLE audit.audit_log IS
  'Immutable append-only audit trail for privileged / break-glass actions. '
  'No UPDATE/DELETE (trigger-enforced). Opaque actor/target only, no PII.';
COMMENT ON COLUMN audit.audit_log.actor    IS 'Opaque principal id (canonical_uuid or service role). No PII.';
COMMENT ON COLUMN audit.audit_log.action   IS 'Action verb, e.g. pii_vault.read, membership.grant, breakglass.access.';
COMMENT ON COLUMN audit.audit_log.target   IS 'Opaque target reference (canonical_uuid / resource id). No PII.';
COMMENT ON COLUMN audit.audit_log.metadata IS 'Structured context (reason, ticket, policy decision). Must not contain PII.';

-- =============================================================================
-- platform.audit_log — the GATEWAY call-audit.
--
-- Every call through the gateway wall (INV-3, INV-9) emits one row here, on both
-- allow and deny, BEFORE forwarding. This is the high-volume RBAC/ABAC decision
-- trail. Shape mirrors the gateway audit sink (spine/gateway/app/audit.py) and
-- the TS DB contract (contracts/src/db) exactly, so durable writes succeed
-- against a live database. Opaque actor only — no PII.
--
-- This is separate from audit.audit_log above (which is the lower-volume
-- privileged / break-glass trail). Both are immutable and append-only.
-- =============================================================================

CREATE TABLE IF NOT EXISTS platform.audit_log (
  audit_id             uuid        PRIMARY KEY,
  actor_canonical_uuid uuid,                          -- opaque ref; null for unauthenticated denials. No PII.
  app                  text,
  action               text        NOT NULL,          -- the routed capability / method
  decision             text        NOT NULL,          -- 'allow' | 'deny'
  resource_scope       jsonb,                         -- the ABAC scope evaluated
  reasons              jsonb       NOT NULL DEFAULT '[]'::jsonb,  -- policy reasons for the decision
  break_glass          boolean     NOT NULL DEFAULT false,
  request_id           text        NOT NULL,
  recorded_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS platform_audit_actor_time_idx
  ON platform.audit_log (actor_canonical_uuid, recorded_at);
CREATE INDEX IF NOT EXISTS platform_audit_decision_time_idx
  ON platform.audit_log (decision, recorded_at);
CREATE INDEX IF NOT EXISTS platform_audit_request_idx
  ON platform.audit_log (request_id);

-- Immutability — reuse platform.deny_mutation() from 0004.
DROP TRIGGER IF EXISTS platform_audit_log_no_update ON platform.audit_log;
CREATE TRIGGER platform_audit_log_no_update
  BEFORE UPDATE ON platform.audit_log
  FOR EACH ROW EXECUTE FUNCTION platform.deny_mutation();

DROP TRIGGER IF EXISTS platform_audit_log_no_delete ON platform.audit_log;
CREATE TRIGGER platform_audit_log_no_delete
  BEFORE DELETE ON platform.audit_log
  FOR EACH ROW EXECUTE FUNCTION platform.deny_mutation();

-- Default-deny RLS (service-role access is mediated by the gateway).
ALTER TABLE platform.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.audit_log FORCE ROW LEVEL SECURITY;

COMMENT ON TABLE platform.audit_log IS
  'Immutable append-only gateway call-audit (every RBAC/ABAC decision). '
  'No UPDATE/DELETE (trigger-enforced). Opaque actor_canonical_uuid only, no PII. '
  'Written by spine/gateway/app/audit.py PostgresAuditSink.';
