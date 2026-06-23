/* ============================================================================
   lib/portfolioData.ts — typed mock for the Learner Portfolio & Credentials
   (d14).

   Mirrors modules/learner-record (portfolio.py + credentials.py): a timeline of
   mastered topics with evidence artifacts (every artifact carries provenance —
   no artifact without evidence), and verifiable credentials with an explicit
   issue + verify state. A credential is `verified` only when actually signed;
   absent a signing key it is `draft` and explicitly NOT verifiable — never
   faked. Issuing a credential is CONSEQUENTIAL and permission-laddered.

   Everything a learner reads is PLAIN LANGUAGE — never a raw composite, score,
   or formula. Opaque ids only, no PII. The live path is the gateway + governed
   reads; this is the graceful-degradation fallback.
   ============================================================================ */

import { SEED_ONTOLOGY_IDS } from '@classess/contracts';
import type { SubjectAccent } from '@classess/design-system';
import type { ProofArtifact } from './parentData';
import { topicInfo } from './loopData';

const IDS = SEED_ONTOLOGY_IDS;

/* ----------------------------------------------------------------------------
   Timeline of mastered topics. Each moment links to its evidence (an artifact),
   reusing the shared ProofArtifact shape + the EvidenceDrawer on the page.
   ---------------------------------------------------------------------------- */

export interface MasteryMoment {
  id: string;
  topicId: string;
  /** Plain-language statement of what the learner can now do. Never a number. */
  plainLanguage: string;
  /** True when this crossed into independent — lights the ignite signature. */
  independent: boolean;
  when: string;
  /** The evidence lineage behind the moment — full, never an opaque claim. */
  evidence: string[];
  /** The shareable proof artifact for this moment (reuses ProofArtifact). */
  proof: ProofArtifact;
}

export interface MasteryMomentView extends MasteryMoment {
  topicName: string;
  subjectName: string;
  accent: SubjectAccent;
}

export function toMomentView(m: MasteryMoment): MasteryMomentView {
  const t = topicInfo(m.topicId);
  return {
    ...m,
    topicName: t.name,
    subjectName: t.subjectName,
    accent: t.accent,
  };
}

const TIMELINE: MasteryMoment[] = [
  {
    id: 'pm-1',
    topicId: IDS.tTrigRatios,
    plainLanguage: 'You can find the trigonometric ratios from a right triangle on your own.',
    independent: true,
    when: 'This week',
    evidence: [
      'Three independent attempts correct across fresh checks, no support used.',
      'A practice set finished without a guided start.',
    ],
    proof: {
      id: 'proof-trig',
      headline: 'I can work out the ratios from any right triangle now.',
      topic: 'Trigonometric ratios',
      subject: 'cobalt',
      whatChanged: 'You moved from needing a worked start to doing this unaided.',
      when: 'This week',
      independent: true,
    },
  },
  {
    id: 'pm-2',
    topicId: IDS.tPolyDegreeZeros,
    plainLanguage: 'You can find the degree and zeros of a polynomial, with the occasional check.',
    independent: false,
    when: 'Two weeks ago',
    evidence: [
      'Correct across recent attempts, a couple still checked against a worked example.',
      'A graph read paired correctly with the algebra.',
    ],
    proof: {
      id: 'proof-poly',
      headline: 'I can read a polynomial’s zeros off the graph and the algebra.',
      topic: 'Degree and zeros of a polynomial',
      subject: 'cobalt',
      whatChanged: 'You are reliable here, with a quick check now and then.',
      when: 'Two weeks ago',
      independent: false,
    },
  },
  {
    id: 'pm-3',
    topicId: IDS.tReflectionLaws,
    plainLanguage: 'You can state and apply the laws of reflection on your own.',
    independent: true,
    when: 'Last month',
    evidence: [
      'Stated the laws unprompted and applied them to a new surface.',
      'A clean independent check with no hints.',
    ],
    proof: {
      id: 'proof-reflection',
      headline: 'I can explain how light reflects without looking it up.',
      topic: 'Laws of reflection',
      subject: 'emerald',
      whatChanged: 'You moved from guided practice to explaining it yourself.',
      when: 'Last month',
      independent: true,
    },
  },
];

export function loadTimeline(store?: unknown): MasteryMomentView[] {
  try {
    const slice = (store as { portfolio?: { timeline?: MasteryMoment[] } } | undefined)?.portfolio
      ?.timeline;
    const seed = Array.isArray(slice) && slice.length > 0 ? slice : TIMELINE;
    return seed.map(toMomentView);
  } catch {
    return TIMELINE.map(toMomentView);
  }
}

/* ----------------------------------------------------------------------------
   Credentials — verifiable, portable, under the learner's control. The state
   mirrors learner-record CredentialState: draft (not verifiable) / verified
   (signed) / revoked. Issuing is consequential and permission-laddered.
   ---------------------------------------------------------------------------- */

export type CredentialState = 'draft' | 'verified' | 'revoked';

export const CREDENTIAL_STATE_LABEL: Record<CredentialState, string> = {
  draft: 'Draft — not yet verifiable',
  verified: 'Verified — tamper-evident',
  revoked: 'Withdrawn by you',
};

export interface Credential {
  id: string;
  title: string;
  /** What the credential attests, in plain language. */
  claim: string;
  state: CredentialState;
  /** The topics this credential draws on. */
  topicIds: string[];
  issued: string;
  /** The evidence lineage behind the claim — never an opaque badge. */
  evidence: string[];
  /**
   * Whether a signing key is configured. When false a credential can only be a
   * draft — we never fake a signature (INVARIANT: generate-and-verify spirit).
   */
  signable: boolean;
}

/**
 * Whether a credential is actually verifiable. Only a `verified` credential with
 * a real signature is — a draft is explicitly not, never faked.
 */
export function isVerifiable(c: Pick<Credential, 'state' | 'signable'>): boolean {
  return c.state === 'verified' && c.signable;
}

export interface CredentialView extends Credential {
  stateLabel: string;
  verifiable: boolean;
  topicNames: string[];
}

export function toCredentialView(c: Credential): CredentialView {
  return {
    ...c,
    stateLabel: CREDENTIAL_STATE_LABEL[c.state],
    verifiable: isVerifiable(c),
    topicNames: c.topicIds.map((id) => topicInfo(id).name),
  };
}

const CREDENTIALS: Credential[] = [
  {
    id: 'cr-1',
    title: 'Trigonometric ratios — independent',
    claim: 'Can find the trigonometric ratios of an acute angle from a right triangle, unaided.',
    state: 'verified',
    topicIds: [IDS.tTrigRatios],
    issued: 'Issued this week',
    evidence: [
      'Three independent demonstrations across fresh checks.',
      'Signed and tamper-evident — anyone you share it with can verify it.',
    ],
    signable: true,
  },
  {
    id: 'cr-2',
    title: 'Laws of reflection — independent',
    claim: 'Can state and apply the laws of reflection to a new surface, unaided.',
    state: 'verified',
    topicIds: [IDS.tReflectionLaws],
    issued: 'Issued last month',
    evidence: [
      'Stated and applied the laws unprompted on a fresh problem.',
      'Signed and tamper-evident.',
    ],
    signable: true,
  },
  {
    id: 'cr-3',
    title: 'Algebraic and trigonometric reasoning — ready to issue',
    claim: 'Reasons across polynomials and trigonometry to solve unfamiliar problems.',
    state: 'draft',
    topicIds: [IDS.tTrigRatios, IDS.tPolyDegreeZeros],
    issued: 'Prepared, awaiting your decision',
    evidence: [
      'Evidence is in place across both topics.',
      'Held as a draft until you choose to issue it — issuing is your decision.',
    ],
    signable: true,
  },
];

export function loadCredentials(store?: unknown): CredentialView[] {
  try {
    const slice = (store as { portfolio?: { credentials?: Credential[] } } | undefined)?.portfolio
      ?.credentials;
    const seed = Array.isArray(slice) && slice.length > 0 ? slice : CREDENTIALS;
    return seed.map(toCredentialView);
  } catch {
    return CREDENTIALS.map(toCredentialView);
  }
}

/**
 * Apply an issue decision to a draft credential, returning the next view. A
 * draft only becomes `verified` when a signing key is configured (`signable`);
 * otherwise it stays a draft — a signature is never faked. Returns the same
 * view when the credential is not a draft (already issued / revoked).
 */
export function issueCredential(c: CredentialView): CredentialView {
  if (c.state !== 'draft') return c;
  const next: CredentialState = c.signable ? 'verified' : 'draft';
  return toCredentialView({ ...c, state: next });
}
