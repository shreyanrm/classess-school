-- =============================================================================
-- 0003_memberships_consent.sql
-- App memberships (User x App x Role x scope, time-bound) and consents.
--
-- INVARIANTS:
--   - These tables live in `platform` and carry ONLY the opaque canonical_uuid.
--   - canonical_uuid logically references pii_vault.users(canonical_uuid) but there
--     is DELIBERATELY NO SQL FOREIGN KEY across the vault/platform boundary.
--     A hard FK would (a) couple the segregated stores, (b) block severing
--     identity (deleting the pii_vault row), and (c) leak pii_vault existence into the
--     behavioral plane. The link is the shared opaque value only.
--   - No PII is stored here. scope is structural (apps, institutions, classes),
--     never identifying.
--
-- Idempotent.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- app_memberships: which person holds which role in which app, time-bound.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform.app_memberships (
  membership_id   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Opaque identity reference ONLY. No FK to the pii_vault (segregation rule).
  canonical_uuid  uuid        NOT NULL,

  app             text        NOT NULL,            -- e.g. 'school'
  role            text        NOT NULL,            -- e.g. 'student','teacher','guardian','admin'

  -- ABAC scope: structural attributes the gateway evaluates (institution_id,
  -- class_ids, grade, section, ...). Never identifying PII.
  scope           jsonb       NOT NULL DEFAULT '{}'::jsonb,

  granted_at      timestamptz NOT NULL DEFAULT now(),
  revoked_at      timestamptz,                     -- NULL => currently active

  CONSTRAINT app_memberships_scope_is_object
    CHECK (jsonb_typeof(scope) = 'object'),
  CONSTRAINT app_memberships_revoke_after_grant
    CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);

-- One active (non-revoked) membership per (person, app, role).
CREATE UNIQUE INDEX IF NOT EXISTS app_memberships_active_uidx
  ON platform.app_memberships (canonical_uuid, app, role)
  WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS app_memberships_lookup_idx
  ON platform.app_memberships (canonical_uuid, app);

COMMENT ON TABLE platform.app_memberships IS
  'User x App x Role x scope, time-bound. Behavioral plane: opaque canonical_uuid '
  'only, NO PII, NO SQL FK to the pii_vault. revoked_at NULL means active.';
COMMENT ON COLUMN platform.app_memberships.canonical_uuid IS
  'Opaque identity reference. Logical link to pii_vault.users; deliberately no FK.';
COMMENT ON COLUMN platform.app_memberships.scope IS
  'ABAC scope object (institution/class/grade attributes). Never PII.';

-- ---------------------------------------------------------------------------
-- consents: the consent primitive. Stamped onto events and gates every
-- cross-context read (see 0006_governed_views.sql).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform.consents (
  consent_id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Opaque identity reference ONLY. No FK to the pii_vault.
  canonical_uuid  uuid        NOT NULL,

  scope           text        NOT NULL,            -- data scope consent covers, e.g. 'learning_behavior'
  purpose         text        NOT NULL,            -- why, e.g. 'personalization','analytics','reporting'

  -- Age tier governs guardian-vs-self consent semantics (derived from dob in
  -- the pii_vault by the identity service; stored here as a non-identifying tier).
  age_tier        text        NOT NULL DEFAULT 'unknown',  -- 'child' | 'teen' | 'adult' | 'unknown'

  -- Who granted it (a canonical_uuid: self or a guardian). Opaque, no PII.
  granted_by      uuid        NOT NULL,

  granted_at      timestamptz NOT NULL DEFAULT now(),
  revoked_at      timestamptz,                     -- NULL => currently in force

  CONSTRAINT consents_age_tier_valid
    CHECK (age_tier IN ('child','teen','adult','unknown')),
  CONSTRAINT consents_revoke_after_grant
    CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);

-- One active consent per (person, scope, purpose).
CREATE UNIQUE INDEX IF NOT EXISTS consents_active_uidx
  ON platform.consents (canonical_uuid, scope, purpose)
  WHERE revoked_at IS NULL;

-- Fast satisfaction lookup used by the governed read function.
CREATE INDEX IF NOT EXISTS consents_satisfaction_idx
  ON platform.consents (canonical_uuid, purpose)
  WHERE revoked_at IS NULL;

COMMENT ON TABLE platform.consents IS
  'Consent primitive. Behavioral plane: opaque canonical_uuid only, no PII. '
  'An active (revoked_at IS NULL) row for (canonical_uuid, purpose) is what '
  'gates governed reads of platform.events and is the basis for the consent_ref '
  'stamped on emitted events.';
COMMENT ON COLUMN platform.consents.purpose IS
  'Purpose the data may be used for. Matched against the event purpose and the '
  'read purpose at the governed-view boundary.';
COMMENT ON COLUMN platform.consents.age_tier IS
  'Non-identifying age tier (child|teen|adult|unknown) derived from pii_vault dob; '
  'drives guardian-vs-self consent rules.';
COMMENT ON COLUMN platform.consents.granted_by IS
  'Opaque canonical_uuid of the grantor (self or guardian). No PII.';
