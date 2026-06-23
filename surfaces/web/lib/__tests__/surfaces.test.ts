import { describe, it, expect, beforeEach } from 'vitest';
import {
  filterResources,
  isServable,
  libraryStats,
  loadContent,
  toResourceView,
  type ContentResource,
} from '../contentData';
import {
  applyTransition,
  canSubmit,
  canTransition,
  loadInbox,
  pushAssignedCheck,
  resetAssignedChecks,
  toAssignmentView,
  type AssignmentItem,
} from '../workData';
import {
  isVerifiable,
  issueCredential,
  loadCredentials,
  toCredentialView,
  type Credential,
} from '../portfolioData';
import { SEED_ONTOLOGY_IDS } from '@classess/contracts';
import { MATH_SUBJECT_ID } from '../loopData';

const IDS = SEED_ONTOLOGY_IDS;

// ---------------------------------------------------------------------------
// d5 — content verification + filtering
// ---------------------------------------------------------------------------

describe('contentData — only verified content is servable (INVARIANT 7)', () => {
  it('marks only verified resources servable', () => {
    expect(isServable({ verification: 'verified' })).toBe(true);
    expect(isServable({ verification: 'needs-review' })).toBe(false);
    expect(isServable({ verification: 'generated' })).toBe(false);
  });

  it('filters to servable (verified) resources only', () => {
    const views = loadContent();
    const servable = filterResources(views, { onlyServable: true });
    expect(servable.length).toBeGreaterThan(0);
    expect(servable.every((v) => v.verification === 'verified')).toBe(true);
    // Filtering down never invents servable content.
    expect(servable.length).toBeLessThanOrEqual(views.length);
  });

  it('filters by subject and by free-text query', () => {
    const views = loadContent();
    const math = filterResources(views, { subjectId: MATH_SUBJECT_ID });
    expect(math.every((v) => v.subjectId === MATH_SUBJECT_ID)).toBe(true);
    const search = filterResources(views, { query: 'reflection' });
    expect(search.length).toBeGreaterThan(0);
    expect(
      search.every((v) => `${v.title} ${v.topicName} ${v.summary}`.toLowerCase().includes('reflection')),
    ).toBe(true);
  });

  it('reports a stat breakdown by verification state', () => {
    const stats = libraryStats(loadContent());
    expect(stats.total).toBe(stats.verified + stats.needsReview + stats.generated);
  });

  it('maps a resource to its ontology topic', () => {
    const r: ContentResource = {
      id: 'x',
      title: 'T',
      summary: 's',
      type: 'explanation',
      topicId: IDS.tTrigRatios,
      verification: 'verified',
      source: 'authored',
      provenance: 'p',
      licence: 'l',
      updated: 'u',
    };
    const v = toResourceView(r);
    expect(v.topicName).toMatch(/Trigonometric Ratios/i);
    expect(v.servable).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// d9 — inbox status transitions + the teacher -> student loop seam
// ---------------------------------------------------------------------------

describe('workData — the submission ladder (consequential, never auto)', () => {
  beforeEach(() => resetAssignedChecks());

  it('only allows the single legal next status from each state', () => {
    expect(canTransition('todo', 'in-progress')).toBe(true);
    expect(canTransition('in-progress', 'submitted')).toBe(true);
    // Cannot skip a rung (todo straight to submitted).
    expect(canTransition('todo', 'submitted')).toBe(false);
    // Submitted is terminal from the learner's side.
    expect(canTransition('submitted', 'in-progress')).toBe(false);
    expect(canTransition('returned', 'in-progress')).toBe(false);
  });

  it('exposes submit only when in progress', () => {
    expect(canSubmit('todo')).toBe(false);
    expect(canSubmit('in-progress')).toBe(true);
    expect(canSubmit('submitted')).toBe(false);
  });

  it('never silently jumps a rung on an illegal transition', () => {
    expect(applyTransition('todo', 'submitted')).toBe('todo');
    expect(applyTransition('todo', 'in-progress')).toBe('in-progress');
    expect(applyTransition('in-progress', 'submitted')).toBe('submitted');
  });

  it('makes a teacher-approved check appear in the student inbox as todo', () => {
    const before = loadInbox();
    pushAssignedCheck({ topicIds: [IDS.tTrigRatios], itemCount: 5 });
    const after = loadInbox();
    expect(after.length).toBe(before.length + 1);
    expect(after[0]!.status).toBe('todo');
    expect(after[0]!.kind).toBe('quick-check');
    expect(after[0]!.topicName).toMatch(/Trigonometric Ratios/i);
  });

  it('derives plain-language labels for an assignment', () => {
    const a: AssignmentItem = {
      id: 'a1',
      title: 'Check',
      kind: 'homework',
      topicId: IDS.tOhmsLaw,
      due: 'soon',
      status: 'returned',
      brief: 'b',
    };
    const v = toAssignmentView(a);
    expect(v.statusLabel).toMatch(/Returned/i);
    expect(v.kindLabel).toMatch(/Homework/i);
  });
});

// ---------------------------------------------------------------------------
// d14 — credentials: verifiable only when signed; issuing is laddered
// ---------------------------------------------------------------------------

describe('portfolioData — credentials are never faked as verified', () => {
  it('treats only a signed, verified credential as verifiable', () => {
    expect(isVerifiable({ state: 'verified', signable: true })).toBe(true);
    expect(isVerifiable({ state: 'verified', signable: false })).toBe(false);
    expect(isVerifiable({ state: 'draft', signable: true })).toBe(false);
    expect(isVerifiable({ state: 'revoked', signable: true })).toBe(false);
  });

  it('issues a draft to verified only when a signing key is configured', () => {
    const signable: Credential = {
      id: 'c1',
      title: 'T',
      claim: 'c',
      state: 'draft',
      topicIds: [IDS.tTrigRatios],
      issued: 'i',
      evidence: ['e'],
      signable: true,
    };
    const issued = issueCredential(toCredentialView(signable));
    expect(issued.state).toBe('verified');
    expect(issued.verifiable).toBe(true);
  });

  it('refuses to fake a signature when no signing key is configured', () => {
    const unsignable: Credential = {
      id: 'c2',
      title: 'T',
      claim: 'c',
      state: 'draft',
      topicIds: [IDS.tTrigRatios],
      issued: 'i',
      evidence: ['e'],
      signable: false,
    };
    const issued = issueCredential(toCredentialView(unsignable));
    expect(issued.state).toBe('draft');
    expect(issued.verifiable).toBe(false);
  });

  it('leaves an already-issued credential unchanged', () => {
    const verified = loadCredentials().find((c) => c.state === 'verified')!;
    expect(issueCredential(verified)).toEqual(verified);
  });
});
