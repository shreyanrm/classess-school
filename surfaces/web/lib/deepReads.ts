/* ============================================================================
   lib/deepReads.ts — the governed DEEP-ENGINE READ seam (gateway-first, engine
   fallback).

   SERVER-ONLY. This is where the web's high-value governed reads — the ones the
   spine owns: mastery, gaps, recommendations, and the class intelligence/insights
   views — are routed THROUGH the live gateway (the wall) to the ONE source of
   truth: the Python intelligence spine. The in-browser engine port (lib/engine +
   lib/classRead) is the DEGRADE FALLBACK ONLY — it answers when, and only when,
   the wall is unreachable / times out / denies / returns a non-contract body.

   One engine, one truth: the Python spine is the source; lib/engine is a faithful
   port kept solely so the live app NEVER breaks when the wall is unavailable. The
   user-visible result is identical either way; in normal operation the deep Python
   engine behind the wall powers the read.

   The web PREPARES and READS; it never bypasses the wall. Writes/auth stay on the
   existing Supabase/local path — only the engine READS are routed here.

   Confidentiality: every id here is an opaque canonical ref. No PII, no secret.
   ============================================================================ */

import {
  callCapability,
  readCapability,
  type CallerIdentity,
  type GatewayResult,
} from './gateway';
import {
  computeMastery,
  detectGaps,
  type EngineEvent,
  type GapResult,
  type MasteryResult,
} from './engine';
import {
  computeClassReads,
  summariseClass,
  studentsNeedingAttention,
  type ClassSummary,
  type StudentTopicRead,
} from './classRead';
import { EDGES, SCENARIO_NOW, SEED_EVENTS } from './loopData';
import { RECOMMENDATIONS } from './mock';

// ---------------------------------------------------------------------------
// Identity helpers — derive the opaque caller identity for the wall from the
// session-held ids. NEVER a secret; only canonical_uuid + role + scope.
// ---------------------------------------------------------------------------

/**
 * Build the wall caller identity from the opaque session ids. The role/scope are
 * what RBAC/ABAC read; the signed token (when the session has one) is forwarded
 * verbatim. This is the ONLY identity the deep reads pass to the wall.
 */
export function callerIdentity(args: {
  canonicalUuid: string;
  role: string;
  scope?: string;
  app?: 'school' | 'learner' | 'platform';
  signedToken?: string;
}): CallerIdentity {
  const app = args.app ?? 'school';
  return {
    canonical_uuid: args.canonicalUuid,
    app,
    memberships: [{ app, role: args.role, scope: args.scope ?? '' }],
    signedToken: args.signedToken,
  };
}

/** What source actually answered a read — surfaced for observability only. */
export type ReadSource = 'gateway' | 'fallback';

export interface DeepRead<T> {
  data: T;
  source: ReadSource;
  /** When the gateway was tried and declined, why (for logs only). */
  fallbackReason?: string;
}

function fallbackOf<T>(data: T, result: GatewayResult<unknown> | null): DeepRead<T> {
  return {
    data,
    source: 'fallback',
    fallbackReason: result && !result.ok ? result.reason : undefined,
  };
}

// ---------------------------------------------------------------------------
// 1) Mastery — a single (learner, topic) reading.
// ---------------------------------------------------------------------------

/**
 * The governed mastery read for one learner+topic. Tries the gateway's
 * `learning.read` (mastery view); falls back to the local engine's computeMastery
 * over the seed/live events. The returned MasteryResult shape is identical.
 */
export async function readMastery(
  subjectUuid: string,
  topicId: string,
  identity: CallerIdentity,
  opts: {
    events?: EngineEvent[];
    asof?: number;
    fetchImpl?: typeof fetch;
  } = {},
): Promise<DeepRead<MasteryResult>> {
  const events = opts.events ?? SEED_EVENTS;
  const asof = opts.asof ?? SCENARIO_NOW;

  const result = await readCapability<MasteryResult>('learning', subjectUuid, {
    identity,
    view: `mastery:${topicId}`,
    // The deep mastery read is a cross-context intelligence read -> assert the
    // purpose so the wall's consent gate runs (it falls back cleanly otherwise).
    consentPurpose: 'intelligence.mastery',
    fetchImpl: opts.fetchImpl,
  });

  if (result.ok && isMasteryShape(result.data)) {
    return { data: result.data, source: 'gateway' };
  }
  return fallbackOf(computeMastery(events, subjectUuid, topicId, asof), result);
}

// ---------------------------------------------------------------------------
// 2) Gaps — the detected gaps for one (learner, topic).
// ---------------------------------------------------------------------------

export async function readGaps(
  subjectUuid: string,
  topicId: string,
  identity: CallerIdentity,
  opts: {
    events?: EngineEvent[];
    asof?: number;
    fetchImpl?: typeof fetch;
  } = {},
): Promise<DeepRead<GapResult[]>> {
  const events = opts.events ?? SEED_EVENTS;
  const asof = opts.asof ?? SCENARIO_NOW;

  const result = await readCapability<GapResult[]>('learning', subjectUuid, {
    identity,
    view: `gaps:${topicId}`,
    // Cross-context intelligence read -> assert the purpose for the consent gate.
    consentPurpose: 'intelligence.gaps',
    fetchImpl: opts.fetchImpl,
  });

  if (result.ok && Array.isArray(result.data)) {
    return { data: result.data, source: 'gateway' };
  }
  return fallbackOf(detectGaps(events, subjectUuid, topicId, EDGES, asof), result);
}

// ---------------------------------------------------------------------------
// 3) Recommendations — the proactive recommendation list.
// ---------------------------------------------------------------------------

export type RecommendationList = typeof RECOMMENDATIONS;

/**
 * The governed recommendations read (intelligence-views). Tries the gateway's
 * `intelligence-views.read` (recommendations view); falls back to the local
 * RECOMMENDATIONS the surface already renders.
 */
export async function readRecommendations(
  subjectUuid: string,
  identity: CallerIdentity,
  opts: { fetchImpl?: typeof fetch } = {},
): Promise<DeepRead<RecommendationList>> {
  const result = await readCapability<RecommendationList>('intelligence-views', subjectUuid, {
    identity,
    view: 'recommendations',
    // Recommendations are a cross-context intelligence read -> declare the purpose
    // so the wall's consent gate runs (it falls back cleanly if consent is absent).
    consentPurpose: 'intelligence.recommendations',
    fetchImpl: opts.fetchImpl,
  });

  if (result.ok && Array.isArray(result.data)) {
    return { data: result.data, source: 'gateway' };
  }
  return fallbackOf(RECOMMENDATIONS, result);
}

// ---------------------------------------------------------------------------
// 4) Class insights — the teacher's rolled-up intelligence view.
// ---------------------------------------------------------------------------

export interface ClassInsights {
  summary: ClassSummary;
  needingAttention: StudentTopicRead[];
  reads: StudentTopicRead[];
}

function localClassInsights(events: EngineEvent[], asof: number): ClassInsights {
  const reads = computeClassReads(events, asof);
  return {
    summary: summariseClass(reads),
    needingAttention: studentsNeedingAttention(reads),
    reads,
  };
}

/**
 * The governed class intelligence/insights view for a teacher. Tries the
 * gateway's `intelligence-views.read` (class view); falls back to the locally
 * computed class reads. `subjectUuid` here is the class/institution scope ref.
 */
export async function readClassInsights(
  subjectUuid: string,
  identity: CallerIdentity,
  opts: {
    events?: EngineEvent[];
    asof?: number;
    fetchImpl?: typeof fetch;
  } = {},
): Promise<DeepRead<ClassInsights>> {
  const events = opts.events ?? SEED_EVENTS;
  const asof = opts.asof ?? SCENARIO_NOW;

  const result = await callCapability<ClassInsights>('intelligence-views', 'read', {
    identity,
    payload: { subject_uuid: subjectUuid, view: 'class-insights' },
    consentPurpose: 'intelligence.class-insights',
    fetchImpl: opts.fetchImpl,
  });

  if (result.ok && isClassInsightsShape(result.data)) {
    return { data: result.data, source: 'gateway' };
  }
  return fallbackOf(localClassInsights(events, asof), result);
}

// ---------------------------------------------------------------------------
// Shape guards — only trust a gateway body that looks like the contract object;
// anything else (e.g. the generic { status: "admitted" } ack) falls back.
// ---------------------------------------------------------------------------

function isMasteryShape(v: unknown): v is MasteryResult {
  return (
    typeof v === 'object' &&
    v !== null &&
    'reading' in v &&
    'plainLanguage' in v &&
    typeof (v as MasteryResult).reading === 'object'
  );
}

function isClassInsightsShape(v: unknown): v is ClassInsights {
  return (
    typeof v === 'object' &&
    v !== null &&
    'summary' in v &&
    'reads' in v &&
    Array.isArray((v as ClassInsights).reads)
  );
}
