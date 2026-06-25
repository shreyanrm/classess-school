/* ============================================================================
   app/api/governance/route.ts — the LIVE governance seam (GAP#3/#4/#5/#7).

   SERVER-ONLY (runtime = 'nodejs'). This is the one place the admin governance
   surface persists and rehydrates its governed configuration AND its immutable
   audit trail. It reuses, end to end, the plumbing the rest of the surface
   already trusts — it WIRES governance into the circuit, it does not rebuild it:

     - the WALL authorizes every write FIRST (lib/opGate.authorizeWrite), so the
       full pipeline runs (authn -> RBAC -> ABAC -> consent -> approval ->
       child-safety -> audit, deny-by-default) before any row is committed;
     - the IMMUTABLE, append-only platform.events store (lib/db pool) is the
       audit trail. A governed governance action (an AI-control toggle, a policy
       version set in force, break-glass, an emergency disable) is one attributed,
       consent-stamped, append-only event. That is what makes the surface's claim
       "recorded to the immutable audit trail" TRUE.

   POST { kind, ... } — record a consequential governance action. The wall
        authorizes it; on admit it appends ONE event to platform.events. Returns
        { persisted, eventId }. A denied caller is refused (403); an unreachable
        wall / unconfigured db degrades to { persisted:false } so the surface
        keeps working on its local store (control state stays in localStorage).

   GET ?actor=<uuid> — rehydrate governance from the real source. Reads the
        governance events back THROUGH the governed, consent-gated function
        platform.read_events and reduces them to:
          - config.aiControls : control id -> on (the last toggle wins)
          - config.policyVersions : policy id -> version in force
          - audit : the recent governance audit entries (immutable, append-only)
        DEGRADE: no db / no consent -> { persisted:false, audit:[] } and the
        surface falls back to its seed mock (degrade-only).

   No PII ever: actors are opaque canonical_uuid refs, resources are plain ids.
   ============================================================================ */

import { getPool } from '@/lib/db';
import { ok, isUuid, str, label } from '@/lib/opRoute';
import { authorizeWrite, denied } from '@/lib/opGate';
import { EVENT_APP } from '@/lib/events';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** The governance consent purpose. The SAME purpose gates the read back. */
const GOVERNANCE_PURPOSE = 'governance' as const;

/** The event types governance appends. Each is one immutable audit entry. */
const TYPE = {
  aiControl: 'governance.ai_control.set',
  policy: 'governance.policy.set',
  breakGlass: 'governance.break_glass.engaged',
  emergencyDisable: 'governance.emergency_disable.engaged',
} as const;

/** A human-readable audit line for each governance event type. */
function describe(type: string, payload: Record<string, unknown>): string {
  switch (type) {
    case TYPE.aiControl:
      return `${payload.on ? 'Enabled' : 'Paused'} AI capability: ${label(payload.controlLabel ?? payload.controlId, 80)}`;
    case TYPE.policy:
      return `Set ${label(payload.policyName ?? payload.policyId, 60)} policy ${label(payload.version, 24)} in force`;
    case TYPE.breakGlass:
      return 'Engaged break-glass emergency access';
    case TYPE.emergencyDisable:
      return 'Engaged emergency disable — halted all model autonomy';
    default:
      return label(type, 80);
  }
}

// ---------------------------------------------------------------------------
// POST — record a consequential governance action (authorized at the wall,
// appended to the immutable event store). One attributed, consent-stamped event.
// ---------------------------------------------------------------------------

interface GovBody {
  kind?: 'ai_control' | 'policy' | 'break_glass' | 'emergency_disable';
  actor?: string;
  // ai_control
  controlId?: string;
  controlLabel?: string;
  on?: boolean;
  // policy
  policyId?: string;
  policyName?: string;
  version?: string;
}

export async function POST(req: Request): Promise<Response> {
  let body: GovBody;
  try {
    body = (await req.json()) as GovBody;
  } catch {
    return ok({ persisted: false, reason: 'bad-request' }, 400);
  }

  const kind = str(body.kind);
  let type: string;
  let payload: Record<string, unknown>;
  switch (kind) {
    case 'ai_control':
      if (!str(body.controlId)) return ok({ persisted: false, reason: 'invalid-input' }, 400);
      type = TYPE.aiControl;
      payload = { controlId: label(body.controlId, 64), controlLabel: label(body.controlLabel, 80), on: Boolean(body.on) };
      break;
    case 'policy':
      if (!str(body.policyId) || !str(body.version)) return ok({ persisted: false, reason: 'invalid-input' }, 400);
      type = TYPE.policy;
      payload = { policyId: label(body.policyId, 64), policyName: label(body.policyName, 60), version: label(body.version, 24) };
      break;
    case 'break_glass':
      type = TYPE.breakGlass;
      payload = {};
      break;
    case 'emergency_disable':
      type = TYPE.emergencyDisable;
      payload = {};
      break;
    default:
      return ok({ persisted: false, reason: 'invalid-input' }, 400);
  }

  // The wall authorizes the governance write FIRST. Governance is a write to the
  // institution capability (only an admin governs); a denied caller is refused
  // before any append, an unreachable wall degrades to the local path.
  const gate = await authorizeWrite(req, 'institution', 'write', {
    payload: { type, purpose: GOVERNANCE_PURPOSE },
    consentPurpose: GOVERNANCE_PURPOSE,
  });
  if (!gate.proceed) return denied(gate.detail);

  // The actor is the opaque caller uuid (from the headers the surface stamps);
  // it is the audit subject (self-attributed). Never PII.
  const actor = str(req.headers.get('x-caller-uuid')) || str(body.actor);
  if (!isUuid(actor)) return ok({ persisted: false, reason: 'no-actor' });

  const pool = getPool();
  if (!pool) return ok({ persisted: false, reason: 'no-db' });

  try {
    // Ensure an active consent row for (actor, governance) so the append carries
    // a consent_ref and the governed read can return it. Mirrors /api/events.
    const found = await pool.query<{ consent_id: string }>(
      `SELECT consent_id FROM platform.consents
         WHERE canonical_uuid = $1 AND purpose = $2 AND revoked_at IS NULL LIMIT 1`,
      [actor, GOVERNANCE_PURPOSE],
    );
    let consentRef = found.rows[0]?.consent_id ?? null;
    if (!consentRef) {
      const inserted = await pool.query<{ consent_id: string }>(
        `INSERT INTO platform.consents (canonical_uuid, scope, purpose, granted_by)
           VALUES ($1, $2, $3, $1)
           ON CONFLICT (canonical_uuid, scope, purpose) WHERE revoked_at IS NULL
           DO UPDATE SET purpose = EXCLUDED.purpose
           RETURNING consent_id`,
        [actor, GOVERNANCE_PURPOSE, GOVERNANCE_PURPOSE],
      );
      consentRef = inserted.rows[0]?.consent_id ?? null;
    }

    const stored = await pool.query<{ event_id: string }>(
      `INSERT INTO platform.events
         (canonical_uuid, app, type, purpose, consent_ref, payload, occurred_at)
       VALUES ($1, $2, $3, $4, $5, $6::jsonb, now())
       RETURNING event_id`,
      [actor, EVENT_APP, type, GOVERNANCE_PURPOSE, consentRef, JSON.stringify(payload)],
    );
    const eventId = stored.rows[0]?.event_id;
    return ok({ persisted: Boolean(eventId), eventId });
  } catch {
    return ok({ persisted: false, reason: 'write-failed' });
  }
}

// ---------------------------------------------------------------------------
// GET — rehydrate governance config + the immutable audit trail from the real
// source (platform.read_events), reduced to the current state. Mock is the
// degrade-only fallback the surface keeps for an unconfigured deploy.
// ---------------------------------------------------------------------------

interface GovEventRow {
  event_id: string;
  type: string;
  payload: Record<string, unknown> | string;
  occurred_at: string;
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const actor = str(url.searchParams.get('actor'));
  if (!isUuid(actor)) {
    return ok({ persisted: false, audit: [], reason: 'invalid-input' }, 400);
  }

  const pool = getPool();
  if (!pool) return ok({ persisted: false, audit: [] });

  try {
    const res = await pool.query<GovEventRow>(
      `SELECT event_id, type, payload, occurred_at
         FROM platform.read_events($1, $2)
        ORDER BY occurred_at ASC`,
      [actor, GOVERNANCE_PURPOSE],
    );

    const aiControls: Record<string, boolean> = {};
    const policyVersions: Record<string, string> = {};
    const audit: { id: string; when: string; action: string }[] = [];

    for (const row of res.rows) {
      const payload = (typeof row.payload === 'string' ? JSON.parse(row.payload) : row.payload) ?? {};
      // The last write wins for config — events are newest-last (ASC).
      if (row.type === TYPE.aiControl && typeof payload.controlId === 'string') {
        aiControls[payload.controlId] = Boolean(payload.on);
      } else if (row.type === TYPE.policy && typeof payload.policyId === 'string' && typeof payload.version === 'string') {
        policyVersions[payload.policyId] = payload.version;
      }
      audit.push({ id: row.event_id, when: row.occurred_at, action: describe(row.type, payload) });
    }
    // The audit trail reads newest-first for display.
    audit.reverse();

    return ok({ persisted: true, config: { aiControls, policyVersions }, audit });
  } catch {
    return ok({ persisted: false, audit: [], reason: 'read-failed' });
  }
}
