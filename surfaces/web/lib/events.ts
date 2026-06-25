/* ============================================================================
   lib/events.ts — the CLIENT-SAFE seam to the live, immutable event store.

   This is the browser side of the event seam. It builds a well-formed,
   ATTRIBUTED event and posts it to /api/events, which persists it to the
   append-only platform.events store through the server-only pool (lib/db.ts).

   It is deliberately split from lib/db.ts so this module carries NO secret and
   NO database import — it is safe to bundle into a client component. The route
   on the other side reads the secret server-side and never returns it.

   GRACEFUL DEGRADATION: emitting is best-effort and NEVER blocks the UI. If the
   database is unconfigured the route answers 200 with { persisted: false } and
   the surface simply stays on its local store. A network/transport failure
   resolves to { persisted: false } too — emit() never throws.

   LAWS honoured here:
     - canonical_uuid is the OPAQUE locally-minted id; never real PII.
     - every event is attributed: app . canonical_uuid . type . purpose .
       consent_ref. The purpose is what gates the governed read back.
     - events are immutable/append-only on the server; this client only appends.
   ============================================================================ */

import { readStore } from './store';

export const EVENTS_ROUTE = '/api/events';

/** The app that emits — the school surface. Stamped on every event. */
export const EVENT_APP = 'school' as const;

/** The locally-held account role, for the wall's RBAC (never PII). Empty when
 *  there is no account yet (pre-sign-in / server render). */
function callerRole(): string {
  try {
    return readStore().account?.role ?? '';
  } catch {
    return '';
  }
}

/**
 * The purposes the surface emits under. The SAME purpose must be consented for
 * the governed read (platform.read_events) to return the event. Kept small and
 * plain so the consent gate is legible.
 */
export const EVENT_PURPOSE = {
  /** Learning behaviour — attempts, the loop, mastery evidence. */
  learning: 'learning_behavior',
  /** Teaching actions — assignments, quick checks prepared by a teacher. */
  teaching: 'teaching_activity',
  /** Attendance confirmations. */
  attendance: 'attendance',
} as const;

export type EventPurpose = (typeof EVENT_PURPOSE)[keyof typeof EVENT_PURPOSE];

/** The attributed event the client emits. Mirrors platform.events columns. */
export interface EmitEventInput {
  /** Opaque canonical_uuid (the local account id or a roster ref). Never PII. */
  canonicalUuid: string;
  /** Event type, e.g. 'attempt.recorded', 'assignment.created'. */
  type: string;
  /** The purpose the data serves; gates the governed read. */
  purpose: EventPurpose;
  /** Arbitrary, non-identifying payload. Must serialise to a JSON object. */
  payload?: Record<string, unknown>;
  /** The consent in force at emit time, if known (opaque consent id). */
  consentRef?: string;
  /** Domain time; defaults to now() server-side when omitted. */
  occurredAt?: string;
}

/** The server's answer to an emit. `persisted` is false on the degraded path. */
export interface EmitEventResult {
  persisted: boolean;
  /** The stored event id when persisted; absent on the local-only path. */
  eventId?: string;
  /** A non-sensitive reason on the degraded path (never a key, never a url). */
  reason?: string;
}

/**
 * Validate + normalise an emit input into the JSON body the route expects.
 * Pure and side-effect-free so it can be unit-tested. Throws a plain Error on a
 * structurally invalid input (the caller treats that as a no-op, never a crash).
 */
export function buildEventBody(input: EmitEventInput): {
  app: string;
  canonical_uuid: string;
  type: string;
  purpose: string;
  payload: Record<string, unknown>;
  consent_ref?: string;
  occurred_at?: string;
} {
  const canonicalUuid = (input.canonicalUuid ?? '').trim();
  if (!canonicalUuid) throw new Error('emit: canonical_uuid is required');
  const type = (input.type ?? '').trim();
  if (!type) throw new Error('emit: type is required');
  const purpose = (input.purpose ?? '').trim();
  if (!purpose) throw new Error('emit: purpose is required');

  const payload =
    input.payload && typeof input.payload === 'object' && !Array.isArray(input.payload)
      ? input.payload
      : {};

  const body: ReturnType<typeof buildEventBody> = {
    app: EVENT_APP,
    canonical_uuid: canonicalUuid,
    type,
    purpose,
    payload,
  };
  if (input.consentRef && input.consentRef.trim()) body.consent_ref = input.consentRef.trim();
  if (input.occurredAt && input.occurredAt.trim()) body.occurred_at = input.occurredAt.trim();
  return body;
}

/**
 * Emit an attributed event to the live store, best-effort. NEVER throws and
 * NEVER blocks the UI: a bad input, a missing database, or a transport failure
 * all resolve to { persisted: false } so the surface stays on its local store.
 */
export async function emitEvent(
  input: EmitEventInput,
  route: string = EVENTS_ROUTE,
  fetchImpl: typeof fetch = fetch,
): Promise<EmitEventResult> {
  let body: ReturnType<typeof buildEventBody>;
  try {
    body = buildEventBody(input);
  } catch {
    return { persisted: false, reason: 'invalid-input' };
  }
  try {
    // The wall identifies the emitter by the opaque caller headers (lib/opGate).
    // The emitter IS the event's subject (self-emit), so the body's canonical_uuid
    // is the caller uuid; the role comes from the locally-held account. Never PII.
    const callerHeaders: Record<string, string> = {
      'x-caller-uuid': body.canonical_uuid,
      'x-caller-app': EVENT_APP,
    };
    const role = callerRole();
    if (role) callerHeaders['x-caller-role'] = role;
    const res = await fetchImpl(route, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...callerHeaders },
      body: JSON.stringify(body),
    });
    const data = (await res.json().catch(() => ({}))) as Partial<EmitEventResult>;
    if (!res.ok) return { persisted: false, reason: data.reason ?? `http-${res.status}` };
    return {
      persisted: Boolean(data.persisted),
      eventId: typeof data.eventId === 'string' ? data.eventId : undefined,
      reason: typeof data.reason === 'string' ? data.reason : undefined,
    };
  } catch {
    return { persisted: false, reason: 'network' };
  }
}
