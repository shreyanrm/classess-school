-- =============================================================================
-- 0001_extensions.sql
-- Classess School - Ring 0 canonical/platform substrate
-- Purpose: enable required Postgres extensions and create the three top-level
--          schemas that encode the security model at the structural level.
--
-- SECURITY MODEL (structural):
--   pii_vault    -> restricted PII store. The ONLY place canonical_uuid maps to a
--               person. Physically segregated from behavioral data.
--   platform -> behavioral / canonical store. Carries ONLY the opaque
--               canonical_uuid plus behavioral data. NEVER any PII.
--   audit    -> immutable append-only record of privileged / break-glass actions.
--
-- Idempotent: safe to run on a fresh project or re-run.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------

-- pgcrypto: provides gen_random_uuid() used as the OPAQUE canonical_uuid.
-- The UUID is random (v4) and is NEVER derived from PII.
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

-- pgvector: prerequisite/ontology graph + feature embeddings (Ring 1+).
-- Enabled now so projection migrations need no extension change later.
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

-- btree_gist: composite exclusion/range support; useful for partitioned
-- range constraints and time-bound membership/consent integrity checks.
CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;

-- ---------------------------------------------------------------------------
-- Schemas
-- ---------------------------------------------------------------------------

-- vault: restricted PII. Most-locked schema in the system. Access is mediated
-- exclusively by the gateway / identity service running as the service role.
CREATE SCHEMA IF NOT EXISTS pii_vault;
COMMENT ON SCHEMA pii_vault IS
  'Restricted PII pii_vault. The ONLY place canonical_uuid maps to a real person. '
  'Physically segregated from platform (behavioral) data. Encryption-at-rest + '
  'access-logging intent. Access mediated only by the gateway/identity service.';

-- platform: behavioral / canonical store. Opaque canonical_uuid only, never PII.
CREATE SCHEMA IF NOT EXISTS platform;
COMMENT ON SCHEMA platform IS
  'Behavioral / canonical store. Rows are keyed by the opaque canonical_uuid and '
  'carry NO PII. Deleting the matching pii_vault row severs identity and leaves these '
  'rows unlinkable to a person (DPDP-clean by construction).';

-- audit: immutable append-only record of privileged actions.
CREATE SCHEMA IF NOT EXISTS audit;
COMMENT ON SCHEMA audit IS
  'Immutable append-only audit trail for privileged / break-glass actions. '
  'No updates or deletes permitted (enforced by trigger).';
