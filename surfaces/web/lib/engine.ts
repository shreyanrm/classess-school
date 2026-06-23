/* ============================================================================
   lib/engine.ts — a faithful TypeScript port of the Classess intelligence
   engine, so the browser can compute the Student <-> Teacher loop live from
   attempt events.

   This mirrors spine/intelligence/app (mastery.py, gaps.py, evidence.py) rule
   for rule, and binds to @classess/contracts for the shared types (the six
   mastery dimensions, the ten gap types, the attempt/score event shapes, and
   the prerequisite ontology). It is PURE and DETERMINISTIC: the same events +
   asof produce the same reading and the same gaps — exactly like the Python
   engine, which never authors mastery directly but REPLAYS events to derive it.

   The raw composite and the formula are NEVER surfaced to a learner. Callers
   render the plain-language band and the explicit dimensions; the composite is
   for ranking only.

   Confidentiality: every id here is an opaque token. Nothing carries PII.
   ============================================================================ */

import type {
  AssistanceLevel,
  Edge,
  GapType,
  MasteryBand,
  MasteryDimensions,
  MasteryReading,
  MasteryWeights,
} from '@classess/contracts';

// ---------------------------------------------------------------------------
// The replayed event shapes the engine consumes. A trimmed-but-faithful mirror
// of contracts EventEnvelope / AttemptPayload / ScoreRecordedPayload — only the
// fields the engine reads. Producers (lib/loopData.ts, the live loop) build
// these directly so the surface can run without the gateway.
// ---------------------------------------------------------------------------

export interface OntologyRef {
  topic_id: string;
  outcome_id?: string;
  competency_id?: string;
  skill_id?: string;
}

export type AttemptMode = 'independent' | 'supported';
export type EvalConfidenceBand = 'low' | 'medium' | 'high';

export interface AttemptPayload {
  attempt_id: string;
  question_id?: string;
  ontology: OntologyRef;
  mode: AttemptMode;
  assistance_level: AssistanceLevel;
  correct: boolean;
  /** Partial-credit score in [0,1]; when absent, derived from `correct`. */
  score?: number;
  time_taken_ms: number;
  difficulty: number;
  attempt_number?: number;
}

export interface ScoreRecordedPayload {
  score_id: string;
  submission_id: string;
  scored_subject: string;
  ontology: OntologyRef;
  raw_score: number;
  confidence_band: EvalConfidenceBand;
  human_final: boolean;
}

/** A stored, immutable, append-only event the engine replays. */
export type EngineEvent =
  | {
      event_id: string;
      occurred_at: string; // ISO-8601 UTC
      canonical_uuid: string; // opaque learner ref
      type: 'attempt.recorded';
      payload: AttemptPayload;
    }
  | {
      event_id: string;
      occurred_at: string;
      canonical_uuid: string;
      type: 'score.recorded';
      payload: ScoreRecordedPayload;
    };

// ---------------------------------------------------------------------------
// Constants — kept identical to the Python engine (evidence.py).
// ---------------------------------------------------------------------------

/** Half-life for recency decay, in days. RECENCY_HALF_LIFE = 21 days. */
const RECENCY_HALF_LIFE_DAYS = 21;

/** Generic weight of a supported attempt vs an independent one. */
const SUPPORTED_WEIGHT = 0.6;
const INDEPENDENT_WEIGHT = 1.0;

/** Assistance ladder, most-support -> none. Lower index = more help. */
const ASSISTANCE_ORDER: Record<AssistanceLevel, number> = {
  Learn: 0,
  Coach: 1,
  Hint: 2,
  'Work-with-me': 3,
  'Check-my-work': 4,
  Independent: 5,
};

/** Evaluator-confidence multipliers for score.recorded corroboration. */
const CONFIDENCE_BAND_WEIGHT: Record<EvalConfidenceBand, number> = {
  low: 0.4,
  medium: 0.7,
  high: 1.0,
};

/** Default multiplicative exponents — uniform (a plain product). */
export const DEFAULT_WEIGHTS: MasteryWeights = {
  performance: 1,
  reliability: 1,
  independence: 1,
  difficulty: 1,
  recency: 1,
  consistency: 1,
};

// Composite -> band thresholds (mastery.py _BAND_THRESHOLDS).
const BAND_THRESHOLDS: ReadonlyArray<[number, MasteryBand]> = [
  [0.55, 'independent'],
  [0.32, 'secure'],
  [0.16, 'developing'],
  [0.0001, 'emerging'],
];

const INDEPENDENT_FLAG_FLOOR = 0.55;
export const MIN_OBSERVATIONS_FOR_STABLE_READING = 2;

// Gap engine constants (gaps.py).
const WEAK_SCORE = 0.5;
const WEAK_PERFORMANCE = 0.55;
const MIN_SIGNALS_TO_CONFIRM = 2;
const SLOW_THRESHOLD_MS = 90_000;

// ---------------------------------------------------------------------------
// Plain-language mapping. INVARIANT: never show the formula or a raw number.
// (mastery.py _PLAIN_LANGUAGE + plain_language_for)
// ---------------------------------------------------------------------------
const PLAIN_LANGUAGE: Record<MasteryBand, string> = {
  'not-started': 'not started yet',
  emerging: 'you are starting to see how this works',
  developing: 'you can do this with guidance',
  secure: 'you can do this reliably, with a little support',
  independent: 'you can do this independently',
};

export function plainLanguageFor(
  band: MasteryBand,
  revisionDue: boolean,
  latentBand: MasteryBand = band,
): string {
  // The revision-due message is judged on LATENT competence (recency held at
  // full), so strong-but-stale evidence reads 'revision is due' rather than as a
  // fresh weakness, while a genuinely weak learner never does. Mirrors
  // spine/intelligence/app/mastery.py plain_language_for.
  if (revisionDue && (latentBand === 'secure' || latentBand === 'independent' || latentBand === 'developing')) {
    return 'revision is due';
  }
  return PLAIN_LANGUAGE[band];
}

export function assistanceRank(level: AssistanceLevel): number {
  return ASSISTANCE_ORDER[level] ?? 0;
}

// ---------------------------------------------------------------------------
// The evidence item — one normalized observation with a back-reference to its
// source event (the unit of LINEAGE). Mirrors evidence.py EvidenceItem.
// ---------------------------------------------------------------------------
export interface EvidenceItem {
  eventId: string;
  occurredAt: number; // epoch ms
  topicId: string;
  score: number;
  correct: boolean;
  independent: boolean;
  assistanceLevel: AssistanceLevel;
  difficulty: number;
  timeTakenMs: number | null;
  source: 'attempt' | 'score';
  confidenceBand: EvalConfidenceBand | null;
}

function recencyWeight(item: EvidenceItem, asof: number): number {
  const ageDays = Math.max(asof - item.occurredAt, 0) / 86_400_000;
  return Math.pow(0.5, ageDays / RECENCY_HALF_LIFE_DAYS);
}

function baseWeight(item: EvidenceItem): number {
  let w = item.independent ? INDEPENDENT_WEIGHT : SUPPORTED_WEIGHT;
  if (item.confidenceBand !== null) {
    w *= CONFIDENCE_BAND_WEIGHT[item.confidenceBand] ?? 0.7;
  }
  return w;
}

function weight(item: EvidenceItem, asof: number): number {
  return baseWeight(item) * recencyWeight(item, asof);
}

function effectiveScore(a: AttemptPayload): number {
  if (a.score !== undefined && a.score !== null) return a.score;
  return a.correct ? 1 : 0;
}

function attemptToItem(env: Extract<EngineEvent, { type: 'attempt.recorded' }>): EvidenceItem {
  const a = env.payload;
  return {
    eventId: env.event_id,
    occurredAt: Date.parse(env.occurred_at),
    topicId: a.ontology.topic_id,
    score: effectiveScore(a),
    correct: a.correct,
    independent: a.mode === 'independent',
    assistanceLevel: a.assistance_level,
    difficulty: a.difficulty,
    timeTakenMs: a.time_taken_ms,
    source: 'attempt',
    confidenceBand: null,
  };
}

function scoreToItem(env: Extract<EngineEvent, { type: 'score.recorded' }>): EvidenceItem {
  // A recorded score is corroborating evidence: it carries no independence
  // signal of its own (treated as supported), so it cannot lift independence,
  // but it DOES count as a second, fresh signal for gaps and reassessment.
  const s = env.payload;
  return {
    eventId: env.event_id,
    occurredAt: Date.parse(env.occurred_at),
    topicId: s.ontology.topic_id,
    score: s.raw_score,
    correct: s.raw_score >= 0.5,
    independent: false,
    assistanceLevel: 'Check-my-work',
    difficulty: 0.5,
    timeTakenMs: null,
    source: 'score',
    confidenceBand: s.confidence_band,
  };
}

/**
 * Replay the event list into the ordered evidence trail for one (learner,
 * topic). Filters by canonical_uuid + topic, sorts chronologically — the same
 * input always yields the same trail (idempotent rebuild).
 */
export function collectEvidence(
  events: EngineEvent[],
  subject: string,
  topicId: string,
): EvidenceItem[] {
  const items: EvidenceItem[] = [];
  for (const env of events) {
    if (env.canonical_uuid !== subject) continue;
    if (env.type === 'attempt.recorded' && env.payload.ontology.topic_id === topicId) {
      items.push(attemptToItem(env));
    } else if (
      env.type === 'score.recorded' &&
      env.payload.scored_subject === subject &&
      env.payload.ontology.topic_id === topicId
    ) {
      items.push(scoreToItem(env));
    }
  }
  items.sort((a, b) => a.occurredAt - b.occurredAt || (a.eventId < b.eventId ? -1 : 1));
  return items;
}

/** Every topic the learner has any evidence on. */
export function topicsWithEvidence(events: EngineEvent[], subject: string): Set<string> {
  const topics = new Set<string>();
  for (const env of events) {
    if (env.canonical_uuid !== subject) continue;
    if (env.type === 'attempt.recorded') topics.add(env.payload.ontology.topic_id);
    else if (env.type === 'score.recorded' && env.payload.scored_subject === subject) {
      topics.add(env.payload.ontology.topic_id);
    }
  }
  return topics;
}

function lineageIds(items: EvidenceItem[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const it of items) {
    if (!seen.has(it.eventId)) {
      seen.add(it.eventId);
      out.push(it.eventId);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// The six dimensions. Each returns a value in [0,1]. (mastery.py)
// ---------------------------------------------------------------------------

function pstdev(values: number[]): number {
  const n = values.length;
  if (n === 0) return 0;
  const mean = values.reduce((s, v) => s + v, 0) / n;
  const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / n;
  return Math.sqrt(variance);
}

const clamp01 = (v: number): number => Math.max(0, Math.min(1, v));

function performance(items: EvidenceItem[], asof: number): number {
  let num = 0;
  let den = 0;
  for (const it of items) {
    const w = weight(it, asof);
    num += it.score * w;
    den += w;
  }
  return den > 0 ? num / den : 0;
}

function reliability(items: EvidenceItem[]): number {
  const n = items.length;
  if (n === 0) return 0;
  const sizeFactor = 1 - Math.pow(0.5, n);
  const scores = items.map((it) => it.score);
  let spreadFactor: number;
  if (n === 1) spreadFactor = 0.5;
  else spreadFactor = 1 - Math.min(pstdev(scores) * 2, 1);
  return clamp01(sizeFactor * (0.5 + 0.5 * spreadFactor));
}

function independence(items: EvidenceItem[], asof: number): number {
  let indepCredit = 0;
  let totalCredit = 0;
  for (const it of items) {
    const w = weight(it, asof);
    const contribution = it.score * w;
    totalCredit += contribution;
    if (it.independent) {
      indepCredit += contribution;
    } else {
      // Partial credit for climbing the ladder, capped at half.
      const rank = assistanceRank(it.assistanceLevel); // 0..5
      const ladderCredit = (rank / 5) * 0.5;
      indepCredit += contribution * ladderCredit;
    }
  }
  if (totalCredit <= 0) return 0;
  return clamp01(indepCredit / totalCredit);
}

function difficulty(items: EvidenceItem[], asof: number): number {
  let num = 0;
  let den = 0;
  for (const it of items) {
    const w = weight(it, asof);
    if (it.score > 0) {
      num += (0.4 + 0.6 * it.difficulty) * it.score * w;
      den += it.score * w;
    }
  }
  return den > 0 ? num / den : 0;
}

function recency(items: EvidenceItem[], asof: number): number {
  if (items.length === 0) return 0;
  return Math.max(...items.map((it) => recencyWeight(it, asof)));
}

function consistency(items: EvidenceItem[]): number {
  const n = items.length;
  if (n === 0) return 0;
  if (n === 1) return 0.5;
  const scores = items.map((it) => it.score);
  let sum = 0;
  for (let i = 1; i < n; i++) sum += Math.abs(scores[i]! - scores[i - 1]!);
  const masd = sum / (n - 1);
  return clamp01(1 - masd);
}

export function computeDimensions(items: EvidenceItem[], asof: number): MasteryDimensions {
  return {
    performance: performance(items, asof),
    reliability: reliability(items),
    independence: independence(items, asof),
    difficulty: difficulty(items, asof),
    recency: recency(items, asof),
    consistency: consistency(items),
  };
}

const DIMENSION_KEYS: ReadonlyArray<keyof MasteryDimensions> = [
  'performance',
  'reliability',
  'independence',
  'difficulty',
  'recency',
  'consistency',
];

/** The collapsed product, for RANKING ONLY. PROD_d dimension[d]^weight[d]. */
export function composite(dims: MasteryDimensions, weights: MasteryWeights = DEFAULT_WEIGHTS): number {
  let value = 1;
  for (const key of DIMENSION_KEYS) {
    value *= Math.pow(dims[key], weights[key]);
  }
  return clamp01(value);
}

export function bandFor(comp: number, dims: MasteryDimensions, nObs: number): MasteryBand {
  if (nObs === 0) return 'not-started';
  let chosen: MasteryBand = 'emerging';
  for (const [threshold, band] of BAND_THRESHOLDS) {
    if (comp >= threshold) {
      chosen = band;
      break;
    }
  }
  // A single observation never reads above 'developing'.
  if (nObs < MIN_OBSERVATIONS_FOR_STABLE_READING && (chosen === 'secure' || chosen === 'independent')) {
    chosen = 'developing';
  }
  // The independent band must be earned independently.
  if (chosen === 'independent' && dims.independence < INDEPENDENT_FLAG_FLOOR) {
    chosen = 'secure';
  }
  return chosen;
}

// ---------------------------------------------------------------------------
// The full mastery result. `reading` is the contract object; `plainLanguage`
// is the only thing a learner ever sees.
// ---------------------------------------------------------------------------
export interface MasteryResult {
  topicId: string;
  reading: MasteryReading;
  plainLanguage: string;
  revisionDue: boolean;
  observationCount: number;
  independentObservationCount: number;
  evidenceEventIds: string[];
  computedAt: number;
}

export function computeMastery(
  events: EngineEvent[],
  subject: string,
  topicId: string,
  asof: number = Date.now(),
  weights: MasteryWeights = DEFAULT_WEIGHTS,
): MasteryResult {
  const items = collectEvidence(events, subject, topicId);
  const dims = computeDimensions(items, asof);
  const comp = composite(dims, weights);
  const n = items.length;
  const band = bandFor(comp, dims, n);
  const isIndependent = band === 'independent' && dims.independence >= INDEPENDENT_FLAG_FLOOR;
  const revisionDue = dims.recency < 0.4 && n > 0;
  // Latent band: recency neutralised, used only to judge the revision-due message.
  const latentBand = revisionDue
    ? bandFor(composite({ ...dims, recency: 1 }, weights), { ...dims, recency: 1 }, n)
    : band;
  const reading: MasteryReading = {
    dimensions: dims,
    composite: comp,
    band,
    independent: isIndependent,
  };
  return {
    topicId,
    reading,
    plainLanguage: plainLanguageFor(band, revisionDue, latentBand),
    revisionDue,
    observationCount: n,
    independentObservationCount: items.filter((it) => it.independent).length,
    evidenceEventIds: lineageIds(items),
    computedAt: asof,
  };
}

// ---------------------------------------------------------------------------
// The gap engine — ten gap types, each with its own detection rule. A gap is
// NEVER confirmed from a single bad score (CORE invariant). (gaps.py)
// ---------------------------------------------------------------------------
export interface GapEvidence {
  gapType: GapType;
  confidence: number;
  confirmed: boolean;
  evidenceEventIds: string[];
  rationale: string;
}

export interface GapResult {
  evidence: GapEvidence;
  signalCount: number;
}

function confidenceFromSignals(signalCount: number, strength = 1): number {
  if (signalCount <= 0) return 0;
  const base = 1 - Math.pow(0.5, signalCount); // 1->0.5, 2->0.75, 3->0.875
  return clamp01(base * strength);
}

function mkGap(
  gapType: GapType,
  signalItems: EvidenceItem[],
  rationale: string,
  strength = 1,
  extraEventIds: string[] = [],
): GapResult | null {
  const ids: string[] = [...signalItems.map((it) => it.eventId), ...extraEventIds];
  const seen = new Set<string>();
  const deduped: string[] = [];
  for (const id of ids) {
    if (!seen.has(id)) {
      seen.add(id);
      deduped.push(id);
    }
  }
  if (deduped.length === 0) return null;
  const n = signalItems.length + extraEventIds.length;
  return {
    evidence: {
      gapType,
      confidence: confidenceFromSignals(n, strength),
      confirmed: n >= MIN_SIGNALS_TO_CONFIRM,
      evidenceEventIds: deduped,
      rationale,
    },
    signalCount: n,
  };
}

function detectSupportDependency(items: EvidenceItem[]): GapResult | null {
  const supportedSuccess = items.filter((it) => !it.independent && it.score >= WEAK_SCORE);
  if (supportedSuccess.length < MIN_SIGNALS_TO_CONFIRM) return null;
  const indepSuccess = items.filter((it) => it.independent && it.score >= WEAK_SCORE);
  if (indepSuccess.length > 0) return null;
  const independentFail = items.filter((it) => it.independent && it.score < WEAK_SCORE);
  return mkGap(
    'support-dependency',
    [...supportedSuccess, ...independentFail],
    'Performs well with assistance but has not yet demonstrated the same independently. Response: deliberately fade the support.',
    0.9,
  );
}

function detectSpeedVsAccuracy(items: EvidenceItem[]): GapResult[] {
  const out: GapResult[] = [];
  const slowCorrect = items.filter(
    (it) => it.correct && it.timeTakenMs !== null && it.timeTakenMs > SLOW_THRESHOLD_MS,
  );
  if (slowCorrect.length >= MIN_SIGNALS_TO_CONFIRM) {
    const g = mkGap(
      'speed',
      slowCorrect,
      'Work is correct but consistently slower than the timed context needs. Response: fluency building, not new instruction.',
      0.85,
    );
    if (g) out.push(g);
  }
  const nearMisses = items.filter((it) => it.score >= 0.5 && it.score < 1);
  if (nearMisses.length >= MIN_SIGNALS_TO_CONFIRM) {
    const g = mkGap(
      'accuracy',
      nearMisses,
      'Method is right but execution is error-prone (slips, miscalculation). Response: precision drills and self-checking.',
      0.7,
    );
    if (g) out.push(g);
  }
  return out;
}

function detectConceptualVsProcedural(items: EvidenceItem[]): GapResult | null {
  const veryWeak = items.filter((it) => it.score <= 0.25);
  const weakEvenSupported = veryWeak.filter((it) => !it.independent);
  if (weakEvenSupported.length >= MIN_SIGNALS_TO_CONFIRM) {
    return mkGap(
      'conceptual',
      weakEvenSupported,
      'Struggles even with support and scores near zero — the underlying idea is misunderstood, not just the execution. Response: re-explain and re-anchor the concept.',
      0.85,
    );
  }
  const partialOrCoached = items.filter(
    (it) => (it.score > 0.25 && it.score < WEAK_SCORE) || (!it.independent && it.score < WEAK_SCORE),
  );
  if (partialOrCoached.length >= MIN_SIGNALS_TO_CONFIRM) {
    return mkGap(
      'procedural',
      partialOrCoached,
      'The concept is grasped but the method/steps are not reliably executed. Response: guided practice on the procedure.',
      0.7,
    );
  }
  return null;
}

function detectApplication(items: EvidenceItem[]): GapResult | null {
  const easySuccess = items.filter((it) => it.difficulty <= 0.4 && it.score >= WEAK_SCORE);
  const hardFail = items.filter((it) => it.difficulty >= 0.6 && it.score < WEAK_SCORE);
  if (easySuccess.length > 0 && hardFail.length >= MIN_SIGNALS_TO_CONFIRM) {
    return mkGap(
      'application',
      hardFail,
      'Handles the idea in isolation but cannot transfer it to novel or harder problems. Response: varied-context application practice.',
      0.75,
      [easySuccess[0]!.eventId],
    );
  }
  return null;
}

function detectRetention(items: EvidenceItem[], mastery: MasteryResult): GapResult | null {
  const priorSuccess = items.filter((it) => it.score >= WEAK_SCORE);
  if (priorSuccess.length === 0) return null;
  if (mastery.reading.dimensions.recency < 0.4) {
    const recent = [...items]
      .sort((a, b) => a.occurredAt - b.occurredAt)
      .slice(-MIN_SIGNALS_TO_CONFIRM);
    return mkGap(
      'retention',
      recent,
      'Was demonstrated before but the evidence has aged and may have decayed. Response: spaced retrieval and review.',
      0.6,
      [priorSuccess[0]!.eventId],
    );
  }
  return null;
}

function detectConfidence(items: EvidenceItem[]): GapResult | null {
  const nearIndepSuccess = items.filter(
    (it) => !it.independent && assistanceRank(it.assistanceLevel) >= 3 && it.score >= WEAK_SCORE,
  );
  const indepDip = items.filter((it) => it.independent && it.score >= 0.25 && it.score < WEAK_SCORE);
  if (nearIndepSuccess.length >= 1 && indepDip.length >= MIN_SIGNALS_TO_CONFIRM - 1 && indepDip.length > 0) {
    const signals = [...nearIndepSuccess.slice(0, 1), ...indepDip];
    if (signals.length >= MIN_SIGNALS_TO_CONFIRM) {
      return mkGap(
        'confidence',
        signals,
        'Capable with light support but falters under full self-reliance. Response: scaffolded autonomy and low-stakes wins.',
        0.65,
      );
    }
  }
  return null;
}

function detectPrerequisite(
  items: EvidenceItem[],
  mastery: MasteryResult,
  events: EngineEvent[],
  subject: string,
  topicId: string,
  edges: Edge[],
  asof: number,
  weights: MasteryWeights,
): GapResult | null {
  if (mastery.reading.dimensions.performance > WEAK_PERFORMANCE) return null;
  const prereqEdges = edges.filter((e) => e.to_topic_id === topicId && e.confirmed);
  for (const edge of prereqEdges) {
    const pre = computeMastery(events, subject, edge.from_topic_id, asof, weights);
    if (pre.observationCount === 0) continue;
    if (pre.reading.dimensions.performance <= WEAK_PERFORMANCE) {
      const hereWeak = items.filter((it) => it.score < WEAK_SCORE);
      if (hereWeak.length >= 1) {
        return mkGap(
          'prerequisite',
          hereWeak,
          `Weak on this topic and also weak on its confirmed prerequisite (${edge.kind} edge: ${edge.rationale}). Response: route back to the prerequisite in the graph.`,
          0.85,
          pre.evidenceEventIds.slice(0, 1),
        );
      }
    }
  }
  return null;
}

function detectLanguage(items: EvidenceItem[]): GapResult | null {
  const slowWrongEasy = items.filter(
    (it) =>
      it.difficulty <= 0.4 &&
      it.score < WEAK_SCORE &&
      it.timeTakenMs !== null &&
      it.timeTakenMs > SLOW_THRESHOLD_MS,
  );
  if (slowWrongEasy.length >= MIN_SIGNALS_TO_CONFIRM) {
    const g = mkGap(
      'language',
      slowWrongEasy,
      'Possible comprehension or terminology barrier rather than the academic concept (slow and wrong even on easy items). Proposed only — confirm with a free-text or translation signal. Response: hyperlocalized language support, not re-teaching the concept.',
      0.4,
    );
    if (g) {
      // Language stays UNCONFIRMED until a richer signal corroborates it.
      return { evidence: { ...g.evidence, confirmed: false }, signalCount: g.signalCount };
    }
  }
  return null;
}

/**
 * Run every gap rule over one (learner, topic) evidence trail. Returns all
 * detected gaps (confirmed and unconfirmed), each with full lineage. A single
 * bad score yields, at most, UNCONFIRMED low-confidence signals.
 */
export function detectGaps(
  events: EngineEvent[],
  subject: string,
  topicId: string,
  edges: Edge[] = [],
  asof: number = Date.now(),
  weights: MasteryWeights = DEFAULT_WEIGHTS,
  mastery?: MasteryResult,
): GapResult[] {
  const items = collectEvidence(events, subject, topicId);
  const m = mastery ?? computeMastery(events, subject, topicId, asof, weights);
  const results: GapResult[] = [];
  if (items.length === 0) return results;

  const add = (g: GapResult | null) => {
    if (g) results.push(g);
  };

  add(detectPrerequisite(items, m, events, subject, topicId, edges, asof, weights));
  add(detectConceptualVsProcedural(items));
  add(detectApplication(items));
  add(detectRetention(items, m));
  add(detectSupportDependency(items));
  add(detectConfidence(items));
  for (const g of detectSpeedVsAccuracy(items)) add(g);
  add(detectLanguage(items));

  // Stable ordering: confirmed first, then by confidence desc, then gap type.
  results.sort((a, b) => {
    if (a.evidence.confirmed !== b.evidence.confirmed) return a.evidence.confirmed ? -1 : 1;
    if (a.evidence.confidence !== b.evidence.confidence) return b.evidence.confidence - a.evidence.confidence;
    return a.evidence.gapType < b.evidence.gapType ? -1 : 1;
  });
  return results;
}

// ---------------------------------------------------------------------------
// Surface helpers: a plain-language phrasing for each band, and gap labels, so
// every consumer renders the same calm copy. Never a number, never a formula.
// ---------------------------------------------------------------------------

/** The short class/teacher-facing phrase for a band (independent vs support). */
export const BAND_SHORT: Record<MasteryBand, string> = {
  'not-started': 'Not started yet',
  emerging: 'Showing the idea, with support',
  developing: 'Works with guidance',
  secure: 'Reliable, with a little support',
  independent: 'Can do this on their own',
};

/** Whether a band counts as an unaided, independent demonstration. */
export function isIndependentBand(reading: MasteryReading): boolean {
  return reading.independent;
}

/** Title-case label for a gap type, e.g. "support-dependency" -> "Support dependency". */
export function gapLabel(gap: GapType): string {
  const spaced = gap.replace(/-/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
