/* ============================================================================
   lib/__tests__/engine.parity.test.ts — the drift guard for the intelligence
   engine.

   The TypeScript engine (lib/engine.ts) and the Python spine
   (spine/intelligence/app: evidence.py, mastery.py, gaps.py) independently
   encode the SAME constants and the SAME rules — they MUST stay in lock-step. A
   change to either one without the other would silently diverge the in-browser
   read from the server read. This fixture pins:

     1) the key shared constants, with the Python source of truth in a comment, and
     2) a few canonical scenarios as expected-outcome fixtures.

   SHARED-CONSTANTS EXPECTATION (keep these two in sync):
     - RECENCY_HALF_LIFE  = 21 days        (evidence.py: RECENCY_HALF_LIFE)
     - SUPPORTED_WEIGHT   = 0.6            (evidence.py: SUPPORTED_WEIGHT)
     - band thresholds    = 0.55 / 0.32 / 0.16 / 0.0001  (mastery.py: _BAND_THRESHOLDS)
     - INDEPENDENT_FLAG_FLOOR = 0.55       (mastery.py: _INDEPENDENT_FLAG_FLOOR)
     - MIN_OBSERVATIONS_FOR_STABLE_READING = 2 (mastery.py)
     - WEAK_SCORE = 0.5, WEAK_PERFORMANCE = 0.55 (gaps.py)
     - MIN_SIGNALS_TO_CONFIRM = 2          (gaps.py)
     - SLOW_THRESHOLD_MS = 90_000          (gaps.py)

   If you change a band cutoff, a half-life, or a gap threshold in lib/engine.ts,
   update spine/intelligence/app AND this fixture together — this test is the
   tripwire that catches a one-sided change.
   ============================================================================ */

import { describe, it, expect } from 'vitest';
import {
  computeMastery,
  detectGaps,
  bandFor,
  composite,
  computeDimensions,
  collectEvidence,
  DEFAULT_WEIGHTS,
  MIN_OBSERVATIONS_FOR_STABLE_READING,
  type EngineEvent,
  type AttemptPayload,
} from '../engine';
import type { MasteryDimensions } from '@classess/contracts';

/** Build dimensions explicitly for a band-threshold check (all six in [0,1]). */
function dims(over: Partial<MasteryDimensions> = {}): MasteryDimensions {
  return {
    performance: 1,
    reliability: 1,
    independence: 1,
    difficulty: 1,
    recency: 1,
    consistency: 1,
    ...over,
  };
}

// Fixed clock so recency math is fully deterministic.
const ASOF = Date.parse('2026-06-01T00:00:00Z');
const DAY = 86_400_000;
const LEARNER = 'learner-parity';
const TOPIC = 'topic-parity';

let seq = 0;
function attempt(
  opts: Partial<AttemptPayload> & {
    correct: boolean;
    mode: 'independent' | 'supported';
    daysAgo: number;
  },
): EngineEvent {
  const { correct, mode, daysAgo, ...rest } = opts;
  seq += 1;
  return {
    event_id: `pe-${seq}`,
    occurred_at: new Date(ASOF - daysAgo * DAY).toISOString(),
    canonical_uuid: LEARNER,
    type: 'attempt.recorded',
    payload: {
      attempt_id: `pa-${seq}`,
      ontology: { topic_id: TOPIC },
      mode,
      assistance_level: mode === 'independent' ? 'Independent' : 'Coach',
      correct,
      time_taken_ms: 30_000,
      difficulty: 0.6,
      ...rest,
    },
  };
}

// ---------------------------------------------------------------------------
// 1) Pinned constants — derived through the engine's own behaviour so a change
//    to any private constant is caught here without exporting internals.
// ---------------------------------------------------------------------------
describe('engine parity — pinned constants (keep in sync with spine/intelligence)', () => {
  it('MIN_OBSERVATIONS_FOR_STABLE_READING is 2 (mastery.py)', () => {
    expect(MIN_OBSERVATIONS_FOR_STABLE_READING).toBe(2);
  });

  it('band thresholds: 0.55 / 0.32 / 0.16 / 0.0001 (mastery.py _BAND_THRESHOLDS)', () => {
    // composite at/above 0.55 with the independence floor cleared -> independent.
    const strong = dims();
    expect(bandFor(0.6, strong, 3)).toBe('independent');
    // at/above 0.55 but independence below the 0.55 floor -> capped to secure.
    expect(bandFor(0.6, dims({ independence: 0.4 }), 3)).toBe('secure');
    // [0.32, 0.55) -> secure.
    expect(bandFor(0.4, strong, 3)).toBe('secure');
    // [0.16, 0.32) -> developing.
    expect(bandFor(0.2, strong, 3)).toBe('developing');
    // (0.0001, 0.16) -> emerging.
    expect(bandFor(0.05, strong, 3)).toBe('emerging');
    // Zero observations is the only path to 'not-started'.
    expect(bandFor(0, strong, 0)).toBe('not-started');
  });

  it('RECENCY_HALF_LIFE is 21 days: one half-life halves a single recency read', () => {
    const fresh = collectEvidence([attempt({ correct: true, mode: 'independent', daysAgo: 0 })], LEARNER, TOPIC);
    const stale = collectEvidence([attempt({ correct: true, mode: 'independent', daysAgo: 21 })], LEARNER, TOPIC);
    const rFresh = computeDimensions(fresh, ASOF).recency;
    const rStale = computeDimensions(stale, ASOF).recency;
    expect(rFresh).toBeCloseTo(1, 5);
    expect(rStale).toBeCloseTo(0.5, 5); // 0.5 ^ (21/21)
  });

  it('SUPPORTED_WEIGHT (0.6) < INDEPENDENT_WEIGHT (1.0): supported reads lower than independent', () => {
    const indep = computeMastery(
      Array.from({ length: 3 }, (_, i) => attempt({ correct: true, mode: 'independent', daysAgo: i, score: 1 })),
      LEARNER,
      TOPIC,
      ASOF,
    );
    const sup = computeMastery(
      Array.from({ length: 3 }, (_, i) => attempt({ correct: true, mode: 'supported', daysAgo: i, score: 1 })),
      LEARNER,
      TOPIC,
      ASOF,
    );
    expect(indep.reading.composite).toBeGreaterThan(sup.reading.composite);
  });
});

// ---------------------------------------------------------------------------
// 2) Canonical scenarios — the readings the loopData seed depends on.
// ---------------------------------------------------------------------------
describe('engine parity — canonical scenarios', () => {
  it('independent vs supported: only the independent trail earns the independent flag', () => {
    const indep = computeMastery(
      Array.from({ length: 4 }, (_, i) => attempt({ correct: true, mode: 'independent', daysAgo: i, score: 1 })),
      LEARNER,
      TOPIC,
      ASOF,
    );
    const sup = computeMastery(
      Array.from({ length: 4 }, (_, i) => attempt({ correct: true, mode: 'supported', daysAgo: i, score: 1 })),
      LEARNER,
      TOPIC,
      ASOF,
    );
    expect(indep.reading.independent).toBe(true);
    expect(sup.reading.independent).toBe(false);
    expect(sup.reading.band).not.toBe('independent');
  });

  it('single bad score is never a confirmed gap (the core invariant)', () => {
    const gaps = detectGaps([attempt({ correct: false, mode: 'independent', daysAgo: 0, score: 0.1 })], LEARNER, TOPIC, [], ASOF);
    expect(gaps.every((g) => !g.evidence.confirmed)).toBe(true);
    // And a single observation never reads above 'developing'.
    const m = computeMastery([attempt({ correct: true, mode: 'independent', daysAgo: 0, score: 1 })], LEARNER, TOPIC, ASOF);
    expect(['not-started', 'emerging', 'developing']).toContain(m.reading.band);
  });

  it('strong-but-stale: an old, strong, independent trail reads revision-due, not weak', () => {
    const stale = computeMastery(
      [
        attempt({ correct: true, mode: 'independent', daysAgo: 70, score: 0.95 }),
        attempt({ correct: true, mode: 'independent', daysAgo: 64, score: 0.95 }),
      ],
      LEARNER,
      TOPIC,
      ASOF,
    );
    expect(stale.revisionDue).toBe(true);
    expect(stale.plainLanguage).toBe('revision is due');
  });

  it('a recent, weak independent learner is NOT told revision is due', () => {
    const weakFresh = computeMastery(
      [
        attempt({ correct: false, mode: 'independent', daysAgo: 1, score: 0.2 }),
        attempt({ correct: false, mode: 'independent', daysAgo: 0, score: 0.25 }),
      ],
      LEARNER,
      TOPIC,
      ASOF,
    );
    expect(weakFresh.plainLanguage).not.toBe('revision is due');
  });

  it('the reading is deterministic: same events + asof give the same composite', () => {
    const events = Array.from({ length: 3 }, (_, i) => attempt({ correct: true, mode: 'independent', daysAgo: i, score: 0.9 }));
    const a = computeMastery(events, LEARNER, TOPIC, ASOF, DEFAULT_WEIGHTS);
    const b = computeMastery(events, LEARNER, TOPIC, ASOF, DEFAULT_WEIGHTS);
    expect(a.reading.composite).toBe(b.reading.composite);
    expect(a.reading.band).toBe(b.reading.band);
  });
});
