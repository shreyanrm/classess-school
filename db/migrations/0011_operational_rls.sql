-- =============================================================================
-- 0011_operational_rls.sql
-- Row Level Security (default-deny) + append-only immutability for the
-- operational schema. Same posture as 0007_rls.sql for vault/platform/audit.
--
-- POSTURE:
--   - RLS is ENABLED and FORCED on every operational base table. With RLS on and
--     no permissive policy, the default is DENY for non-owner roles.
--   - We add NO permissive policies for application/anon/authenticated roles.
--     Direct table access from those roles is therefore denied. All legitimate
--     access is mediated by the GATEWAY running as the Supabase service role
--     (which bypasses RLS by design) and is subject to RBAC + ABAC at the wall,
--     plus tenant isolation (institution_id) enforced in the gateway.
--   - Each table gets an explicit RESTRICTIVE deny-all policy that documents the
--     default-deny intent at the policy level. A future, carefully-reviewed
--     direct-access path would be added as an explicit named policy here -- never
--     by relaxing the default.
--   - content_versions is additionally IMMUTABLE (append-only): a BEFORE
--     UPDATE/DELETE trigger raises, mirroring the platform.events guard. The
--     version history is never rewritten.
--
-- Idempotent.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Helper: enable + force RLS and install an explicit RESTRICTIVE deny-all
-- policy on a given operational table. Keeps this migration DRY and uniform.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  t text;
  tables text[] := ARRAY[
    -- institution / hierarchy / roster / policy (0008)
    'institutions',
    'structure_nodes',
    'structure_relationships',
    'memberships',
    'policies',
    -- ontology (0009)
    'ontology_boards',
    'ontology_grades',
    'ontology_subjects',
    'ontology_units',
    'ontology_chapters',
    'ontology_topics',
    'ontology_outcomes',
    'ontology_competencies',
    'prerequisite_edges',
    'cross_board_equivalences',
    -- capabilities (0010)
    'content_items',
    'content_versions',
    'attendance_records',
    'rubrics',
    'assignments',
    'submissions',
    'gradebook_scores',
    'channels',
    'messages',
    'tasks',
    'profile_items',
    'portfolio_items',
    'credentials',
    'calendars',
    'timetable_slots',
    'substitutions'
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    EXECUTE format('ALTER TABLE operational.%I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format('ALTER TABLE operational.%I FORCE ROW LEVEL SECURITY;', t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON operational.%I;', t || '_deny_all', t);
    EXECUTE format(
      'CREATE POLICY %I ON operational.%I AS RESTRICTIVE FOR ALL USING (false) WITH CHECK (false);',
      t || '_deny_all', t
    );
    EXECUTE format(
      'COMMENT ON POLICY %I ON operational.%I IS %L;',
      t || '_deny_all', t,
      'Default-deny. All access is mediated by the gateway as the service role '
      '(RBAC + ABAC + tenant isolation on institution_id). No direct '
      'anon/authenticated access.'
    );
  END LOOP;
END;
$$;

-- ---------------------------------------------------------------------------
-- Defense in depth: strip schema/table privileges from the client-facing roles
-- so the operational plane is unreachable even if RLS were misconfigured.
-- Guarded so the migration does not fail if a role is absent on an environment.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    REVOKE ALL ON ALL TABLES IN SCHEMA operational FROM anon;
    REVOKE USAGE ON SCHEMA operational FROM anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE ALL ON ALL TABLES IN SCHEMA operational FROM authenticated;
    REVOKE USAGE ON SCHEMA operational FROM authenticated;
  END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- Immutability for the append-only version history. Reuses platform.deny_mutation
-- (defined in 0004_events.sql) so the same append-only guarantee applies.
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS content_versions_no_update ON operational.content_versions;
CREATE TRIGGER content_versions_no_update
  BEFORE UPDATE ON operational.content_versions
  FOR EACH ROW EXECUTE FUNCTION platform.deny_mutation();

DROP TRIGGER IF EXISTS content_versions_no_delete ON operational.content_versions;
CREATE TRIGGER content_versions_no_delete
  BEFORE DELETE ON operational.content_versions
  FOR EACH ROW EXECUTE FUNCTION platform.deny_mutation();

COMMENT ON TRIGGER content_versions_no_update ON operational.content_versions IS
  'Append-only: content body versions are never mutated in place (history is '
  'never rewritten). Mirrors the platform.events immutability guard.';
