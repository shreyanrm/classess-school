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
import type { Recommendation } from './mock';
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

export type RecommendationList = Recommendation[];

/** The engine-derived recommendation the workflow runtime mints + PERSISTS
 *  (workflow_app.do_recommend -> _RECS). Carries the STABLE id that approve and
 *  execute resolve, and the ladder-derived consequential flag. */
interface EngineRecommendation {
  dispatched?: boolean;
  recommendation_id?: string;
  is_consequential?: boolean;
  why_am_i_seeing_this?: string;
  suggested_action?: string;
}

/** A non-consequential effect lands at `prepare`; a consequential one must use a
 *  CONSEQUENTIAL_VERB so the spine pins it at execute_with_permission (the
 *  ladder). 'submit' is the safe, generic consequential verb for a card. */
function effectVerbFor(rec: Recommendation): string {
  return rec.consequential ? 'submit' : 'prepare';
}

/**
 * The governed recommendations read (intelligence-views). Mints one ENGINE-DERIVED
 * recommendation per surface card through the gateway's `intelligence-views.recommend`
 * rung — the runtime PERSISTS each into its `_RECS` registry so the SAME id the
 * card carries is the one approve/execute resolve end-to-end (the loop contract).
 * The rich display fields stay from the seed card; the engine owns the id + the
 * ladder-derived `consequential` flag. Falls back to the static RECOMMENDATIONS
 * ONLY on true infra-degrade (the recommend rung unreachable / unconfigured).
 */
export async function readRecommendations(
  subjectUuid: string,
  identity: CallerIdentity,
  opts: { fetchImpl?: typeof fetch; seeds?: RecommendationList } = {},
): Promise<DeepRead<RecommendationList>> {
  const seeds = opts.seeds ?? RECOMMENDATIONS;

  // Mint each card's engine-derived recommendation (persisted -> a stable id).
  const minted = await Promise.all(
    seeds.map((seed) =>
      callCapability<EngineRecommendation>('intelligence-views', 'recommend', {
        identity,
        payload: {
          subject_uuid: subjectUuid,
          owner_ref: subjectUuid,
          owner_role: identity.memberships[0]?.role ?? 'teacher',
          gap_type: seed.gapType,
          effect_verb: effectVerbFor(seed),
          evidence_summary: seed.evidenceSummary,
          why_am_i_seeing_this: seed.whySeeing,
          suggested_action: seed.title,
          consequence_of_ignoring: seed.consequence,
        },
        consentPurpose: 'intelligence.recommendations',
        fetchImpl: opts.fetchImpl,
      }),
    ),
  );

  // Every rung must answer with a stable id for the loop to reference one object
  // end-to-end. If ANY card failed to mint, the engine path is not whole -> fall
  // back to the static list (true infra-degrade) rather than ship a mixed feed.
  const allMinted = minted.every(
    (r) => r.ok && typeof r.data.recommendation_id === 'string' && r.data.recommendation_id,
  );
  if (allMinted) {
    const data = seeds.map((seed, i) => {
      const eng = (minted[i] as { ok: true; data: EngineRecommendation }).data;
      return {
        ...seed,
        // The STABLE engine id approve/execute resolve — this IS the loop ref.
        id: eng.recommendation_id as string,
        // The ladder-derived flag is the engine's truth (fail closed to the seed).
        consequential:
          typeof eng.is_consequential === 'boolean' ? eng.is_consequential : seed.consequential,
      };
    });
    return { data, source: 'gateway' };
  }

  // True infra-degrade -> the surface stays on the static feed it already renders.
  const firstFailure = minted.find((r) => !r.ok) as GatewayResult<unknown> | undefined;
  return fallbackOf(seeds, firstFailure ?? null);
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
