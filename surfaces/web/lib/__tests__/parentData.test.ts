import { describe, it, expect } from 'vitest';
import {
  PARENT_CHILDREN,
  DEFAULT_CHILD_ID,
  findChild,
  resolveChildId,
  selectChildData,
  TONE_TAG,
  TONE_PHRASE,
} from '../parentData';

describe('parent surface — child-switch logic', () => {
  it('the default child is the first consented child in the list', () => {
    expect(DEFAULT_CHILD_ID).toBe(PARENT_CHILDREN[0]!.id);
    expect(findChild(DEFAULT_CHILD_ID)?.consentGranted).toBe(true);
  });

  it('findChild returns the matching child and undefined for an unknown id', () => {
    expect(findChild('child-a')?.label).toBe('Child A');
    expect(findChild('does-not-exist')).toBeUndefined();
  });

  it('resolveChildId keeps a valid id and falls back to the default otherwise', () => {
    expect(resolveChildId('child-b')).toBe('child-b');
    expect(resolveChildId('child-z')).toBe(DEFAULT_CHILD_ID);
    expect(resolveChildId(null)).toBe(DEFAULT_CHILD_ID);
    expect(resolveChildId(undefined)).toBe(DEFAULT_CHILD_ID);
    expect(resolveChildId('')).toBe(DEFAULT_CHILD_ID);
  });

  it('switching children returns a different, fully-populated data bundle', () => {
    const a = selectChildData('child-a');
    const b = selectChildData('child-b');
    expect(a).not.toBeNull();
    expect(b).not.toBeNull();
    // The whole surface re-renders: each bundle is its own child's data.
    expect(a!.timeline[0]!.id).not.toBe(b!.timeline[0]!.id);
    expect(a!.briefings.length).toBeGreaterThan(0);
    expect(b!.reports.length).toBeGreaterThan(0);
  });

  it('consent gates the read: an unconsented child yields no data', () => {
    const gated = PARENT_CHILDREN.find((c) => !c.consentGranted);
    expect(gated).toBeDefined();
    expect(selectChildData(gated!.id)).toBeNull();
  });

  it('an unknown child id yields no data rather than leaking another child', () => {
    expect(selectChildData('child-z')).toBeNull();
  });

  it('every consented child has exactly three Today briefings (calm, finite)', () => {
    for (const child of PARENT_CHILDREN) {
      const data = selectChildData(child.id);
      if (!child.consentGranted) {
        expect(data).toBeNull();
        continue;
      }
      expect(data).not.toBeNull();
      expect(data!.briefings).toHaveLength(3);
    }
  });

  it('plain-language copy carries no raw numbers, scores, percentages, or emoji', () => {
    const blob = JSON.stringify(PARENT_CHILDREN.map((c) => selectChildData(c.id)));
    // No percentage signs or standalone score-like tokens slip into parent copy.
    expect(blob).not.toMatch(/%/);
    expect(blob).not.toMatch(/\b\d+\s*\/\s*\d+\b/); // e.g. "7/10"
    expect(blob).not.toMatch(/\b\d+\s*marks?\b/i);
    // No emoji.
    expect(blob).not.toMatch(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}]/u);
    // Product copy carries no exclamation marks.
    expect(blob).not.toMatch(/!/);
  });

  it('every parent tone maps to a calm (non-alarming) tag tone', () => {
    expect(TONE_TAG.celebrate).toBe('success');
    expect(TONE_TAG.support).toBe('info');
    expect(TONE_TAG.steady).toBe('neutral');
    // Never a danger/red framing on the parent surface.
    expect(Object.values(TONE_TAG)).not.toContain('danger');
  });

  it('every tone has a plain-language phrase', () => {
    for (const tone of Object.keys(TONE_TAG) as Array<keyof typeof TONE_TAG>) {
      expect(TONE_PHRASE[tone]).toBeTruthy();
    }
  });

  it('every proof artifact is drawn from the child and states what changed', () => {
    for (const child of PARENT_CHILDREN) {
      const data = selectChildData(child.id);
      if (!data) continue;
      for (const proof of data.proof) {
        expect(proof.headline.length).toBeGreaterThan(0);
        expect(proof.whatChanged.length).toBeGreaterThan(0);
        expect(typeof proof.independent).toBe('boolean');
      }
    }
  });
});
