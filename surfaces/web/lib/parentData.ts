/* ============================================================================
   lib/parentData.ts — typed mock data + child-switch logic for the Parent surface.

   The Parent surface is partnership and pride, never surveillance or fear. A
   parent sees only what consent permits (INVARIANT: consent gates every
   cross-context read; the Parent surface is the consent-authority and the
   partnership, never a watchtower). Behavioural data carries only the opaque
   canonical_uuid; nothing here is PII. Names are deliberately generic and
   fictional ("Child A", "Child B", "Section 10-B") per the confidentiality
   scrub. No real pricing, no codenames, no emoji, no exclamation marks.

   Everything a parent reads is in PLAIN LANGUAGE — never a raw number, score, or
   formula. Where a finding is shown, its evidence, the owner, and the "why am I
   seeing this" travel with it (explainable intelligence).

   The live data path is the gateway + event store (env vars named in
   lib/runtime.ts); these mocks are the graceful-degradation fallback the surface
   renders when no live keys or DB are present.
   ============================================================================ */

import type { SubjectAccent, Confidence } from '@classess/design-system';

/** A plain-language tone used for small status dots. Never a number. */
export type ParentTone = 'celebrate' | 'support' | 'steady';

/* ----------------------------------------------------------------------------
   Children — generic labels only. The Child switcher re-renders the whole
   surface for the selected child.
   ---------------------------------------------------------------------------- */

export interface ParentChild {
  /** Opaque, stable identifier — stands in for the canonical_uuid. Never PII. */
  id: string;
  /** Generic display label — never a real name. */
  label: string;
  /** The child's section, generic. */
  section: string;
  /**
   * Whether this child's school has shared a consented view with this parent.
   * When false, the surface shows the consent-gated state instead of data — a
   * parent sees only what consent permits.
   */
  consentGranted: boolean;
}

export const PARENT_CHILDREN: ParentChild[] = [
  { id: 'child-a', label: 'Child A', section: 'Section 10-B', consentGranted: true },
  { id: 'child-b', label: 'Child B', section: 'Section 7-A', consentGranted: true },
  { id: 'child-c', label: 'Child C', section: 'Section 4-C', consentGranted: false },
];

/* ----------------------------------------------------------------------------
   Today — three actions that need attention this week, in the parent's
   language. Calm. Each carries its why and the support it creates.
   ---------------------------------------------------------------------------- */

export interface ParentBriefing {
  id: string;
  /** The headline, in the parent's language. */
  title: string;
  /** The one next thing the parent can do. Supportive, never an order. */
  nextAction: string;
  /** Where the next action goes — a real, navigable page. Never a dead button. */
  target: string;
  /** A light time estimate. */
  minutes: number;
  /** Why this surfaced now — plain language, evidence-led. */
  why: string;
  /** What supporting this helps build. */
  builds: string;
  tone: ParentTone;
  /** How sure the school is, in plain bands — never a raw number. */
  confidence: Confidence;
  /** Who holds this at the school. */
  owner: string;
  /** When it helps most. Calm, never an order. */
  due: string;
  /** What gently slips if it is left — supportive, never alarming. */
  consequence: string;
  /** The evidence behind it, in the parent's language. */
  evidence: string[];
  /** Plain "why am I seeing this." */
  whySeeing: string;
}

/* ----------------------------------------------------------------------------
   The child view — one calm timeline per child: progress, strengths, support
   areas. Plain language throughout.
   ---------------------------------------------------------------------------- */

/**
 * What KIND of moment a timeline row is — the v2 child-record data points,
 * carried into v3 and re-expressed in plain language:
 *   · milestone     — something the child can now do on their own (a crossing).
 *   · observation   — a calm, dated note from the classroom (what was noticed).
 *   · intervention  — a PREPARED supportive step (waits for a human; never auto-fires).
 */
export type MomentKind = 'milestone' | 'observation' | 'intervention';

export interface TimelineMoment {
  id: string;
  when: string;
  title: string;
  detail: string;
  tone: ParentTone;
  subject: SubjectAccent;
  /** The kind of moment — drives the marker glyph + the row's plain label. */
  kind: MomentKind;
  /**
   * The evidence behind this moment, in the parent's language — what was
   * observed/corroborated, each with a human "when". Every conclusion on the
   * timeline carries a path to its evidence (explainable intelligence). A
   * milestone is corroborated across attempts, never a single score.
   */
  evidence: { text: string; when?: string }[];
  /** Plain "why am I seeing this" for the moment's evidence drawer. */
  whySeeing: string;
  /**
   * For a PREPARED intervention only — the supportive next step the school has
   * prepared, and who holds it. It waits; it never auto-sends.
   */
  prepared?: { step: string; owner: string };
  /** True for a milestone the child can now do unprompted — lights the marker. */
  independent?: boolean;
}

export interface PlainPoint {
  id: string;
  topic: string;
  subject: SubjectAccent;
  /** Plain-language description — never a number. */
  note: string;
  /** True when the child can now do this on their own (the ignite moment). */
  independent?: boolean;
}

/* ----------------------------------------------------------------------------
   Reports — assignments, exams & reports with parent-specific feedback,
   celebration points, and next steps. Published by a human (consequential
   actions never auto-fire); a parent reads what the school has chosen to share.
   ---------------------------------------------------------------------------- */

export interface ParentReport {
  id: string;
  title: string;
  subject: SubjectAccent;
  /** When the school shared this. */
  shared: string;
  /** Plain-language feedback written for the parent — never a raw mark. */
  feedback: string;
  /** A celebration point — pride, drawn from the child's own work. */
  celebration: string;
  /** A concrete, supportive next step. */
  nextStep: string;
  /** Who published it — a role, never a real name. */
  publishedBy: string;
}

/* ----------------------------------------------------------------------------
   Together — learn-alongside activities and PTM (parent-teacher meeting) prep.
   ---------------------------------------------------------------------------- */

export interface LearnAlongside {
  id: string;
  title: string;
  subject: SubjectAccent;
  minutes: number;
  /** What you do together, in plain language. */
  how: string;
  /** Why this helps right now. */
  why: string;
}

export interface PtmPrepItem {
  id: string;
  /** A plain-language talking point to bring to the meeting. */
  point: string;
  /** Why it matters — the evidence behind it, in the parent's language. */
  context: string;
}

export interface PtmMeeting {
  /** Whether a meeting is scheduled. Drives the empty vs scheduled state. */
  scheduled: boolean;
  when?: string;
  with?: string;
  prep: PtmPrepItem[];
}

/* ----------------------------------------------------------------------------
   The Proof artifact — a beautiful, shareable moment drawn from the child's
   own learning. Child-triggerable ("show what I just cracked"). The parent
   surface renders it with pride; nothing is shared without an explicit action.
   ---------------------------------------------------------------------------- */

export interface ProofArtifact {
  id: string;
  /** The moment, in the child's voice — short and proud. */
  headline: string;
  topic: string;
  subject: SubjectAccent;
  /** Plain-language statement of what changed — "can do this on their own". */
  whatChanged: string;
  /** When it happened. */
  when: string;
  /** True when this crossed into independent — lights the ignite signature. */
  independent: boolean;
}

/* ----------------------------------------------------------------------------
   Per-child data bundle. The whole surface re-renders from one of these when
   the Child switcher changes the selected child.
   ---------------------------------------------------------------------------- */

export interface ParentChildData {
  briefings: ParentBriefing[];
  timeline: TimelineMoment[];
  strengths: PlainPoint[];
  supportAreas: PlainPoint[];
  reports: ParentReport[];
  learnAlongside: LearnAlongside[];
  ptm: PtmMeeting;
  proof: ProofArtifact[];
}

const DATA_BY_CHILD: Record<string, ParentChildData> = {
  'child-a': {
    briefings: [
      {
        id: 'pa-b1',
        title: 'A short fractions warm-up would help before next week',
        nextAction: 'See a 15-minute activity',
        target: '/parent/together',
        minutes: 15,
        why: 'Child A is close on equivalent fractions and a little practice now keeps it steady before the next unit.',
        builds: 'A firm footing for the ratios work coming up.',
        tone: 'support',
        confidence: 'middle',
        owner: 'You, with the Class 10-B teacher',
        due: 'Before the next Mathematics unit',
        consequence: 'The new ratios work would feel harder without the warm-up first.',
        evidence: [
          'Two recent checks — close on equivalent fractions, with a small wobble on simplifying.',
          'The teacher noted a worked example still helps Child A get started.',
        ],
        whySeeing: 'A gentle heads-up before a new unit — shared because it is where a little home time helps most.',
      },
      {
        id: 'pa-b2',
        title: 'Child A did this on their own in Mathematics this week',
        nextAction: 'See the moment',
        target: '/parent/child',
        minutes: 3,
        why: 'Linear equations were solved cleanly without any prompts across two fresh checks.',
        builds: 'Confidence to take on harder problems independently.',
        tone: 'celebrate',
        confidence: 'high',
        owner: 'Class 10-B teacher',
        due: 'A win to enjoy — no action needed',
        consequence: 'Nothing slips. Noticing the win at home helps it stick.',
        evidence: [
          'Two fresh checks on linear equations — solved without any prompts.',
          'The independence read moved from supported to on their own.',
        ],
        whySeeing: 'Wins are shared too, not just the areas to support — this is a partnership, not a watch list.',
      },
      {
        id: 'pa-b3',
        title: 'A parent-teacher meeting is open to book',
        nextAction: 'See suggested times',
        target: '/parent/together',
        minutes: 5,
        why: 'The school has opened slots this fortnight and shared a short prep list with you.',
        builds: 'A shared plan between home and the classroom.',
        tone: 'steady',
        confidence: 'high',
        owner: 'Class 10-B teacher',
        due: 'Slots open this fortnight',
        consequence: 'The open slots may fill before a time that suits you is free.',
        evidence: [
          'The school opened meeting slots for this fortnight.',
          'A short prep list was shared so the conversation can be focused.',
        ],
        whySeeing: 'Shared so you can pick a time that works — booking is always your choice, never required.',
      },
    ],
    timeline: [
      {
        id: 'pa-t1',
        when: 'Today',
        title: 'Solved linear equations without help',
        detail: 'Two fresh checks, no prompts. This is now something Child A can do on their own.',
        tone: 'celebrate',
        subject: 'cobalt',
        kind: 'milestone',
        independent: true,
        evidence: [
          { text: 'Two linear-equation checks solved with no hints used.', when: 'Today' },
          { text: 'The independence read crossed from "with support" to "on their own".', when: 'This week' },
          { text: 'A milestone is confirmed across attempts — never from a single good day.' },
        ],
        whySeeing:
          'A milestone is a crossing the child can now do unprompted, corroborated over time — shared so a win at home can be celebrated out loud.',
      },
      {
        id: 'pa-t2',
        when: 'This week',
        title: 'A short fractions warm-up has been prepared',
        detail: 'Child A is close on equivalent fractions; a worked example to start still helps. A gentle home activity is ready for whenever it suits.',
        tone: 'support',
        subject: 'cobalt',
        kind: 'intervention',
        prepared: {
          step: 'A 15-minute fractions warm-up, prepared and waiting in Learn alongside.',
          owner: 'You, with the Section 10-B teacher',
        },
        evidence: [
          { text: 'Two recent checks — close on equivalent fractions, a small wobble on simplifying.', when: 'This week' },
          { text: 'The teacher noted a worked example still helps Child A get started.' },
        ],
        whySeeing:
          'A prepared step is supportive, not an order — it waits for you, and nothing is assigned or sent on its own.',
      },
      {
        id: 'pa-t3',
        when: 'Last week',
        title: 'Steady, reliable work in Science',
        detail: 'Photosynthesis is dependable when guided. Explaining it unprompted is the next small step.',
        tone: 'steady',
        subject: 'emerald',
        kind: 'observation',
        evidence: [
          { text: 'Guided Science tasks completed carefully and accurately.', when: 'Last week' },
          { text: 'A calm, dated note from the classroom — a pattern to notice, never a judgement.' },
        ],
        whySeeing:
          'An observation is a calm note of what was noticed in class — context for a conversation, not a verdict.',
      },
    ],
    strengths: [
      {
        id: 'pa-s1',
        topic: 'Linear equations',
        subject: 'cobalt',
        note: 'Solved cleanly on their own across two fresh checks.',
        independent: true,
      },
      {
        id: 'pa-s2',
        topic: 'Reading for meaning',
        subject: 'violet',
        note: 'Picks out the main idea reliably and explains it in their own words.',
        independent: true,
      },
    ],
    supportAreas: [
      {
        id: 'pa-u1',
        topic: 'Equivalent fractions',
        subject: 'cobalt',
        note: 'Comfortable with a worked example to start; building towards doing it unprompted.',
      },
      {
        id: 'pa-u2',
        topic: 'Explaining Science unprompted',
        subject: 'emerald',
        note: 'Reliable when guided. The next step is putting it into their own words without help.',
      },
    ],
    reports: [
      {
        id: 'pa-r1',
        title: 'Mathematics — unit check',
        subject: 'cobalt',
        shared: 'Shared two days ago',
        feedback:
          'Child A is moving from working with help towards working independently in algebra. Equations are now solved without prompts; fractions still benefit from a worked start.',
        celebration: 'Solved every linear-equation question without any help — a real step up.',
        nextStep: 'A short, weekly fractions warm-up at home would keep the momentum going.',
        publishedBy: 'Section 10-B teacher',
      },
      {
        id: 'pa-r2',
        title: 'Science — class assignment',
        subject: 'emerald',
        shared: 'Shared last week',
        feedback:
          'Strong, careful work when guided. The next growth is explaining ideas unprompted, in their own words.',
        celebration: 'Clear, well-organised answers when working through the guided steps.',
        nextStep: 'Ask Child A to teach you one idea from the lesson, with the book closed.',
        publishedBy: 'Section 10-B teacher',
      },
    ],
    learnAlongside: [
      {
        id: 'pa-l1',
        title: 'Fractions in the kitchen',
        subject: 'cobalt',
        minutes: 15,
        how: 'Halve and double a simple recipe together and talk through the equivalent amounts.',
        why: 'Turns equivalent fractions into something concrete, building towards doing it unprompted.',
      },
      {
        id: 'pa-l2',
        title: 'Teach-back, book closed',
        subject: 'emerald',
        minutes: 10,
        how: 'Ask Child A to explain photosynthesis to you in their own words, with the book closed.',
        why: 'Practises explaining unprompted — the exact next step in Science.',
      },
    ],
    ptm: {
      scheduled: true,
      when: 'This Thursday, afternoon slot',
      with: 'Section 10-B teacher',
      prep: [
        {
          id: 'pa-p1',
          point: 'Celebrate the move to independent work in algebra',
          context: 'Linear equations are now solved without prompts across two fresh checks.',
        },
        {
          id: 'pa-p2',
          point: 'Ask how to support unprompted explaining in Science',
          context: 'Child A is reliable when guided and is ready for the next small step.',
        },
        {
          id: 'pa-p3',
          point: 'Agree a light home routine for fractions',
          context: 'A short weekly warm-up would steady this before the ratios unit.',
        },
      ],
    },
    proof: [
      {
        id: 'pa-pr1',
        headline: 'I solved linear equations on my own',
        topic: 'Linear equations',
        subject: 'cobalt',
        whatChanged: 'Child A can now do this without any help — two clean checks, no prompts.',
        when: 'Today',
        independent: true,
      },
      {
        id: 'pa-pr2',
        headline: 'I explained the main idea in my own words',
        topic: 'Reading for meaning',
        subject: 'violet',
        whatChanged: 'Picked out and explained the main idea unprompted.',
        when: 'This week',
        independent: true,
      },
    ],
  },
  'child-b': {
    briefings: [
      {
        id: 'pb-b1',
        title: 'A little reading-aloud time would help this week',
        nextAction: 'See a 10-minute activity',
        target: '/parent/together',
        minutes: 10,
        why: 'Child B reads carefully and is building fluency; short, regular reading aloud helps it settle.',
        builds: 'Smoother, more confident reading across subjects.',
        tone: 'support',
        confidence: 'middle',
        owner: 'You, with the English teacher',
        due: 'A few short sessions this week',
        consequence: 'Fluency builds more slowly without the regular short practice.',
        evidence: [
          'Reading checks — careful and accurate, with pace still building.',
          'The teacher noted reading aloud at home settles fluency fastest.',
        ],
        whySeeing: 'A small, supportive nudge — shared because short home practice helps fluency most right now.',
      },
      {
        id: 'pb-b2',
        title: 'Child B cracked a tricky multiplication idea',
        nextAction: 'See the moment',
        target: '/parent/child',
        minutes: 3,
        why: 'Worked through a set of multiplication problems independently for the first time.',
        builds: 'A foundation for the division work ahead.',
        tone: 'celebrate',
        confidence: 'high',
        owner: 'Mathematics teacher',
        due: 'A win to enjoy — no action needed',
        consequence: 'Nothing slips. Noticing the win at home helps it stick.',
        evidence: [
          'A full set of multiplication problems worked through independently.',
          'First time without prompts — a clear step up from last fortnight.',
        ],
        whySeeing: 'Wins are shared too, not just the areas to support — this is a partnership, not a watch list.',
      },
      {
        id: 'pb-b3',
        title: 'No meeting is scheduled yet',
        nextAction: 'See how to request one',
        target: '/parent/together',
        minutes: 4,
        why: 'There is nothing urgent. You can request a meeting whenever it suits you.',
        builds: 'A connection between home and the classroom when you want it.',
        tone: 'steady',
        confidence: 'high',
        owner: 'You, whenever it suits',
        due: 'No deadline — entirely your choice',
        consequence: 'Nothing slips. A meeting is here for whenever you want one.',
        evidence: [
          'Nothing urgent is flagged for Child B this week.',
          'The school keeps meeting requests open all term.',
        ],
        whySeeing: 'Shown so the option is always visible — there is no pressure to act.',
      },
    ],
    timeline: [
      {
        id: 'pb-t1',
        when: 'Today',
        title: 'Worked through multiplication on their own',
        detail: 'A full set, unprompted. This is now something Child B can do independently.',
        tone: 'celebrate',
        subject: 'cobalt',
        kind: 'milestone',
        independent: true,
        evidence: [
          { text: 'A full multiplication set worked through with no prompts.', when: 'Today' },
          { text: 'First time unaided — a clear step up from last fortnight.', when: 'This fortnight' },
          { text: 'A milestone is confirmed across attempts, never a single lucky run.' },
        ],
        whySeeing:
          'A milestone is a crossing the child can now do on their own, corroborated over time — a real win to enjoy.',
      },
      {
        id: 'pb-t2',
        when: 'This week',
        title: 'A little reading-aloud practice is prepared',
        detail: 'Child B reads carefully and is building fluency. Short, regular reading aloud is ready for whenever it suits.',
        tone: 'support',
        subject: 'violet',
        kind: 'intervention',
        prepared: {
          step: 'A 10-minute reading-aloud routine, prepared and waiting in Learn alongside.',
          owner: 'You, with the English teacher',
        },
        evidence: [
          { text: 'Reading checks — careful and accurate, with pace still building.', when: 'This week' },
          { text: 'The teacher noted reading aloud at home settles fluency fastest.' },
        ],
        whySeeing:
          'A prepared step is supportive, not an order — it waits for you, and nothing is assigned on its own.',
      },
      {
        id: 'pb-t3',
        when: 'Last fortnight',
        title: 'Settling well into number work',
        detail: 'Approaches new number problems calmly and checks their own work — a lovely habit forming.',
        tone: 'steady',
        subject: 'cobalt',
        kind: 'observation',
        evidence: [
          { text: 'Number tasks attempted methodically, with self-checking noticed.', when: 'Last fortnight' },
          { text: 'A calm, dated note from the classroom — a pattern to notice, never a judgement.' },
        ],
        whySeeing:
          'An observation is a calm note of what was noticed in class — context for a conversation, not a verdict.',
      },
    ],
    strengths: [
      {
        id: 'pb-s1',
        topic: 'Multiplication facts',
        subject: 'cobalt',
        note: 'Worked through a full set on their own for the first time.',
        independent: true,
      },
    ],
    supportAreas: [
      {
        id: 'pb-u1',
        topic: 'Reading fluency',
        subject: 'violet',
        note: 'Accurate and careful; building towards smoother, more confident reading.',
      },
    ],
    reports: [
      {
        id: 'pb-r1',
        title: 'Mathematics — practice set',
        subject: 'cobalt',
        shared: 'Shared three days ago',
        feedback:
          'Child B is now confident with multiplication and ready to begin division. A lovely step into working independently.',
        celebration: 'Completed a whole multiplication set without any help.',
        nextStep: 'Short, playful number games at home will keep this fresh.',
        publishedBy: 'Section 7-A teacher',
      },
    ],
    learnAlongside: [
      {
        id: 'pb-l1',
        title: 'Five minutes of reading aloud',
        subject: 'violet',
        minutes: 10,
        how: 'Take turns reading a page aloud together each evening.',
        why: 'Regular practice builds the reading fluency Child B is working towards.',
      },
    ],
    ptm: {
      scheduled: false,
      prep: [],
    },
    proof: [
      {
        id: 'pb-pr1',
        headline: 'I did all my times tables on my own',
        topic: 'Multiplication facts',
        subject: 'cobalt',
        whatChanged: 'Child B can now work through multiplication independently.',
        when: 'Today',
        independent: true,
      },
    ],
  },
};

/* ----------------------------------------------------------------------------
   Child-switch logic — small, pure, and tested. Selecting a child returns the
   right child plus its data bundle; consent is honoured (no data leaks through
   for a child whose view has not been consented).
   ---------------------------------------------------------------------------- */

/** The id the surface opens on — the first child in the list. */
export const DEFAULT_CHILD_ID = PARENT_CHILDREN[0]?.id ?? '';

/** Find a child by id, returning undefined when the id is unknown. */
export function findChild(id: string): ParentChild | undefined {
  return PARENT_CHILDREN.find((c) => c.id === id);
}

/**
 * Resolve a requested child id to a concrete, valid selection. An unknown or
 * empty id falls back to the default child, so the switcher can never land the
 * surface on a blank selection.
 */
export function resolveChildId(requested: string | null | undefined): string {
  if (requested && findChild(requested)) return requested;
  return DEFAULT_CHILD_ID;
}

/**
 * The data the selected child's surface renders from. Consent is enforced here:
 * when a child's view has not been consented, no behavioural data is returned —
 * the surface shows the consent-gated state instead. A parent sees only what
 * consent permits.
 */
export function selectChildData(id: string): ParentChildData | null {
  const child = findChild(id);
  if (!child || !child.consentGranted) return null;
  return DATA_BY_CHILD[id] ?? null;
}

/** The tone word a parent reads for each plain-language status. */
export const TONE_PHRASE: Record<ParentTone, string> = {
  celebrate: 'Something to celebrate',
  support: 'A place to support',
  steady: 'Steady and on track',
};

/** Map a parent tone to a design-system Tag tone (no red-alarm framing). */
export const TONE_TAG: Record<ParentTone, 'success' | 'info' | 'neutral'> = {
  celebrate: 'success',
  support: 'info',
  steady: 'neutral',
};
