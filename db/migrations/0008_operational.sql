-- =============================================================================
-- 0008_operational.sql
-- The OPERATIONAL schema: per-capability behavioral/operational tables the
-- surfaces persist real data into. Institution + hierarchy + roster + policy.
--
-- SECURITY MODEL (structural — same posture as 0001..0007):
--   operational -> per-capability behavioral / operational store. Carries ONLY
--                  opaque canonical_uuid references and structural data. NEVER
--                  any PII (PII stays in pii_vault). Separate from platform
--                  (the canonical event store), pii_vault, and audit.
--
-- RULES honoured by every table in this and the sibling 00NN_operational_*
-- migrations:
--   - uuid PK (gen_random_uuid()).
--   - a tenant/institution scope column (institution_id) on every table —
--     logical multi-tenancy (INVARIANT 10). Logical reference by id; no FK into
--     pii_vault, ever.
--   - created_at / updated_at on every table.
--   - indexes for the obvious lookups (tenant scope + the natural foreign key).
--   - person references are the opaque canonical_uuid only — never PII, and
--     deliberately NO SQL FK to pii_vault (severing identity must not cascade).
--   - RLS is ENABLED + FORCED with a default-deny posture in
--     0011_operational_rls.sql; all legitimate access is mediated by the gateway
--     running as the Supabase service role (which bypasses RLS by design).
--
-- Idempotent: IF NOT EXISTS throughout; safe to re-run.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Schema. Behavioral/operational plane, opaque refs only, never PII.
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS operational;
COMMENT ON SCHEMA operational IS
  'Per-capability behavioral / operational store (institution, ontology, '
  'content, attendance, coursework, messaging, learner record, timetable). '
  'Rows are keyed by opaque canonical_uuid references and structural ids and '
  'carry NO PII. Modules own their own tables and never share tables (they '
  'share only events). Access is mediated by the gateway as the service role; '
  'RLS is default-deny (see 0011_operational_rls.sql).';

-- ---------------------------------------------------------------------------
-- Shared updated_at trigger fn. Keeps updated_at honest without app coupling.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION operational.touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;
COMMENT ON FUNCTION operational.touch_updated_at() IS
  'BEFORE UPDATE trigger fn: stamps updated_at = now() on every row update.';

-- ===========================================================================
-- INSTITUTION + HIERARCHY (module: institution, B1)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- institutions: the tenant root. institution_id IS the opaque tenant scope
-- (INVARIANT 10) — random, never derived from a name. Every other operational
-- row carries this id. No PII: an institution is a structural unit.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.institutions (
  institution_id  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Generic, institution-supplied display label (data, never a board lock-in).
  label           text        NOT NULL,
  -- Optional stable short handle the institution chooses. Not identifying.
  handle          text,

  -- Free-form structural attributes (e.g. board-agnostic affiliation codes,
  -- medium of instruction). NEVER PII.
  attributes      jsonb       NOT NULL DEFAULT '{}'::jsonb,

  status          text        NOT NULL DEFAULT 'active',  -- active | suspended | archived

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT institutions_attributes_is_object
    CHECK (jsonb_typeof(attributes) = 'object'),
  CONSTRAINT institutions_status_chk
    CHECK (status IN ('active', 'suspended', 'archived'))
);
COMMENT ON TABLE operational.institutions IS
  'Tenant root. institution_id is the opaque tenant scope (INVARIANT 10), '
  'random and never derived from a name. No PII; an institution is structural.';

CREATE INDEX IF NOT EXISTS institutions_status_idx
  ON operational.institutions (status);

DROP TRIGGER IF EXISTS institutions_touch ON operational.institutions;
CREATE TRIGGER institutions_touch
  BEFORE UPDATE ON operational.institutions
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- structure_nodes: the configurable containment tree, board-agnostic.
-- Ladder (coarsest -> finest): group -> region -> campus -> school ->
-- department -> grade -> section. Self-referential parent_id (one structural
-- parent per node). `kind` is a canonical rung; `label` is the institution's
-- own display name (data). No PII — a node is a place, not a person.
-- (mirrors modules/institution/app/hierarchy.py Node)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.structure_nodes (
  node_id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid        NOT NULL,    -- tenant scope (INVARIANT 10)

  kind            text        NOT NULL,    -- canonical ladder rung (see CHECK)
  label           text        NOT NULL,    -- institution display name (data)

  -- Single structural parent; NULL for the root. Same-tenant by construction.
  parent_id       uuid        REFERENCES operational.structure_nodes(node_id)
                              ON DELETE RESTRICT,

  -- Free-form structural attributes (capacity, medium of instruction, ...).
  attributes      jsonb       NOT NULL DEFAULT '{}'::jsonb,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT structure_nodes_kind_chk
    CHECK (kind IN ('group','region','campus','school','department','grade','section')),
  CONSTRAINT structure_nodes_attributes_is_object
    CHECK (jsonb_typeof(attributes) = 'object'),
  CONSTRAINT structure_nodes_not_self_parent
    CHECK (parent_id IS NULL OR parent_id <> node_id)
);
COMMENT ON TABLE operational.structure_nodes IS
  'Configurable containment tree (group->region->campus->school->department->'
  'grade->section). parent_id is the single structural parent (self-ref). No PII.';
COMMENT ON COLUMN operational.structure_nodes.kind IS
  'Canonical, board-agnostic ladder rung. A parent must out-rank its child '
  '(enforced in app logic; the ladder order is fixed by the CHECK domain).';

CREATE INDEX IF NOT EXISTS structure_nodes_tenant_idx
  ON operational.structure_nodes (institution_id);
CREATE INDEX IF NOT EXISTS structure_nodes_parent_idx
  ON operational.structure_nodes (parent_id);
CREATE INDEX IF NOT EXISTS structure_nodes_tenant_kind_idx
  ON operational.structure_nodes (institution_id, kind);

DROP TRIGGER IF EXISTS structure_nodes_touch ON operational.structure_nodes;
CREATE TRIGGER structure_nodes_touch
  BEFORE UPDATE ON operational.structure_nodes
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- structure_relationships: the many-to-many, SCOPED, TIME-BOUND relationship
-- graph (NOT containment) — shared_department, combined_section, feeder,
-- coordination, affiliation. valid_from inclusive, valid_to exclusive/NULL.
-- Both endpoints are in the same tenant (a relationship never spans tenants).
-- (mirrors modules/institution/app/hierarchy.py Relationship)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.structure_relationships (
  relationship_id uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid        NOT NULL,    -- tenant scope (INVARIANT 10)

  kind            text        NOT NULL,    -- see CHECK
  source_id       uuid        NOT NULL REFERENCES operational.structure_nodes(node_id)
                              ON DELETE CASCADE,
  target_id       uuid        NOT NULL REFERENCES operational.structure_nodes(node_id)
                              ON DELETE CASCADE,

  valid_from      date        NOT NULL,
  valid_to        date,                    -- NULL => open-ended (exclusive bound)

  attributes      jsonb       NOT NULL DEFAULT '{}'::jsonb,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT structure_relationships_kind_chk
    CHECK (kind IN ('shared_department','combined_section','feeder','coordination','affiliation')),
  CONSTRAINT structure_relationships_distinct
    CHECK (source_id <> target_id),
  CONSTRAINT structure_relationships_window
    CHECK (valid_to IS NULL OR valid_to > valid_from),
  CONSTRAINT structure_relationships_attributes_is_object
    CHECK (jsonb_typeof(attributes) = 'object')
);
COMMENT ON TABLE operational.structure_relationships IS
  'Scoped, time-bound many-to-many edges between structure_nodes (NOT '
  'containment). valid_from inclusive, valid_to exclusive/NULL. Same-tenant only.';

CREATE INDEX IF NOT EXISTS structure_relationships_tenant_idx
  ON operational.structure_relationships (institution_id);
CREATE INDEX IF NOT EXISTS structure_relationships_source_idx
  ON operational.structure_relationships (source_id, kind);
CREATE INDEX IF NOT EXISTS structure_relationships_target_idx
  ON operational.structure_relationships (target_id, kind);

DROP TRIGGER IF EXISTS structure_relationships_touch ON operational.structure_relationships;
CREATE TRIGGER structure_relationships_touch
  BEFORE UPDATE ON operational.structure_relationships
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- memberships (roster): person (opaque canonical_uuid) x structure node x role,
-- time-bound. The roster of who sits where in which role. Opaque ref ONLY —
-- never PII, deliberately no FK to pii_vault.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.memberships (
  membership_id   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid        NOT NULL,    -- tenant scope (INVARIANT 10)

  -- Opaque identity reference ONLY. No FK to the pii_vault (segregation rule).
  canonical_uuid  uuid        NOT NULL,

  -- Where the person sits in the org tree (section, grade, department, ...).
  node_id         uuid        REFERENCES operational.structure_nodes(node_id)
                              ON DELETE SET NULL,

  role            text        NOT NULL,    -- admin | teacher | student | parent | staff

  -- Time-bound roster window; valid_to NULL => currently active.
  valid_from      date        NOT NULL DEFAULT CURRENT_DATE,
  valid_to        date,

  -- Structural attributes (e.g. subject taught, guardian-of refs). Never PII.
  attributes      jsonb       NOT NULL DEFAULT '{}'::jsonb,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT memberships_role_chk
    CHECK (role IN ('admin','teacher','student','parent','staff')),
  CONSTRAINT memberships_window
    CHECK (valid_to IS NULL OR valid_to > valid_from),
  CONSTRAINT memberships_attributes_is_object
    CHECK (jsonb_typeof(attributes) = 'object')
);
COMMENT ON TABLE operational.memberships IS
  'Roster: opaque canonical_uuid x structure node x role, time-bound. Opaque '
  'person ref ONLY, NO PII, NO SQL FK to the pii_vault. valid_to NULL = active.';
COMMENT ON COLUMN operational.memberships.canonical_uuid IS
  'Opaque identity reference. Logical link to pii_vault.users; deliberately no FK.';

CREATE INDEX IF NOT EXISTS memberships_tenant_idx
  ON operational.memberships (institution_id);
CREATE INDEX IF NOT EXISTS memberships_person_idx
  ON operational.memberships (canonical_uuid);
CREATE INDEX IF NOT EXISTS memberships_node_role_idx
  ON operational.memberships (node_id, role);
-- One active (non-expired) membership per (person, node, role).
CREATE UNIQUE INDEX IF NOT EXISTS memberships_active_uidx
  ON operational.memberships (institution_id, canonical_uuid, node_id, role)
  WHERE valid_to IS NULL;

DROP TRIGGER IF EXISTS memberships_touch ON operational.memberships;
CREATE TRIGGER memberships_touch
  BEFORE UPDATE ON operational.memberships
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- policies: named, typed settings set at a node and INHERITED down the tree.
-- `locked` seals a value descendants may not override. Hyperlocalisation is
-- just policy with three well-known keys: locale.language / locale.region /
-- locale.calendar. Resolution (nearest-setter, highest-lock-wins) lives in app
-- logic; this table is the store of set values with provenance.
-- (mirrors modules/institution/app/policy.py PolicyValue)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.policies (
  policy_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid        NOT NULL,    -- tenant scope (INVARIANT 10)

  -- The node this policy value is SET ON (it inherits down to descendants).
  node_id         uuid        NOT NULL REFERENCES operational.structure_nodes(node_id)
                              ON DELETE CASCADE,

  -- Policy key, e.g. 'grading.scheme', 'attendance.threshold', and the three
  -- well-known hyperlocalisation keys: 'locale.language' | 'locale.region' |
  -- 'locale.calendar'. A config key, never a value lock-in.
  key             text        NOT NULL,
  -- Typed value as jsonb so any policy shape (string/number/object) fits.
  value           jsonb       NOT NULL,
  -- A locked value is the floor a higher node sets that descendants may not
  -- override (e.g. a child-safety / data-retention minimum).
  locked          boolean     NOT NULL DEFAULT false,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE operational.policies IS
  'Policy values set at a node and inherited down the containment tree. '
  'Hyperlocalisation = policy with keys locale.language/region/calendar. '
  'locked seals a value descendants may not override. No PII.';

-- One value per (node, key): a node sets a key at most once.
CREATE UNIQUE INDEX IF NOT EXISTS policies_node_key_uidx
  ON operational.policies (node_id, key);
CREATE INDEX IF NOT EXISTS policies_tenant_key_idx
  ON operational.policies (institution_id, key);

DROP TRIGGER IF EXISTS policies_touch ON operational.policies;
CREATE TRIGGER policies_touch
  BEFORE UPDATE ON operational.policies
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();
