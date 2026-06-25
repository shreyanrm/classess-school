/* ============================================================================
   lib/opData.ts — the CLIENT-SAFE seam to the LIVE operational data routes.

   This is the browser side of the operational data plane (school setup,
   attendance, coursework, messaging). It builds well-formed requests and posts
   them to /api/* route handlers, which read/write the operational.* tables
   through the SERVER-ONLY pool in lib/db.ts. Like lib/events.ts it carries NO
   secret and NO database import — it is safe to bundle into a client component.

   GRACEFUL DEGRADATION: every call is best-effort and NEVER throws. When the
   database is unconfigured (CLSS_DATABASE_URL unset) the routes answer 200 with
   { persisted:false } / { rows:[] } and callers stay on the local store / mock
   layer — nothing is ever blank, nothing ever crashes.

   LAWS honoured here:
     - canonical_uuid is the OPAQUE locally-minted id; never real PII.
     - no secret is read, no NEXT_PUBLIC leak; the routes hold the secret.
     - reads are scoped by opaque ids; the routes validate every input.
   ============================================================================ */

import { readStore } from './store';

/** Route the school setup persists / reloads from. */
export const SCHOOL_ROUTE = '/api/school';
/** Route attendance records persist / reload from. */
export const ATTENDANCE_ROUTE = '/api/attendance';
/** Route assignments + submissions persist / reload from. */
export const COURSEWORK_ROUTE = '/api/coursework';
/** Route channels + messages persist / reload from. */
export const MESSAGES_ROUTE = '/api/messages';

/** The shared shape every operational route returns. `persisted` is false on
 *  the degraded (no-db) path; `rows` is present on reads. Never carries a key. */
export interface OpResult<Row = Record<string, unknown>> {
  persisted: boolean;
  rows?: Row[];
  /** An opaque id minted by a write (e.g. institution_id), when persisted. */
  id?: string;
  /** A non-sensitive reason on the degraded path (never a key, never a url). */
  reason?: string;
  /** The child-safety verdict the messages route returns (real, not hard-coded).
   *  flagged: held for a responsible adult. escalate: a crisis routed to a human
   *  NOW (never silenced). category: the plain-language reason. support: a calm
   *  line to show on a crisis. */
  flagged?: boolean;
  escalate?: boolean;
  requiresHuman?: boolean;
  category?: 'safe' | 'harassment' | 'crisis';
  support?: string;
}

/** A drafted/confirmed school blueprint, in the shape the route persists. */
export interface SchoolWire {
  institutionId?: string;
  name: string;
  board?: string;
  pacing?: string;
  /** The containment tree as group -> grade -> section, opaque labels only. */
  structure: Array<{
    id: string;
    name: string;
    grades: Array<{
      id: string;
      name: string;
      sections: Array<{ id: string; name: string; teacherLabel?: string }>;
    }>;
  }>;
  /** The starter roster — generic labels only, opaque refs, never PII. */
  roster: Array<{ id: string; label: string; kind: 'student' | 'teacher'; sectionId: string }>;
}

async function call<Row = Record<string, unknown>>(
  route: string,
  init: RequestInit,
  fetchImpl: typeof fetch = fetch,
): Promise<OpResult<Row>> {
  try {
    const res = await fetchImpl(route, init);
    const data = (await res.json().catch(() => ({}))) as Partial<OpResult<Row>>;
    const safety = {
      flagged: typeof data.flagged === 'boolean' ? data.flagged : undefined,
      escalate: typeof data.escalate === 'boolean' ? data.escalate : undefined,
      requiresHuman: typeof data.requiresHuman === 'boolean' ? data.requiresHuman : undefined,
      category:
        data.category === 'safe' || data.category === 'harassment' || data.category === 'crisis'
          ? data.category
          : undefined,
      support: typeof data.support === 'string' ? data.support : undefined,
    };
    if (!res.ok) return { persisted: false, reason: data.reason ?? `http-${res.status}`, ...safety };
    return {
      persisted: Boolean(data.persisted),
      rows: Array.isArray(data.rows) ? data.rows : undefined,
      id: typeof data.id === 'string' ? data.id : undefined,
      reason: typeof data.reason === 'string' ? data.reason : undefined,
      ...safety,
    };
  } catch {
    return { persisted: false, reason: 'network' };
  }
}

/**
 * The opaque caller-identity headers the operational write routes pass to the
 * wall (lib/opGate). Read from the locally-held account — canonical_uuid + role
 * only, NEVER PII, NEVER a secret. When there is no account yet (pre-sign-in /
 * server render) the headers are simply omitted and the route degrades.
 */
function callerHeaders(): Record<string, string> {
  try {
    const account = readStore().account;
    if (!account?.id) return {};
    return {
      'x-caller-uuid': account.id,
      'x-caller-role': account.role,
      'x-caller-app': 'school',
    };
  } catch {
    return {};
  }
}

const JSON_POST = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'content-type': 'application/json', ...callerHeaders() },
  body: JSON.stringify(body),
});

// ---------------------------------------------------------------------------
// School setup — persist the cold-start (institution + structure + roster).
// ---------------------------------------------------------------------------

/** Persist a confirmed blueprint. Returns the live institution id when stored. */
export function saveSchoolLive(
  school: SchoolWire,
  fetchImpl: typeof fetch = fetch,
): Promise<OpResult> {
  return call(SCHOOL_ROUTE, JSON_POST(school), fetchImpl);
}

/** Reload the persisted blueprint for an institution id, if any rows exist. */
export function loadSchoolLive(
  institutionId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<OpResult> {
  const q = `?institution_id=${encodeURIComponent(institutionId)}`;
  return call(`${SCHOOL_ROUTE}${q}`, { method: 'GET' }, fetchImpl);
}

// ---------------------------------------------------------------------------
// Attendance — confirmed marks for a session.
// ---------------------------------------------------------------------------

export interface AttendanceMarkWire {
  institutionId: string;
  sessionId: string;
  nodeId?: string;
  canonicalUuid: string;
  status: 'present' | 'absent' | 'late' | 'excused' | 'unknown';
  confirmedBy?: string;
}

/** Persist a confirmed attendance roll (one row per learner). */
export function saveAttendanceLive(
  input: { institutionId: string; sessionId: string; nodeId?: string; confirmedBy?: string; marks: Array<Omit<AttendanceMarkWire, 'institutionId' | 'sessionId' | 'nodeId' | 'confirmedBy'>> },
  fetchImpl: typeof fetch = fetch,
): Promise<OpResult> {
  return call(ATTENDANCE_ROUTE, JSON_POST(input), fetchImpl);
}

/** Reload confirmed attendance for a session. */
export function loadAttendanceLive(
  sessionId: string,
  institutionId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<OpResult> {
  const q = `?session_id=${encodeURIComponent(sessionId)}&institution_id=${encodeURIComponent(institutionId)}`;
  return call(`${ATTENDANCE_ROUTE}${q}`, { method: 'GET' }, fetchImpl);
}

// ---------------------------------------------------------------------------
// Coursework — assignments + submissions.
// ---------------------------------------------------------------------------

export interface AssignmentWire {
  institutionId: string;
  createdBy: string;
  kind: 'quick_check' | 'assignment' | 'project';
  title: string;
  instructions?: string;
  dueAt?: string;
}

/** Persist a created assignment. Returns its live id when stored. */
export function saveAssignmentLive(
  input: AssignmentWire,
  fetchImpl: typeof fetch = fetch,
): Promise<OpResult> {
  return call(COURSEWORK_ROUTE, JSON_POST(input), fetchImpl);
}

/** Reload assignments for an institution. */
export function loadAssignmentsLive(
  institutionId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<OpResult> {
  const q = `?institution_id=${encodeURIComponent(institutionId)}`;
  return call(`${COURSEWORK_ROUTE}${q}`, { method: 'GET' }, fetchImpl);
}

// ---------------------------------------------------------------------------
// Messaging — channels + messages (the persistence backbone behind Realtime).
// ---------------------------------------------------------------------------

export interface MessageWire {
  institutionId: string;
  channelId: string;
  senderRef: string;
  body: string;
  /** Which surface/thread kind this channel belongs to (e.g. 'parent'). Used by
   *  the route to upsert the channel row before the message references it. */
  surface?: string;
  flagged?: boolean;
  requiresHuman?: boolean;
}

/** Persist a posted message (already safety-screened on the client gate). */
export function saveMessageLive(
  input: MessageWire,
  fetchImpl: typeof fetch = fetch,
): Promise<OpResult> {
  return call(MESSAGES_ROUTE, JSON_POST(input), fetchImpl);
}

/** Reload the message history for a channel. */
export function loadMessagesLive(
  channelId: string,
  institutionId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<OpResult> {
  const q = `?channel_id=${encodeURIComponent(channelId)}&institution_id=${encodeURIComponent(institutionId)}`;
  return call(`${MESSAGES_ROUTE}${q}`, { method: 'GET' }, fetchImpl);
}
