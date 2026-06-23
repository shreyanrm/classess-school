-- =============================================================================
-- 0004_events.sql
-- The immutable, append-only, partitioned behavioral event store.
--
-- INVARIANTS:
--   - Append-only + immutable: a BEFORE UPDATE/DELETE trigger raises an
--     exception on every row. Events are never mutated or deleted in place.
--   - Opaque reference ONLY: canonical_uuid is the random pii_vault key; NO PII
--     is stored, and there is NO SQL FK to the pii_vault (segregation rule).
--   - Every event is attributed: app . canonical_uuid . type . purpose .
--     consent_ref. consent_ref points at the platform.consents row in force
--     at emit time (logical reference, no cross-boundary FK needed since both
--     live in `platform`; kept as a soft reference to preserve append-only
--     semantics even if a consent is later revoked).
--   - Partitioned by occurred_at (monthly RANGE) for retention + performance.
--
-- Idempotent.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Immutability guard (shared by events and audit). Defined in `platform`.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION platform.deny_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION
    'append-only store: % is not permitted on %.%',
    TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME
    USING ERRCODE = 'restrict_violation';
END;
$$;
COMMENT ON FUNCTION platform.deny_mutation() IS
  'Trigger fn enforcing append-only/immutable semantics. RAISES on UPDATE/DELETE.';

-- ---------------------------------------------------------------------------
-- Parent partitioned table.
-- Note: a partition key column (occurred_at) must be part of the PRIMARY KEY
-- for native range partitioning, so the PK is (event_id, occurred_at).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS platform.events (
  event_id        uuid        NOT NULL DEFAULT gen_random_uuid(),

  -- Opaque identity reference ONLY. No FK to the pii_vault. No PII anywhere here.
  canonical_uuid  uuid        NOT NULL,

  app             text        NOT NULL,            -- emitting app, e.g. 'school'
  type            text        NOT NULL,            -- event type, e.g. 'attempt.submitted'
  purpose         text        NOT NULL,            -- purpose the data serves

  -- Consent in force at emit time. Soft reference (no FK) to keep events
  -- immutable even after the consent is revoked or its row removed.
  consent_ref     uuid,

  payload         jsonb       NOT NULL DEFAULT '{}'::jsonb,

  occurred_at     timestamptz NOT NULL,            -- domain time (partition key)
  recorded_at     timestamptz NOT NULL DEFAULT now(),  -- ingest time
  schema_version  integer     NOT NULL DEFAULT 1,

  CONSTRAINT events_payload_is_object CHECK (jsonb_typeof(payload) = 'object'),
  PRIMARY KEY (event_id, occurred_at)
) PARTITION BY RANGE (occurred_at);

COMMENT ON TABLE platform.events IS
  'Immutable, append-only, monthly-range-partitioned behavioral event store. '
  'Opaque canonical_uuid only, NO PII, NO SQL FK to the pii_vault. Attributed by '
  'app/type/purpose/consent_ref. Read only through platform.read_events().';
COMMENT ON COLUMN platform.events.canonical_uuid IS
  'Opaque identity reference. Logical link to pii_vault.users; deliberately no FK.';
COMMENT ON COLUMN platform.events.consent_ref IS
  'platform.consents.consent_id in force at emit time (soft ref; no FK to keep '
  'events immutable after revocation).';
COMMENT ON COLUMN platform.events.occurred_at IS
  'Domain timestamp; the monthly RANGE partition key.';
COMMENT ON COLUMN platform.events.recorded_at IS 'Ingest timestamp.';

-- Read index for the governed view: per-person, per-type, time-ordered.
CREATE INDEX IF NOT EXISTS events_uuid_type_time_idx
  ON platform.events (canonical_uuid, type, occurred_at);

-- ---------------------------------------------------------------------------
-- Immutability triggers on the PARENT. Row triggers on a partitioned parent
-- propagate to all partitions (existing and future), so this covers them all.
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS events_no_update ON platform.events;
CREATE TRIGGER events_no_update
  BEFORE UPDATE ON platform.events
  FOR EACH ROW EXECUTE FUNCTION platform.deny_mutation();

DROP TRIGGER IF EXISTS events_no_delete ON platform.events;
CREATE TRIGGER events_no_delete
  BEFORE DELETE ON platform.events
  FOR EACH ROW EXECUTE FUNCTION platform.deny_mutation();

-- ---------------------------------------------------------------------------
-- Partitions.
--
-- HOW TO ADD A MONTHLY PARTITION (do this ahead of each month, e.g. via cron):
--   CREATE TABLE IF NOT EXISTS platform.events_yYYYYmMM
--     PARTITION OF platform.events
--     FOR VALUES FROM ('YYYY-MM-01 00:00:00+00') TO ('YYYY-MM+1-01 00:00:00+00');
-- Example for 2026-07:
--   CREATE TABLE IF NOT EXISTS platform.events_y2026m07
--     PARTITION OF platform.events
--     FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');
--
-- A DEFAULT partition catches any row whose occurred_at has no explicit
-- monthly partition, so inserts never fail for a missing partition. Rows can
-- be migrated out of DEFAULT later when the proper monthly partition is added.
-- ---------------------------------------------------------------------------

-- Current-month partition (build month: 2026-06).
CREATE TABLE IF NOT EXISTS platform.events_y2026m06
  PARTITION OF platform.events
  FOR VALUES FROM ('2026-06-01 00:00:00+00') TO ('2026-07-01 00:00:00+00');

-- Next-month partition (2026-07), so ingest does not depend on cron landing.
CREATE TABLE IF NOT EXISTS platform.events_y2026m07
  PARTITION OF platform.events
  FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-08-01 00:00:00+00');

-- Safety net: catch-all DEFAULT partition.
CREATE TABLE IF NOT EXISTS platform.events_default
  PARTITION OF platform.events DEFAULT;

COMMENT ON TABLE platform.events_default IS
  'Catch-all partition for occurred_at values with no dedicated monthly '
  'partition. Monitor and migrate rows into proper monthly partitions.';
