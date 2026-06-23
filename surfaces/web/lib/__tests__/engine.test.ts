import { describe, it, expect } from 'vitest';
import {
  computeMastery,
  detectGaps,
  plainLanguageFor,
  type EngineEvent,
  type AttemptPayload,
} from '../engine';

// Fixed clock so recency math is deterministic.
const ASOF = Date.parse('2026-06-01T00:00:00Z');
const DAY = 86_400_000;
const LEARNER = 'learner-a';
const TOPIC = 'topic-trig';

let seq = 0;
function attempt(
  opts: Partial<AttemptPayload> & { correct: boolean; mode: 'independent' | 'supported'; daysAgo: number },
): EngineEvent {
  const { correct, mode, daysAgo, ...rest } = opts;
  seq += 1;
  return {
    event_id: `evt-${seq}`,
    occurred_at: new Date(ASOF - daysAgo * DAY).toISOString(),
    canonical_uuid: LEARNER,
    type: 'attempt.recorded',
    payload: {
      attempt_id: `att-${seq}`,
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

describe('mastery engine — parity with spine/intelligence', () => {
  it('separates independent from support-dependent mastery', () => {
    const indep = Array.from({ length: 4 }, (_, i) =>
      attempt({ correct: true, mode: 'independent', daysAgo: i }),
    );
    const sup = Array.from({ length: 4 }, (_, i) =>
      attempt({ correct: true, mode: 'supported', daysAgo: i }),
    );
    const a = computeMastery(indep, LEARNER, TOPIC, ASOF);
    const b = computeMastery(sup, LEARNER, TOPIC, ASOF);
    expect(a.reading.composite).toBeGreaterThan(b.reading.composite);
    expect(b.reading.band).not.toBe('independent');
  });

  it('never confirms a confident band from a single observation', () => {
    const res = computeMastery(
      [attempt({ correct: true, mode: 'independent', daysAgo: 0 })],
      LEARNER,
      TOPIC,
      ASOF,
    );
    expect(res.observationCount).toBe(1);
    expect(['secure', 'independent']).not.toContain(res.reading.band);
  });

  it('flags strong-but-stale evidence as "revision is due", not a fresh weakness', () => {
    const stale = Array.from({ length: 4 }, () =>
      attempt({ correct: true, mode: 'independent', daysAgo: 120 }),
    );
    const fresh = Array.from({ length: 4 }, (_, i) =>
      attempt({ correct: true, mode: 'independent', daysAgo: i }),
    );
    const old = computeMastery(stale, LEARNER, TOPIC, ASOF);
    const recent = computeMastery(fresh, LEARNER, TOPIC, ASOF);
    expect(old.reading.dimensions.recency).toBeLessThan(recent.reading.dimensions.recency);
    expect(old.reading.dimensions.recency).toBeLessThan(0.4);
    expect(old.plainLanguage).toBe('revision is due');
  });

  it('never leaks the formula or a raw number to a learner', () => {
    const res = computeMastery(
      Array.from({ length: 4 }, (_, i) => attempt({ correct: true, mode: 'supported', daysAgo: i })),
      LEARNER,
      TOPIC,
      ASOF,
    );
    expect(res.plainLanguage).not.toMatch(/[0-9]/);
    expect(res.plainLanguage).not.toMatch(/×|\*/);
  });
});

describe('plainLanguageFor — latent-band override', () => {
  it('a genuinely weak learner is never told "revision is due"', () => {
    // band emerging, latent also emerging -> no override even when stale.
    expect(plainLanguageFor('emerging', true, 'emerging')).not.toBe('revision is due');
  });
  it('a demonstrably strong but stale topic reads "revision is due"', () => {
    expect(plainLanguageFor('emerging', true, 'secure')).toBe('revision is due');
  });
});

describe('gap engine — a gap is never confirmed from a single bad score', () => {
  it('does not classify a gap from one failure', () => {
    const gaps = detectGaps(
      [attempt({ correct: false, mode: 'independent', daysAgo: 0 })],
      LEARNER,
      TOPIC,
      [],
      ASOF,
    );
    // With a single signal, no gap is confirmed (corroboration required).
    expect(gaps.every((g) => g.evidence.confirmed === false)).toBe(true);
  });
});
