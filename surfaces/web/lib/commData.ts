/* ============================================================================
   lib/commData.ts — the CLIENT-SAFE seam to the LIVE communication capability.

   This is the browser side of the communication circuit. It builds well-formed
   requests and posts them to /api/comm, which calls the EXISTING communication
   capability (translate / make_tasks / ptm) THROUGH the wall and dispatches to
   the module's own logic (translation / hub / ptm). Like lib/opData / lib/events
   it carries NO secret and NO gateway import — it is safe to bundle into a client
   component.

   GRACEFUL DEGRADATION: every call is best-effort and NEVER throws. When the
   wall is unconfigured / unreachable the route answers { ok:false, degraded:true }
   and callers keep their local behaviour — nothing blanks, nothing crashes. A
   wall deny answers { ok:false, denied:true }.

   LAWS honoured here:
     - canonical_uuid is the OPAQUE locally-held id; never real PII.
     - no secret is read, no NEXT_PUBLIC leak; the route holds the secret.
     - translate is a READ; make_tasks + ptm are consequential (the wall +
       dispatch persist a clean attributed event for each).
   ============================================================================ */

import { readStore } from './store';

export const COMM_ROUTE = '/api/comm';

/** The shared answer shape from /api/comm. `ok` true when the wall admitted and
 *  the module ran; `data` is the module's JSON result. Never carries a secret. */
export interface CommResult<Data = Record<string, unknown>> {
  ok: boolean;
  data?: Data;
  /** True when the wall actively denied (RBAC/ABAC/consent/approval). */
  denied?: boolean;
  /** True when the wall was unreachable/unconfigured (local behaviour stands). */
  degraded?: boolean;
  /** A non-sensitive reason on the degraded/denied path (never a key, never a url). */
  reason?: string;
  source?: 'gateway' | 'fallback';
}

/** The translate result the module returns (translation.render_for_reader). */
export interface TranslateData {
  rendered_text: string;
  source_lang: string;
  target_lang: string;
  status: 'translated' | 'passthrough';
  preserved_terms: string[];
  provider: string;
}

/** The make_tasks result (hub.route_to_task + a persisted task_created event). */
export interface MakeTaskData {
  task_id: string;
  owner_role: string;
  needs_human: boolean;
  event?: Record<string, unknown>;
}

/** The ptm result (ptm.PtmService.request_booking + a persisted ptm.requested event). */
export interface PtmData {
  booking_id: string;
  is_confirmed: boolean;
  question_count: number;
  event?: Record<string, unknown>;
}

/**
 * The opaque caller-identity headers the route passes to the wall. Read from the
 * locally-held account — canonical_uuid + role only, NEVER PII, NEVER a secret.
 * When there is no account yet the headers are omitted and the route degrades.
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

async function call<Data = Record<string, unknown>>(
  payload: Record<string, unknown>,
  fetchImpl: typeof fetch = fetch,
): Promise<CommResult<Data>> {
  try {
    const res = await fetchImpl(COMM_ROUTE, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...callerHeaders() },
      body: JSON.stringify(payload),
    });
    const data = (await res.json().catch(() => ({}))) as Partial<CommResult<Data>>;
    return {
      ok: Boolean(data.ok),
      data: (data.data as Data) ?? undefined,
      denied: data.denied === true,
      degraded: data.degraded === true,
      reason: typeof data.reason === 'string' ? data.reason : undefined,
      source: data.source === 'gateway' ? 'gateway' : 'fallback',
    };
  } catch {
    return { ok: false, degraded: true, reason: 'network', source: 'fallback' };
  }
}

/**
 * Render text into a READER's preferred language, preserving subject terminology
 * + code-switch spans (GAP#8). Degrades to a content-preserving passthrough; the
 * caller shows the original text unchanged when degraded — never blank.
 */
export function translateForReader(
  input: { text: string; preferredLang?: string; sourceLang?: string },
  fetchImpl: typeof fetch = fetch,
): Promise<CommResult<TranslateData>> {
  return call<TranslateData>(
    {
      op: 'translate',
      text: input.text,
      preferred_lang: input.preferredLang,
      source_lang: input.sourceLang ?? 'und',
    },
    fetchImpl,
  );
}

/**
 * Promote a free-text concern into an owned, tracked task (GAP#9). The message is
 * screened then routed (hub.route_to_task); a clean attributed event is persisted.
 * Consequential -> the route forwards the approval token (the permission ladder).
 */
export function routeToTask(
  input: {
    body: string;
    title: string;
    ownerRole: string;
    why?: string;
    dueDate?: string;
    surface?: string;
    contextRef?: string;
    targetContextRef?: string;
    consentRef?: string;
    senderRef?: string;
  },
  fetchImpl: typeof fetch = fetch,
): Promise<CommResult<MakeTaskData>> {
  return call<MakeTaskData>(
    {
      op: 'make_tasks',
      body: input.body,
      title: input.title,
      owner_role: input.ownerRole,
      why: input.why,
      due_date: input.dueDate,
      surface: input.surface,
      context_ref: input.contextRef,
      target_context_ref: input.targetContextRef,
      consent_ref: input.consentRef,
      sender_ref: input.senderRef,
    },
    fetchImpl,
  );
}

/**
 * Prepare a parent-teacher meeting booking request (GAP#12) — PROPOSED, awaiting
 * a human confirm (the permission ladder). Reuses ptm.PtmService; a clean
 * attributed ptm.requested event is persisted. Consequential -> the route
 * forwards the approval token.
 */
export function requestPtm(
  input: {
    parentRef: string;
    childContextRef: string;
    teacherRef?: string;
    windowLabel?: string;
    startsAt?: string;
    childBrief?: string;
    questionBodies?: string[];
    consentRef?: string;
  },
  fetchImpl: typeof fetch = fetch,
): Promise<CommResult<PtmData>> {
  return call<PtmData>(
    {
      op: 'ptm',
      parent_ref: input.parentRef,
      child_context_ref: input.childContextRef,
      teacher_ref: input.teacherRef,
      window_label: input.windowLabel,
      starts_at: input.startsAt,
      child_brief: input.childBrief,
      question_bodies: input.questionBodies,
      consent_ref: input.consentRef,
    },
    fetchImpl,
  );
}
