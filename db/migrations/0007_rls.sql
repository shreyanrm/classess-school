-- =============================================================================
-- 0007_rls.sql
-- Row Level Security: restrictive, default-deny across vault, platform, audit.
--
-- POSTURE:
--   - RLS is ENABLED and FORCED on every base table. With RLS on and no
--     permissive policy, the default is DENY for non-owner roles.
--   - We add NO permissive policies for application/anon/authenticated roles.
--     Direct table access from those roles is therefore denied. All legitimate
--     access is mediated by the GATEWAY running as the Supabase service role
--     (which bypasses RLS by design) and is subject to RBAC + ABAC at the wall,
--     plus the purpose gate in platform.read_events().
--   - The pii_vault schema is the most restricted: not only RLS-denied, but its
--     table privileges are revoked from anon/authenticated entirely.
--
-- This migration is intentionally conservative: it locks everything down. If a
-- future, carefully-reviewed direct-access path is needed, it is added as an
-- explicit named policy here -- never by relaxing the default.
--
-- Idempotent.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- VAULT (most restricted)
-- ---------------------------------------------------------------------------
ALTER TABLE pii_vault.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE pii_vault.users FORCE ROW LEVEL SECURITY;

-- Defense in depth: strip table privileges from the client-facing roles so
-- the pii_vault is unreachable even if RLS were ever misconfigured. Guarded so the
-- migration does not fail if a role is absent on a given environment.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    REVOKE ALL ON ALL TABLES IN SCHEMA pii_vault FROM anon;
    REVOKE USAGE ON SCHEMA pii_vault FROM anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE ALL ON ALL TABLES IN SCHEMA pii_vault FROM authenticated;
    REVOKE USAGE ON SCHEMA pii_vault FROM authenticated;
  END IF;
END;
$$;

-- Explicit deny-all policy (no USING clause that is ever true). Documents the
-- default-deny intent at the policy level.
DROP POLICY IF EXISTS pii_vault_users_deny_all ON pii_vault.users;
CREATE POLICY pii_vault_users_deny_all
  ON pii_vault.users
  AS RESTRICTIVE
  FOR ALL
  USING (false)
  WITH CHECK (false);

COMMENT ON POLICY pii_vault_users_deny_all ON pii_vault.users IS
  'Default-deny. Vault access is mediated only by the gateway/identity service '
  'as the service role; no direct anon/authenticated access. Most restricted schema.';

-- ---------------------------------------------------------------------------
-- PLATFORM (behavioral plane)
-- ---------------------------------------------------------------------------
ALTER TABLE platform.app_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.app_memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.consents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.consents        FORCE ROW LEVEL SECURITY;
ALTER TABLE platform.events          ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.events          FORCE ROW LEVEL SECURITY;

-- RLS on a partitioned parent applies to all partitions; no per-partition setup.

DROP POLICY IF EXISTS app_memberships_deny_all ON platform.app_memberships;
CREATE POLICY app_memberships_deny_all
  ON platform.app_memberships AS RESTRICTIVE FOR ALL
  USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS consents_deny_all ON platform.consents;
CREATE POLICY consents_deny_all
  ON platform.consents AS RESTRICTIVE FOR ALL
  USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS events_deny_all ON platform.events;
CREATE POLICY events_deny_all
  ON platform.events AS RESTRICTIVE FOR ALL
  USING (false) WITH CHECK (false);

COMMENT ON POLICY events_deny_all ON platform.events IS
  'Default-deny. Reads go through platform.read_events() (consent+purpose gate); '
  'writes go through the gateway as the service role. No direct client access.';

-- ---------------------------------------------------------------------------
-- AUDIT (immutable; read mediated by governance tooling via service role)
-- ---------------------------------------------------------------------------
ALTER TABLE audit.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit.audit_log FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_log_deny_all ON audit.audit_log;
CREATE POLICY audit_log_deny_all
  ON audit.audit_log AS RESTRICTIVE FOR ALL
  USING (false) WITH CHECK (false);

COMMENT ON POLICY audit_log_deny_all ON audit.audit_log IS
  'Default-deny. Audit append/read mediated by governance tooling as the '
  'service role; immutability separately enforced by trigger.';
