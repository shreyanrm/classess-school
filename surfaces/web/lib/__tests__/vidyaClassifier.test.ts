import { describe, it, expect } from 'vitest';
import { classifyPath, pathSummary, type VidyaAction, type VidyaPath } from '../vidya';

/* ============================================================================
   The 5-path generative-UI classifier CONTRACT (spec 16.2). classifyPath is a
   PURE projection of the actions the orchestrator returned onto exactly one of
   five paths — the same truth on the home and the dock. These lock the
   precedence and the exhaustiveness so the taxonomy can never silently drift.
   ============================================================================ */

const nav: VidyaAction = { type: 'navigate', target: '/student/progress' };
const highlight: VidyaAction = { type: 'highlight', region: 'mastery-band' };
const annotate: VidyaAction = { type: 'annotate', region: 'gap-list', note: 'start here' };
const mastery: VidyaAction = {
  type: 'render',
  spec: {
    kind: 'mastery',
    topic: 'Trigonometry',
    plainLanguage: 'growing',
    independent: false,
    revisionDue: false,
    observationCount: 4,
    dimensions: [],
  },
};
const draft: VidyaAction = {
  type: 'render',
  spec: {
    kind: 'draft',
    title: 'Quick check',
    topic: 'Fractions',
    body: 'prepared',
    items: ['a'],
    confidence: 'middle',
    requiresApproval: true,
    openHref: '/teacher/assign',
    openLabel: 'Review',
  },
};
const quizSurface: VidyaAction = {
  type: 'render',
  spec: {
    kind: 'surface',
    surface: {
      kind: 'quiz-builder',
      title: 'Quiz',
      topic: 'Photosynthesis',
      items: [],
      publish: { label: 'Set live', requiresApproval: true, openHref: '/teacher/assign' },
    },
  },
};
const classSurface: VidyaAction = {
  type: 'render',
  spec: {
    kind: 'surface',
    surface: { kind: 'class-view', title: '9-B', section: '9-B', rows: [] },
  },
};
const canvas: VidyaAction = {
  type: 'canvas',
  spec: { kind: 'canvas', title: 'Derivation', content: { type: 'derivation', steps: [{ text: 'x' }] } },
};

describe('classifyPath — the 5-path contract (spec 16.2)', () => {
  it('Path 1 (answer): no render/route/guide actions', () => {
    expect(classifyPath([])).toBe('answer');
  });

  it('Path 1 (answer): highlight/annotate alone is still prose (pointing, not routing)', () => {
    expect(classifyPath([highlight])).toBe('answer');
    expect(classifyPath([annotate])).toBe('answer');
  });

  it('Path 2 (compose): a non-consequential rendered view', () => {
    expect(classifyPath([mastery])).toBe('compose');
    expect(classifyPath([classSurface])).toBe('compose');
    expect(classifyPath([canvas])).toBe('compose');
  });

  it('Path 3 (act): a consequential prepare carries the approval step', () => {
    expect(classifyPath([draft])).toBe('act');
    expect(classifyPath([quizSurface])).toBe('act');
  });

  it('Path 4 (route-dock): a bare navigate opens the page + docks', () => {
    expect(classifyPath([nav])).toBe('route-dock');
  });

  it('Path 5 (route-guide): a navigate + an on-screen guide (highlight/annotate)', () => {
    expect(classifyPath([nav, highlight])).toBe('route-guide');
    expect(classifyPath([nav, annotate])).toBe('route-guide');
  });

  it('precedence: route+guide outranks route-dock; route outranks render', () => {
    // A turn that both routes and renders + guides is still a routing turn —
    // the workspace is the destination, guided.
    expect(classifyPath([nav, highlight, mastery])).toBe('route-guide');
    expect(classifyPath([nav, draft])).toBe('route-dock');
  });
});

describe('pathSummary — a calm, neutral line for every path (no orchestrator name)', () => {
  const paths: VidyaPath[] = ['answer', 'compose', 'act', 'route-dock', 'route-guide'];
  it('names each path in plain language with no PII / product name', () => {
    for (const p of paths) {
      const s = pathSummary(p);
      expect(s.length).toBeGreaterThan(0);
      expect(s.toLowerCase()).not.toContain('orchestrator');
      expect(s).not.toMatch(/!/);
    }
  });
});
