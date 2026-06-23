import { describe, it, expect } from 'vitest';
import {
  parseActions,
  sanitiseCanvas,
  canvasHasContent,
  type CanvasAction,
} from '../vidya';

/* ============================================================================
   The floating-canvas action: parsing + sanitisation at the trust boundary.
   The model emits structured content; the client only ever renders a BOUNDED,
   sanitised set of primitives, and a derivation reuses the SAME generate-and-
   verify gate as inline steps (an unverified arithmetic step is dropped).
   ============================================================================ */

describe('parseActions — canvas action', () => {
  it('parses a diagram canvas, clamping coordinates and dropping unknown primitives', () => {
    const actions = parseActions([
      {
        type: 'canvas',
        spec: {
          title: 'A right triangle',
          content: {
            type: 'diagram',
            primitives: [
              { kind: 'line', x1: 10, y1: 10, x2: 90, y2: 10 },
              { kind: 'line', x1: 999, y1: -50, x2: 90, y2: 80, label: 'hyp' },
              { kind: 'mystery', x: 1 }, // dropped: unknown kind
              { kind: 'label', x: 50, y: 5, text: 'base' },
              { kind: 'label', x: 1, y: 1 }, // dropped: no text
            ],
          },
        },
      },
    ]);
    expect(actions).toHaveLength(1);
    const a = actions[0] as CanvasAction;
    expect(a.type).toBe('canvas');
    expect(a.spec.content.type).toBe('diagram');
    const prims = a.spec.content.type === 'diagram' ? a.spec.content.primitives : [];
    expect(prims).toHaveLength(3); // two lines + one label; two dropped
    // The out-of-range coordinates were clamped into [0,100].
    const line2 = prims[1];
    expect(line2?.kind).toBe('line');
    if (line2 && line2.kind === 'line') {
      expect(line2.x1).toBe(100);
      expect(line2.y1).toBe(0);
    }
  });

  it('verifies a derivation canvas — drops the unverified step (generate-and-verify)', () => {
    const actions = parseActions([
      {
        type: 'canvas',
        spec: {
          title: 'Adding fractions',
          content: {
            type: 'derivation',
            steps: [
              { text: 'A half plus a quarter', check: { lhs: '1/2 + 1/4', rhs: '3/4' } },
              { text: 'This (wrong) claim is dropped', check: { lhs: '1/2 + 1/4', rhs: '1' } },
              { text: 'A plain reasoning step with no check' },
            ],
          },
        },
      },
    ]);
    expect(actions).toHaveLength(1);
    const a = actions[0] as CanvasAction;
    const steps = a.spec.content.type === 'derivation' ? a.spec.content.steps : [];
    expect(steps).toHaveLength(2); // the wrong-arithmetic step was withheld
    expect(steps.map((s) => s.text)).not.toContain('This (wrong) claim is dropped');
  });

  it('drops a canvas with no usable content after sanitisation', () => {
    const actions = parseActions([
      { type: 'canvas', spec: { title: 'Empty', content: { type: 'written', lines: ['', '   '] } } },
      { type: 'canvas', spec: { title: 'Unknown', content: { type: 'nope' } } },
    ]);
    expect(actions).toHaveLength(0);
  });
});

describe('sanitiseCanvas — direct', () => {
  it('keeps a real openHref and drops an unknown one', () => {
    const ok = sanitiseCanvas({
      title: 'x',
      content: { type: 'written', lines: ['a line'] },
      openHref: '/student/learn',
      openLabel: 'Open the lesson',
    });
    expect(ok.openHref).toBe('/student/learn');
    expect(canvasHasContent(ok)).toBe(true);

    const bad = sanitiseCanvas({
      title: 'x',
      content: { type: 'written', lines: ['a line'] },
      openHref: '/not-a-route',
    });
    expect(bad.openHref).toBeUndefined();
  });

  it('bounds a graph (needs >=2 points) and a number line', () => {
    const graph = sanitiseCanvas({
      title: 'g',
      content: {
        type: 'diagram',
        primitives: [
          { kind: 'graph', points: [{ x: 0, y: 0 }, { x: 50, y: 80 }, { x: 100, y: 40 }] },
          { kind: 'graph', points: [{ x: 0, y: 0 }] }, // dropped: <2 points
          { kind: 'numberline', from: 0, to: 10, points: [{ value: 3, label: 'x' }] },
        ],
      },
    });
    const prims = graph.content.type === 'diagram' ? graph.content.primitives : [];
    expect(prims).toHaveLength(2);
    expect(prims.map((p) => p.kind)).toEqual(['graph', 'numberline']);
  });
});
