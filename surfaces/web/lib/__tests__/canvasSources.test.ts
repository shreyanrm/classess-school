import { describe, it, expect } from 'vitest';
import { parseActions, sanitiseCanvas, type CanvasAction } from '../vidya';

/* ============================================================================
   The canvas SOURCES / evidence shown alongside the answer. Sanitised at the
   trust boundary: plain text, bounded count + length, and an href is kept ONLY
   when it is a real in-app route (never an arbitrary URL).
   ============================================================================ */

describe('sanitiseCanvas — sources / evidence', () => {
  it('keeps plain-text sources, bounds them, and validates the href', () => {
    const spec = sanitiseCanvas({
      title: 'Why this read',
      content: { type: 'written', lines: ['Here is the read'] },
      sources: [
        { label: 'Your last three attempts on fractions', note: 'all unaided', href: '/student/progress' },
        { label: 'A reference', href: '/not-a-real-route' }, // href dropped
        { note: 'no label here' }, // dropped: no label
        { label: '   ' }, // dropped: empty after trim
      ],
    });
    expect(spec.sources).toHaveLength(2);
    expect(spec.sources?.[0]?.href).toBe('/student/progress');
    // An unknown route is dropped, but the source itself (its label) is kept.
    expect(spec.sources?.[1]?.label).toBe('A reference');
    expect(spec.sources?.[1]?.href).toBeUndefined();
  });

  it('caps sources at 8 and leaves sources undefined when there are none', () => {
    const many = Array.from({ length: 20 }, (_, i) => ({ label: `source ${i}` }));
    const spec = sanitiseCanvas({
      title: 't',
      content: { type: 'written', lines: ['x'] },
      sources: many,
    });
    expect(spec.sources).toHaveLength(8);

    const none = sanitiseCanvas({ title: 't', content: { type: 'written', lines: ['x'] } });
    expect(none.sources).toBeUndefined();
  });

  it('round-trips sources through parseActions on a real canvas action', () => {
    const actions = parseActions([
      {
        type: 'canvas',
        spec: {
          title: 'Adding fractions',
          content: { type: 'derivation', steps: [{ text: 'A half plus a quarter', check: { lhs: '1/2 + 1/4', rhs: '3/4' } }] },
          sources: [{ label: 'The worked example you opened earlier' }],
        },
      },
    ]);
    expect(actions).toHaveLength(1);
    const a = actions[0] as CanvasAction;
    expect(a.spec.sources).toHaveLength(1);
    expect(a.spec.sources?.[0]?.label).toBe('The worked example you opened earlier');
  });
});
