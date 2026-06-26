/* ============================================================================
   app/api/admin-config/route.ts — the LIVE seam for the seed-only admin config
   surfaces (calendar, curriculum, exams, integrations, intelligence, network).

   SERVER-ONLY (runtime = 'nodejs'). This is the one place those admin surfaces
   persist their governed configuration AND read it back. It is a faithful, keyed
   generalization of /api/governance: same plumbing, same laws, same degrade —
   it WIRES these surfaces into the circuit, it does not rebuild anything:

     - the WALL authorizes every write FIRST (lib/opGate.authorizeWrite), so the
       full pipeline runs (authn -> RBAC -> ABAC -> consent -> approval ->
       child-safety -> audit, deny-by-default) before any row is committed;
     - the IMMUTABLE, append-only platform.events store (lib/db pool) is the
       record. A config change (a confirmed timetable choice, a hyperlocalisation
       field, an approved exam stage, a connector state, an intelligence lens, an
       opened region) is one attributed, consent-stamped, append-only event.

   POST { surface, key, value } — record one config set. The wall authorizes it;
        on admit it appends ONE event to platform.events. Returns { persisted,
        eventId }. A denied caller is refused (403); an unreachable wall / no db
        degrades to { persisted:false } so the surface keeps working on its seed.

   GET ?actor=<uuid>&surface=<id> — rehydrate that surface's config from the real
        source. Reads its events back THROUGH the governed, consent-gated function
        platform.read_events and reduces them to config : key -> value (last write
        wins). DEGRADE: no db / no consent -> { persisted:false } and the surface
        falls back to its seed (degrade-only).

   No PII ever: actors are opaque canonical_uuid refs; surface/key/value are plain
   bounded strings or scalars the surface owns. Mirrors /api/governance exactly.
   ============================================================================ */

import { getPool } from '@/lib/db';
import { ok, isUuid, str, label } from '@/lib/opRoute';
import { authorizeWrite, denied } from '@/lib/opGate';
import { EVENT_APP } from '@/lib/events';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** The admin-config consent purpose. The SAME purpose gates the read back. */
const CONFIG_PURPOSE = 'admin_config' as const;

/** The one event type these surfaces append. Each is an immutable config record. */
const TYPE = 'admin.config.set' as const;

/** The surfaces allowed to use this seam — bounds the key so it stays legible. */
const SURFACES: ReadonlySet<string> = new Set([
  'calendar',
  'curriculum',
  'exams',
  'integrations',
  'intelligence',
  'network',
  'operations',
]);

/** A config value is a plain scalar the surface owns — bounded, never a blob. */
type ConfigValue = string | number | boolean;

function normaliseValue(v: unknown): ConfigValue {
  if (typeof v === 'boolean' || typeof v === 'number') return v;
  return label(v, 200);
}

// ---------------------------------------------------------------------------
// POST — record one config set (authorized at the wall, appended to the
// immutable event store). One attributed, consent-stamped event.
// ---------------------------------------------------------------------------

interface ConfigBody {
  surface?: string;
  key?: string;
  value?: unknown;
  actor?: string;
}

export async function POST(req: Request): Promise<Response> {
  let body: ConfigBody;
  try {
    body = (await req.json()) as ConfigBody;
  } catch {
    return ok({ persisted: false, reason: 'bad-request' }, 400);
  }

  const surface = str(body.surface);
  const key = label(body.key, 96);
  if (!SURFACES.has(surface) || !key) {
    return ok({ persisted: false, reason: 'invalid-input' }, 400);
  }
  const value = normaliseValue(body.value);

  // The wall authorizes the config write FIRST. Admin config is a write to the
  // institution capability (only an admin configures the institution); a denied
  // caller is refused before any append, an unreachable wall degrades to seed.
  const gate = await authorizeWrite(req, 'institution', 'write', {
    payload: { type: TYPE, surface, purpose: CONFIG_PURPOSE },
    consentPurpose: CONFIG_PURPOSE,
  });
  if (!gate.proceed) return denied(gate.detail);

  // The actor is the opaque caller uuid (from the headers the surface stamps).
  const actor = str(req.headers.get('x-caller-uuid')) || str(body.actor);
  if (!isUuid(actor)) return ok({ persisted: false, reason: 'no-actor' });

  const pool = getPool();
  if (!pool) return ok({ persisted: false, reason: 'no-db' });

  try {
    // Ensure an active consent row for (actor, admin_config) so the append carries
    // a consent_ref and the governed read can return it. Mirrors /api/governance.
    const found = await pool.query<{ consent_id: string }>(
      `SELECT consent_id FROM platform.consents
         WHERE canonical_uuid = $1 AND purpose = $2 AND revoked_at IS NULL LIMIT 1`,
      [actor, CONFIG_PURPOSE],
    );
    let consentRef = found.rows[0]?.consent_id ?? null;
    if (!consentRef) {
      const inserted = await pool.query<{ consent_id: string }>(
        `INSERT INTO platform.consents (canonical_uuid, scope, purpose, granted_by)
           VALUES ($1, $2, $3, $1)
           ON CONFLICT (canonical_uuid, scope, purpose) WHERE revoked_at IS NULL
           DO UPDATE SET purpose = EXCLUDED.purpose
           RETURNING consent_id`,
        [actor, CONFIG_PURPOSE, CONFIG_PURPOSE],
      );
      consentRef = inserted.rows[0]?.consent_id ?? null;
    }

    const payload = { surface, key, value };
    const stored = await pool.query<{ event_id: string }>(
      `INSERT INTO platform.events
         (canonical_uuid, app, type, purpose, consent_ref, payload, occurred_at)
       VALUES ($1, $2, $3, $4, $5, $6::jsonb, now())
       RETURNING event_id`,
      [actor, EVENT_APP, TYPE, CONFIG_PURPOSE, consentRef, JSON.stringify(payload)],
    );
    const eventId = stored.rows[0]?.event_id;
    return ok({ persisted: Boolean(eventId), eventId });
  } catch {
    return ok({ persisted: false, reason: 'write-failed' });
  }
}

// ---------------------------------------------------------------------------
// GET — rehydrate one surface's config from the real source
// (platform.read_events), reduced to key -> value (last write wins). The seed is
// the degrade-only fallback the surface keeps for an unconfigured deploy.
// ---------------------------------------------------------------------------

interface ConfigEventRow {
  type: string;
  payload: Record<string, unknown> | string;
  occurred_at: string;
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const actor = str(url.searchParams.get('actor'));
  const surface = str(url.searchParams.get('surface'));
  if (!isUuid(actor) || !SURFACES.has(surface)) {
    return ok({ persisted: false, config: {}, reason: 'invalid-input' }, 400);
  }

  const pool = getPool();
  if (!pool) return ok({ persisted: false, config: {} });

  try {
    const res = await pool.query<ConfigEventRow>(
      `SELECT type, payload, occurred_at
         FROM platform.read_events($1, $2)
        ORDER BY occurred_at ASC`,
      [actor, CONFIG_PURPOSE],
    );

    const config: Record<string, ConfigValue> = {};
    for (const row of res.rows) {
      if (row.type !== TYPE) continue;
      const payload = (typeof row.payload === 'string' ? JSON.parse(row.payload) : row.payload) ?? {};
      // Reduce only THIS surface's sets; events are newest-last (ASC) so the last
      // write for a key wins.
      if (payload.surface === surface && typeof payload.key === 'string') {
        config[payload.key] = normaliseValue(payload.value);
      }
    }

    return ok({ persisted: true, config });
  } catch {
    return ok({ persisted: false, config: {}, reason: 'read-failed' });
  }
}
