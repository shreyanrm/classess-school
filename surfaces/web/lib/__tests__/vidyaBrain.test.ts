import { describe, it, expect } from 'vitest';
import {
  parseActions,
  verifyStep,
  evalRational,
  tutorReveal,
  TUTOR_START,
  isHighlightRegion,
  type StepsCardSpec,
} from '../vidya';
import { runTool } from '../vidyaServer';

/* ============================================================================
   Locks for the expanded Vidya brain: speak-and-show action parsing (highlight /
   annotate / verified steps), the deterministic step verifier, and the TUTOR
   ladder invariant — never reveal before a posed attempt. Pure logic only.
   ============================================================================ */

describe('parseActions — speak-and-show actions', () => {
  it('parses a highlight action and drops an unknown region', () => {
    const actions = parseActions([
      { type: 'highlight', region: 'mastery-band', label: 'this is where you stand' },
      { type: 'highlight', region: 'not-a-region' }, // dropped
    ]);
    expect(actions).toHaveLength(1);
    const [h] = actions;
    expect(h && h.type).toBe('highlight');
    expect(h && h.type === 'highlight' && h.region).toBe('mastery-band');
    expect(h && h.type === 'highlight' && h.label).toBe('this is where you stand');
  });

  it('parses an annotate action, dropping an empty or region-less note', () => {
    const actions = parseActions([
      { type: 'annotate', region: 'gap-list', note: 'watch this one' },
      { type: 'annotate', region: 'gap-list', note: '   ' }, // dropped: empty
      { type: 'annotate', region: 'nope', note: 'x' }, // dropped: bad region
    ]);
    expect(actions).toHaveLength(1);
    const [a] = actions;
    expect(a && a.type === 'annotate' && a.region).toBe('gap-list');
    expect(a && a.type === 'annotate' && a.note).toBe('watch this one');
  });

  it('keeps verified steps and DROPS any step whose check fails', () => {
    const actions = parseActions([
      {
        type: 'render',
        spec: {
          kind: 'steps',
          title: 'Adding fractions',
          steps: [
            { text: 'Find a common denominator' }, // no check -> kept
            { text: 'A half plus a quarter is three quarters', check: { lhs: '1/2 + 1/4', rhs: '3/4' } }, // verified -> kept
            { text: 'A half plus a quarter is four quarters', check: { lhs: '1/2 + 1/4', rhs: '4/4' } }, // WRONG -> dropped
          ],
        },
      },
    ]);
    expect(actions).toHaveLength(1);
    const [s] = actions;
    expect(s && s.type).toBe('render');
    const spec = (s as { spec: StepsCardSpec }).spec;
    expect(spec.kind).toBe('steps');
    expect(spec.steps).toHaveLength(2); // the false step is gone
    expect(spec.steps.map((x) => x.text)).not.toContain(
      'A half plus a quarter is four quarters',
    );
  });

  it('isHighlightRegion gates the closed region map', () => {
    expect(isHighlightRegion('mastery-band')).toBe(true);
    expect(isHighlightRegion('vidya-steps')).toBe(true);
    expect(isHighlightRegion('made-up')).toBe(false);
    expect(isHighlightRegion(7)).toBe(false);
  });
});

describe('verifyStep / evalRational — deterministic generate-and-verify gate', () => {
  it('confirms true rational equalities exactly', () => {
    expect(verifyStep('1/2 + 1/4', '3/4')).toBe(true);
    expect(verifyStep('2/4', '1/2')).toBe(true);
    expect(verifyStep('(1+2)*3', '9')).toBe(true);
    expect(verifyStep('0.5 + 0.25', '3/4')).toBe(true);
    expect(verifyStep('3 - 1/3', '8/3')).toBe(true);
  });

  it('rejects false equalities', () => {
    expect(verifyStep('1/2 + 1/4', '4/4')).toBe(false);
    expect(verifyStep('2 + 2', '5')).toBe(false);
  });

  it('treats anything unparseable (or divide-by-zero) as UNVERIFIED', () => {
    expect(verifyStep('x + 1', '2')).toBe(false);
    expect(verifyStep('1/0', '1')).toBe(false);
    expect(verifyStep('', '0')).toBe(false);
    expect(evalRational('sin(x)')).toBeNull();
  });
});

describe('tutorReveal — the assistance ladder never reveals before an attempt', () => {
  it('poses first, with no attempt yet', () => {
    expect(tutorReveal(TUTOR_START)).toBe('pose');
    expect(tutorReveal({ attempts: 0, lastCorrect: false, gaveUp: false })).toBe('pose');
  });

  it('scaffolds after a wrong attempt — still no reveal', () => {
    expect(tutorReveal({ attempts: 1, lastCorrect: false, gaveUp: false })).toBe('scaffold');
    expect(tutorReveal({ attempts: 2, lastCorrect: false, gaveUp: false })).toBe('scaffold');
  });

  it('reveals once correct, after enough scaffolds, or on an explicit give-up', () => {
    expect(tutorReveal({ attempts: 1, lastCorrect: true, gaveUp: false })).toBe('reveal');
    expect(tutorReveal({ attempts: 3, lastCorrect: false, gaveUp: false })).toBe('reveal');
    expect(tutorReveal({ attempts: 0, lastCorrect: false, gaveUp: true })).toBe('reveal');
  });

  it('NEVER reveals on a fresh, un-attempted step (the core invariant)', () => {
    for (let attempts = 0; attempts <= 5; attempts++) {
      const phase = tutorReveal({ attempts: 0, lastCorrect: false, gaveUp: false });
      expect(phase).not.toBe('reveal');
    }
  });
});

describe('runTool — new capabilities behave + obey the ladder', () => {
  it('tutor_step poses (no reveal) when the learner has not tried', () => {
    const { result } = runTool('tutor_step', { concept: 'adding fractions', attempts: 0 });
    expect(result.phase).toBe('pose');
  });

  it('tutor_step scaffolds after a wrong attempt, never revealing early', () => {
    const { result } = runTool('tutor_step', {
      concept: 'adding fractions',
      attempts: 1,
      lastCorrect: false,
    });
    expect(result.phase).toBe('scaffold');
  });

  it('explain_steps emits only verified steps and drops the bad one', () => {
    const { result, action } = runTool('explain_steps', {
      topic: 'adding fractions',
      steps: [
        { text: 'Common denominator first' },
        { text: 'one half plus one quarter', check: { lhs: '1/2+1/4', rhs: '3/4' } },
        { text: 'wrong claim', check: { lhs: '1/2+1/4', rhs: '1' } },
      ],
    });
    expect(result.verified).toBe(true);
    expect(result.stepCount).toBe(2);
    expect(result.dropped).toBe(1);
    expect(action?.type).toBe('render');
    expect(action && action.type === 'render' && action.spec.kind).toBe('steps');
  });

  it('explain_steps refuses to show anything when no step verifies', () => {
    const { result, action } = runTool('explain_steps', {
      topic: 'broken',
      steps: [{ text: 'bad', check: { lhs: '2+2', rhs: '5' } }],
    });
    expect(result.verified).toBe(false);
    expect(action).toBeUndefined();
  });

  it('highlight_target returns a visual action for a known region only', () => {
    const ok = runTool('highlight_target', { region: 'mastery-band', label: 'here' });
    expect(ok.action?.type).toBe('highlight');
    const bad = runTool('highlight_target', { region: 'nope' });
    expect(bad.action).toBeUndefined();
    expect(bad.result.highlighted).toBe(false);
  });

  it('create_study_plan PREPARES and requires approval (never auto-applied)', () => {
    const { result, action } = runTool('create_study_plan', { topic: 'Fractions', days: 5 });
    expect(result.prepared).toBe(true);
    expect(result.requires_approval).toBe(true);
    expect(action?.type).toBe('render');
  });
});
