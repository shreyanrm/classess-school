/* ============================================================================
   lib/vizReads.ts — the gateway-first VISUALIZATION read seam.

   SERVER-ONLY. The shared viz + report components (attendance heatmap, holistic
   progress, project rubric, paper analysis, Bloom, trend, success gauge,
   calendar, timetable) read their data through the live gateway (the wall) to
   the one source of truth — the intelligence spine. The PII-free seed shapes in
   lib/vizData are the DEGRADE FALLBACK ONLY: they answer when, and only when,
   the wall is unreachable / times out / denies / returns a non-contract body.

   The user-visible reading is identical either way; the `source` ('gateway' vs
   'fallback') is surfaced so a consuming surface can render the SourceNote
   honestly. The web only READS here; it never bypasses the wall.

   Confidentiality: every id is an opaque canonical ref. No PII, no secret.
   ============================================================================ */

import { readCapability, type CallerIdentity, type GatewayResult } from './gateway';
import {
  VIZ_FALLBACK,
  type VizBundle,
  type VizKind,
} from './vizData';

/** What source actually answered a read — surfaced for the SourceNote. */
export type ReadSource = 'gateway' | 'fallback';

export interface VizRead<K extends VizKind> {
  kind: K;
  data: VizBundle[K];
  source: ReadSource;
  /** When the gateway was tried and declined, why (for logs only). */
  fallbackReason?: string;
}

/** Was this a hard wall deny (RBAC/ABAC/consent) vs a soft infra-degrade. */
export function isDenied(reason?: string): boolean {
  return reason === 'unauthorized';
}

/**
 * Read one viz shape through the wall. Tries the gateway's `intelligence-views`
 * read for the named view; falls back to the PII-free seed on any degrade. The
 * returned shape is identical either way.
 */
export async function readViz<K extends VizKind>(
  kind: K,
  subjectUuid: string,
  identity: CallerIdentity,
  opts: { fetchImpl?: typeof fetch } = {},
): Promise<VizRead<K>> {
  const result = await readCapability<VizBundle[K]>('intelligence-views', subjectUuid, {
    identity,
    view: `viz:${kind}`,
    // A viz read is a cross-context intelligence read -> assert the purpose so
    // the wall's consent gate runs (it falls back cleanly otherwise).
    consentPurpose: 'intelligence.viz',
    fetchImpl: opts.fetchImpl,
  });

  if (result.ok && isVizShape(kind, result.data)) {
    return { kind, data: result.data, source: 'gateway' };
  }
  return {
    kind,
    data: VIZ_FALLBACK[kind],
    source: 'fallback',
    fallbackReason: result.ok ? 'bad-response' : (result as GatewayResult<unknown> & { ok: false }).reason,
  };
}

/** Read several viz shapes in one hop — one bundle for a surface. */
export async function readVizBundle(
  kinds: VizKind[],
  subjectUuid: string,
  identity: CallerIdentity,
  opts: { fetchImpl?: typeof fetch } = {},
): Promise<{ reads: Array<VizRead<VizKind>>; source: ReadSource; permissionDenied: boolean }> {
  const reads = await Promise.all(kinds.map((k) => readViz(k, subjectUuid, identity, opts)));
  const source: ReadSource = reads.every((r) => r.source === 'gateway') ? 'gateway' : 'fallback';
  const permissionDenied = reads.some((r) => isDenied(r.fallbackReason));
  return { reads, source, permissionDenied };
}

/* ---------------------------------------------------------------------------
   Shape guards — only trust a gateway body that looks like the contract shape;
   anything else (e.g. a generic ack) falls back to the seed.
   --------------------------------------------------------------------------- */

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null;
}

function isVizShape(kind: VizKind, v: unknown): v is VizBundle[VizKind] {
  if (!isObj(v)) return false;
  switch (kind) {
    case 'attendance':
      return Array.isArray(v.months) && isObj(v.counts);
    case 'holistic':
      return Array.isArray(v.competencies) && Array.isArray(v.foundational);
    case 'formalReport':
      return Array.isArray(v.subjects) && isObj(v.attendance);
    case 'rubric':
      return Array.isArray(v.criteria) && Array.isArray(v.submissions);
    case 'paper':
      return isObj(v.overall) && Array.isArray(v.periods);
    case 'bloom':
      return Array.isArray(v.slices);
    case 'success':
      return typeof v.probability === 'number';
    case 'trend':
      return Array.isArray(v.points);
    case 'calendar':
      return Array.isArray(v.events) && typeof v.days === 'number';
    case 'timetable':
      return Array.isArray(v.blocks) && Array.isArray(v.dayLabels);
    case 'assignments':
      return Array.isArray(v.chapters);
    case 'testPaper':
      return Array.isArray(v.sections) && typeof v.kind === 'string';
    case 'teachingStats':
      return typeof v.classesThisWeek === 'number';
    case 'quizResult':
      return Array.isArray(v.questions) && Array.isArray(v.bloom);
    case 'markbook':
      return Array.isArray(v.rows) && Array.isArray(v.periods);
    case 'paperPreview':
      return Array.isArray(v.sections) && typeof v.duration === 'string';
    case 'teacherPtm':
      return Array.isArray(v.slots) && Array.isArray(v.queries);
    default:
      return false;
  }
}
