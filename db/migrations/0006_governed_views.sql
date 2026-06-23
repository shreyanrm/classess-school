-- =============================================================================
-- 0006_governed_views.sql
-- Governed, consent-and-purpose-gated read path over platform.events.
--
-- THE RULE: nothing reads events by bulk-selecting the table. Every read goes
-- through platform.read_events(p_canonical_uuid, p_purpose), which returns rows
-- ONLY when an active consent for that (person, purpose) exists. Without a
-- satisfied consent the function returns ZERO rows -- never an error that could
-- leak existence, just an empty set.
--
-- Consent satisfaction (here): an active consent row
--   (revoked_at IS NULL) for the person whose purpose matches the requested
--   purpose. The event's own stamped purpose must also match, so a consent for
--   one purpose cannot unlock events emitted under another.
--
-- Idempotent.
-- =============================================================================

CREATE OR REPLACE FUNCTION platform.read_events(
  p_canonical_uuid uuid,
  p_purpose        text
)
RETURNS TABLE (
  event_id        uuid,
  canonical_uuid  uuid,
  app             text,
  type            text,
  purpose         text,
  consent_ref     uuid,
  payload         jsonb,
  occurred_at     timestamptz,
  recorded_at     timestamptz,
  schema_version  integer
)
LANGUAGE sql
STABLE
-- SECURITY INVOKER (default): the caller's privileges apply; RLS on
-- platform.events still governs. This function is the *purpose* gate, layered
-- on top of RLS (the identity gate). Both must pass.
AS $$
  SELECT
    e.event_id,
    e.canonical_uuid,
    e.app,
    e.type,
    e.purpose,
    e.consent_ref,
    e.payload,
    e.occurred_at,
    e.recorded_at,
    e.schema_version
  FROM platform.events e
  WHERE e.canonical_uuid = p_canonical_uuid
    AND e.purpose        = p_purpose
    -- Consent gate: an active consent for this person + purpose must exist.
    AND EXISTS (
      SELECT 1
      FROM platform.consents c
      WHERE c.canonical_uuid = p_canonical_uuid
        AND c.purpose        = p_purpose
        AND c.revoked_at IS NULL
    )
  ORDER BY e.occurred_at;
$$;

COMMENT ON FUNCTION platform.read_events(uuid, text) IS
  'Governed read path over platform.events. Returns rows ONLY when an active '
  'consent for (canonical_uuid, purpose) exists AND the event was emitted under '
  'that same purpose; otherwise returns an empty set. This is the only intended '
  'way to read events back -- never a bulk table read.';

-- ---------------------------------------------------------------------------
-- Convenience: a person's currently-satisfiable purposes. Lets a caller learn
-- what it may request without exposing event contents.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION platform.satisfied_purposes(
  p_canonical_uuid uuid
)
RETURNS TABLE (purpose text, scope text, age_tier text)
LANGUAGE sql
STABLE
AS $$
  SELECT c.purpose, c.scope, c.age_tier
  FROM platform.consents c
  WHERE c.canonical_uuid = p_canonical_uuid
    AND c.revoked_at IS NULL;
$$;

COMMENT ON FUNCTION platform.satisfied_purposes(uuid) IS
  'Lists active (consented) purposes for a person. No event contents exposed.';
