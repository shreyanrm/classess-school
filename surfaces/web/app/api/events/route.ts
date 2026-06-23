/* ============================================================================
   app/api/events/route.ts — the LIVE event seam over the platform database.

   SERVER-ONLY (runtime = 'nodejs'). This is the one place the surface writes to
   and reads from the immutable, append-only platform.events store, through the
   server-only pool in lib/db.ts. The client talks to it via lib/events.ts and
   never touches the database or the connection string directly.

   POST  emits an attributed event:
           app . canonical_uuid (opaque) . type . purpose . consent_ref .
           payload . occurred_at
         Before the append it ensures an ACTIVE consent row for
         (canonical_uuid, purpose) exists — that consent is what gates the
         governed read back, and its id becomes the event's consent_ref. The
         insert is append-only; the store's BEFORE UPDATE/DELETE triggers make
         it immutable.

   GET   reads events back THROUGH the governed function
           platform.read_events(p_canonical_uuid, p_purpose)
         — never a bulk table read. Without an active consent it returns zero
         rows by design.

   DEGRADE: when CLSS_DATABASE_URL is unset (getPool() === null) BOTH verbs
   answer 200 with { persisted:false } / { rows:[] } so the app keeps working on
   its local store. The connection string and any secret are NEVER returned,
   logged, or exposed as NEXT_PUBLIC.
   ============================================================================ */

import { getPool, type PoolLike } from '@/lib/db';
import { EVENT_APP } from '@/lib/events';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const NO_STORE = { 'cache-control': 'no-store' } as const;

function ok(body: Record<string, unknown>, status = 200): Response {
  return Response.json(body, { status, headers: NO_STORE });
}

/** A defensive uuid check so a malformed ref never reaches the query layer. */
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function isUuid(v: unknown): v is string {
  return typeof v === 'string' && UUID_RE.test(v);
}

/**
 * Ensure an active consent row for (canonical_uuid, purpose) exists, returning
 * its id to stamp as the event's consent_ref. Uses the partial unique index
 * (consents_active_uidx) so a concurrent insert collapses to the existing row.
 * The grantor is the person themselves (self-consent) for this demo seam.
 */
async function ensureConsent(
  pool: PoolLike,
  canonicalUuid: string,
  purpose: string,
): Promise<string | null> {
  const found = await pool.query<{ consent_id: string }>(
    `SELECT consent_id FROM platform.consents
       WHERE canonical_uuid = $1 AND purpose = $2 AND revoked_at IS NULL
       LIMIT 1`,
    [canonicalUuid, purpose],
  );
  if (found.rows[0]?.consent_id) return found.rows[0].consent_id;

  const inserted = await pool.query<{ consent_id: string }>(
    `INSERT INTO platform.consents (canonical_uuid, scope, purpose, granted_by)
       VALUES ($1, $2, $3, $1)
       ON CONFLICT (canonical_uuid, scope, purpose) WHERE revoked_at IS NULL
       DO UPDATE SET purpose = EXCLUDED.purpose
       RETURNING consent_id`,
    [canonicalUuid, purpose, purpose],
  );
  return inserted.rows[0]?.consent_id ?? null;
}

export async function POST(req: Request): Promise<Response> {
  let body: {
    canonical_uuid?: string;
    type?: string;
    purpose?: string;
    payload?: unknown;
    consent_ref?: string;
    occurred_at?: string;
  };
  try {
    body = await req.json();
  } catch {
    return ok({ persisted: false, reason: 'bad-request' }, 400);
  }

  const canonicalUuid = String(body.canonical_uuid ?? '').trim();
  const type = String(body.type ?? '').trim();
  const purpose = String(body.purpose ?? '').trim();
  if (!isUuid(canonicalUuid) || !type || !purpose) {
    return ok({ persisted: false, reason: 'invalid-input' }, 400);
  }
  const payload =
    body.payload && typeof body.payload === 'object' && !Array.isArray(body.payload)
      ? (body.payload as Record<string, unknown>)
      : {};

  // No live database — designed degraded path. The app stays on its local store.
  const pool = getPool();
  if (!pool) return ok({ persisted: false, reason: 'no-db' });

  try {
    const consentRef = isUuid(body.consent_ref)
      ? body.consent_ref
      : await ensureConsent(pool, canonicalUuid, purpose);

    const occurredAt = body.occurred_at && String(body.occurred_at).trim()
      ? String(body.occurred_at)
      : new Date().toISOString();

    const inserted = await pool.query<{ event_id: string }>(
      `INSERT INTO platform.events
         (canonical_uuid, app, type, purpose, consent_ref, payload, occurred_at)
       VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
       RETURNING event_id`,
      [canonicalUuid, EVENT_APP, type, purpose, consentRef, JSON.stringify(payload), occurredAt],
    );
    const eventId = inserted.rows[0]?.event_id;
    return ok({ persisted: Boolean(eventId), eventId });
  } catch {
    // A live database that rejected the write must not break the UI either.
    return ok({ persisted: false, reason: 'write-failed' });
  }
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const canonicalUuid = String(url.searchParams.get('canonical_uuid') ?? '').trim();
  const purpose = String(url.searchParams.get('purpose') ?? '').trim();
  if (!isUuid(canonicalUuid) || !purpose) {
    return ok({ persisted: false, rows: [], reason: 'invalid-input' }, 400);
  }

  const pool = getPool();
  if (!pool) return ok({ persisted: false, rows: [] });

  try {
    // The ONLY way to read events back: the governed, consent-gated function.
    const res = await pool.query(
      `SELECT event_id, canonical_uuid, app, type, purpose, payload, occurred_at, recorded_at
         FROM platform.read_events($1, $2)`,
      [canonicalUuid, purpose],
    );
    return ok({ persisted: true, rows: res.rows });
  } catch {
    return ok({ persisted: false, rows: [], reason: 'read-failed' });
  }
}
