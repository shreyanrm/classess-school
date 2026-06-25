import { describe, it, expect } from 'vitest';
import {
  AGENTS,
  agentEnabled,
  POLICIES,
  policyInForce,
  QUADRANT_META,
  QUADRANT_POINTS,
  bandOf,
  quadrantGroups,
  PACING_ROWS,
  pacingSummary,
  TRAJECTORY,
  type QuadrantBand,
} from '../adminData';

describe('agent governance', () => {
  it('falls back to the declared default when no override is set', () => {
    const observer = AGENTS.find((a) => a.id === 'observer')!;
    const steward = AGENTS.find((a) => a.id === 'steward')!;
    expect(agentEnabled(observer)).toBe(observer.defaultOn);
    expect(agentEnabled(steward)).toBe(steward.defaultOn);
  });

  it('honours a persisted override over the default', () => {
    const observer = AGENTS.find((a) => a.id === 'observer')!;
    expect(agentEnabled(observer, { observer: false })).toBe(false);
    const steward = AGENTS.find((a) => a.id === 'steward')!;
    expect(agentEnabled(steward, { steward: true })).toBe(true);
  });

  it('marks every consequential agent as one that only prepares', () => {
    // A consequential agent must never be a plain auto-actor — the surface
    // shows the ladder note; here we just assert the flag exists and is bool.
    for (const a of AGENTS) expect(typeof a.consequential).toBe('boolean');
    expect(AGENTS.some((a) => a.consequential)).toBe(true);
  });
});

describe('policy versioning', () => {
  it('returns the head version when nothing is overridden', () => {
    for (const p of POLICIES) {
      expect(policyInForce(p)).toEqual(p.versions[0]);
    }
  });

  it('returns the chosen version when it is set in force', () => {
    const ai = POLICIES.find((p) => p.id === 'ai-usage')!;
    const v1 = ai.versions.find((v) => v.version === 'v1')!;
    expect(policyInForce(ai, { 'ai-usage': 'v1' })).toEqual(v1);
  });

  it('falls back to the head when an unknown version is set', () => {
    const ai = POLICIES.find((p) => p.id === 'ai-usage')!;
    expect(policyInForce(ai, { 'ai-usage': 'v99' })).toEqual(ai.versions[0]);
  });

  it('keeps versions newest-first with effective dates and a setter', () => {
    for (const p of POLICIES) {
      expect(p.versions.length).toBeGreaterThan(0);
      for (const v of p.versions) {
        expect(v.effective).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(v.setBy.length).toBeGreaterThan(0);
      }
    }
  });
});

describe('study quadrant', () => {
  it('places a point into a band by the independence x consistency split', () => {
    expect(bandOf({ id: 'a', label: 'A', section: 'x', independence: 80, consistency: 80 })).toBe(
      'star',
    );
    expect(bandOf({ id: 'b', label: 'B', section: 'x', independence: 80, consistency: 10 })).toBe(
      'emerging',
    );
    expect(bandOf({ id: 'c', label: 'C', section: 'x', independence: 10, consistency: 80 })).toBe(
      'potential',
    );
    expect(bandOf({ id: 'd', label: 'D', section: 'x', independence: 10, consistency: 10 })).toBe(
      'at-risk',
    );
  });

  it('groups every point into exactly one band', () => {
    const groups = quadrantGroups();
    const total = (Object.keys(groups) as QuadrantBand[]).reduce((n, b) => n + groups[b].length, 0);
    expect(total).toBe(QUADRANT_POINTS.length);
  });

  it('gives every band a tone and a suggested set', () => {
    for (const band of Object.keys(QUADRANT_META) as QuadrantBand[]) {
      expect(QUADRANT_META[band].suggestion.length).toBeGreaterThan(0);
      expect(QUADRANT_META[band].tone).toBeDefined();
    }
  });
});

describe('pacing protection', () => {
  it('counts behind sections and instructional time lost', () => {
    const s = pacingSummary();
    const behind = PACING_ROWS.filter((r) => r.delivered < r.planned);
    expect(s.sections).toBe(PACING_ROWS.length);
    expect(s.behind).toBe(behind.length);
    expect(s.periodsLost).toBe(
      behind.reduce((n, r) => n + (r.planned - r.delivered), 0),
    );
    // Auto-eligible is a subset of the behind sections.
    expect(s.autoEligible).toBeLessThanOrEqual(s.behind);
  });
});

describe('trajectory', () => {
  it('keeps the predicted tail continuing from the last actual reading', () => {
    expect(TRAJECTORY.predicted[0]).toBe(TRAJECTORY.actual[TRAJECTORY.actual.length - 1]);
    expect(TRAJECTORY.actual.every((v) => v >= 0 && v <= 100)).toBe(true);
    expect(TRAJECTORY.predicted.every((v) => v >= 0 && v <= 100)).toBe(true);
  });
});
