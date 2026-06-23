-- =============================================================================
-- 0002_pii_vault.sql
-- The PII pii_vault. The single point in the entire system where the opaque
-- canonical_uuid maps to an identifiable person.
--
-- INVARIANTS:
--   - canonical_uuid is OPAQUE and RANDOM (gen_random_uuid / UUID v4).
--     It is NEVER derived from phone, email, name, or any other PII.
--   - This table is physically segregated (schema `vault`) from the behavioral
--     event store (schema `platform`). No behavioral table references this one
--     with a SQL foreign key; the link is logical (the shared canonical_uuid
--     value) so that deleting a pii_vault row severs identity while de-identified
--     behavioral rows remain and are unlinkable.
--   - Encryption-at-rest is provided by the platform (Supabase / cloud KMS).
--     Column-level intent and access-logging intent are documented below; the
--     identity service is responsible for emitting an audit.audit_log entry on
--     every read of this table (break-glass / privileged access recording).
--
-- Idempotent.
-- =============================================================================

CREATE TABLE IF NOT EXISTS pii_vault.users (
  -- OPAQUE primary key. Random v4 UUID. NEVER derived from any PII field.
  canonical_uuid  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

  -- PII fields. Encryption-at-rest is enforced at the storage/KMS layer.
  -- Application-layer field encryption MAY wrap these values; this schema does
  -- not assume plaintext semantics beyond type.
  phone           text,
  full_name       text,
  dob             date,
  email           text,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Uniqueness on contact identifiers (nullable; partial to ignore NULLs).
CREATE UNIQUE INDEX IF NOT EXISTS users_phone_uidx
  ON pii_vault.users (phone) WHERE phone IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS users_email_uidx
  ON pii_vault.users (email) WHERE email IS NOT NULL;

-- keep updated_at honest
CREATE OR REPLACE FUNCTION pii_vault.touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS users_touch_updated_at ON pii_vault.users;
CREATE TRIGGER users_touch_updated_at
  BEFORE UPDATE ON pii_vault.users
  FOR EACH ROW
  EXECUTE FUNCTION pii_vault.touch_updated_at();

-- ---------------------------------------------------------------------------
-- Column / table documentation (security intent is part of the contract)
-- ---------------------------------------------------------------------------
COMMENT ON TABLE pii_vault.users IS
  'PII pii_vault. The ONLY table mapping the opaque canonical_uuid to a real person. '
  'Physically segregated from platform.* behavioral data. Encryption-at-rest via '
  'storage/KMS; every read is expected to be access-logged to audit.audit_log by '
  'the identity service. Deleting a row here severs identity; behavioral events '
  'keyed by the same canonical_uuid remain and become unlinkable.';

COMMENT ON COLUMN pii_vault.users.canonical_uuid IS
  'OPAQUE random identity key (UUID v4 via gen_random_uuid). NEVER derived from '
  'PII. This same value appears in platform.* and audit.* as an opaque reference '
  'only -- those stores hold no PII.';
COMMENT ON COLUMN pii_vault.users.phone     IS 'PII. Encrypted at rest. Access-logged.';
COMMENT ON COLUMN pii_vault.users.full_name IS 'PII. Encrypted at rest. Access-logged.';
COMMENT ON COLUMN pii_vault.users.dob       IS 'PII. Encrypted at rest. Access-logged. Drives age-tier derivation for consent.';
COMMENT ON COLUMN pii_vault.users.email     IS 'PII. Encrypted at rest. Access-logged.';
COMMENT ON COLUMN pii_vault.users.created_at IS 'Vault row creation timestamp.';
COMMENT ON COLUMN pii_vault.users.updated_at IS 'Last mutation timestamp (maintained by trigger).';
