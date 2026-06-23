import { describe, it, expect } from 'vitest';
import {
  CONNECTORS,
  CONNECTOR_STATE_META,
  connectorHealth,
  TRACK_USAGE,
  gateTotals,
  GROWTH_SIGNALS,
  GROWTH_DIRECTION_META,
  nextGrowthInsight,
  NETWORK_NODES,
  childrenOf,
  exceptions,
  networkRoot,
} from '../ring2Data';

describe('connector hub', () => {
  it('every connector state has a tone and a plain-language label', () => {
    for (const c of CONNECTORS) {
      expect(CONNECTOR_STATE_META[c.state]).toBeDefined();
      expect(CONNECTOR_STATE_META[c.state].label.length).toBeGreaterThan(0);
    }
  });

  it('enabling a consequential connector is human-gated, never auto-on', () => {
    // Any consequential connector must NOT already be enabled — it waits.
    for (const c of CONNECTORS) {
      if (c.consequential) {
        expect(c.state).not.toBe('enabled');
      }
    }
  });

  it('the health summary counts add up and never exceed the total', () => {
    const h = connectorHealth();
    expect(h.total).toBe(CONNECTORS.length);
    expect(h.connected).toBeGreaterThan(0);
    expect(h.connected + h.awaitingApproval + h.needsAttention).toBeLessThanOrEqual(h.total);
  });
});

describe('AI control centre — track separation and the confidence gate', () => {
  it('reports exactly one row per track and the two tracks stay distinct', () => {
    const tracks = TRACK_USAGE.map((u) => u.track);
    expect(new Set(tracks).size).toBe(tracks.length);
    expect(tracks).toContain('standards');
    expect(tracks).toContain('platform');
  });

  it('per-track passed + withheld never exceeds total calls', () => {
    for (const u of TRACK_USAGE) {
      expect(u.passed + u.withheld).toBeLessThanOrEqual(u.calls);
    }
  });

  it('gate totals sum the tracks and produce a clamped pass rate', () => {
    const t = gateTotals();
    expect(t.calls).toBe(TRACK_USAGE.reduce((n, u) => n + u.calls, 0));
    expect(t.passRate).toBeGreaterThanOrEqual(0);
    expect(t.passRate).toBeLessThanOrEqual(100);
  });

  it('gate totals handle an empty input without dividing by zero', () => {
    expect(gateTotals([]).passRate).toBe(0);
  });
});

describe('teacher growth coaching', () => {
  it('every signal has a direction with a calm tone and a single experiment', () => {
    for (const s of GROWTH_SIGNALS) {
      expect(GROWTH_DIRECTION_META[s.direction]).toBeDefined();
      expect(s.tryThis.length).toBeGreaterThan(0);
    }
  });

  it('coaching is framed as growth, never judgement (no ranking tone)', () => {
    // None of the directions map to a danger/alarming framing.
    expect(Object.values(GROWTH_DIRECTION_META).map((m) => m.tone)).not.toContain('danger');
  });

  it('surfaces one insight at a time, leading with a growth area', () => {
    const insight = nextGrowthInsight();
    expect(insight).not.toBeNull();
    expect(insight!.direction).toBe('grow');
  });

  it('falls back to the first signal when nothing needs growth', () => {
    const onlyWins = GROWTH_SIGNALS.filter((s) => s.direction === 'celebrate');
    expect(nextGrowthInsight(onlyWins)).toBe(onlyWins[0]);
    expect(nextGrowthInsight([])).toBeNull();
  });

  it('carries no exclamation marks or emoji in coaching copy', () => {
    const blob = JSON.stringify(GROWTH_SIGNALS);
    expect(blob).not.toMatch(/!/);
    expect(blob).not.toMatch(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}]/u);
  });
});

describe('network leadership — hierarchy and manage-by-exception', () => {
  it('has a single group root', () => {
    const root = networkRoot();
    expect(root).not.toBeNull();
    expect(root!.parentId).toBeNull();
    expect(childrenOf(null)).toHaveLength(1);
  });

  it('every non-root node references an existing parent', () => {
    const ids = new Set(NETWORK_NODES.map((n) => n.id));
    for (const n of NETWORK_NODES) {
      if (n.parentId !== null) expect(ids.has(n.parentId)).toBe(true);
    }
  });

  it('regions roll up to campuses (group -> region -> campus)', () => {
    const root = networkRoot()!;
    const regions = childrenOf(root.id);
    expect(regions.length).toBeGreaterThan(0);
    expect(regions.every((r) => r.level === 'region')).toBe(true);
    for (const r of regions) {
      expect(childrenOf(r.id).every((c) => c.level === 'campus')).toBe(true);
    }
  });

  it('the exception list contains only nodes that need attention', () => {
    const ex = exceptions();
    expect(ex.length).toBeGreaterThan(0);
    expect(ex.every((n) => n.needsAttention)).toBe(true);
    for (const n of ex) expect(n.exceptionNote).toBeTruthy();
  });

  it('mastery trends are valid percentages', () => {
    for (const n of NETWORK_NODES) {
      expect(n.masteryTrend).toBeGreaterThanOrEqual(0);
      expect(n.masteryTrend).toBeLessThanOrEqual(100);
    }
  });
});
