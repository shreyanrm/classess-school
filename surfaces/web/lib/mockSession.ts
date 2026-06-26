/* ============================================================================
   lib/mockSession.ts — the full sectioned-paper content for a mock-taking
   session, built so the student can sit a real board-shaped paper end to end.

   This is the LIVE-TAKING layer that sits under lib/mocksData.ts (the catalogue
   of blueprints). A blueprint says "where the weight sits"; a session says
   "here are the actual questions, in sections, with marks and a duration".

   v3 GRAMMAR (read this before editing):
     · A paper has a TOTAL and a DURATION and per-question MARKS — those are
       facts about the PAPER (the real exam carries them), so we show them.
     · The RESULT a student sees is NEVER a raw score or a percentage. The
       submit screen reports, in plain language, what they showed they can do
       and one clear next focus — the same evidence-first read every other
       student surface uses. Marks-attempted is framed as coverage, not a grade.
     · Confidentiality: generic content, opaque topic ids from the seed, no PII,
       no real board, no real pricing.

   Content is genuinely-static demo content kept in lib/ so every surface reads
   ONE coherent layer. The questions are tied to real seed topic ids so the
   review can name the topic a learner should revisit.
   ============================================================================ */

import { SEED_ONTOLOGY_IDS } from '@classess/contracts';
import { topicInfo } from './loopData';

const IDS = SEED_ONTOLOGY_IDS;

/** One multiple-choice question — four options, one correct index. */
export interface McqQuestion {
  kind: 'mcq';
  id: string;
  /** The opaque seed topic this question exercises (drives the review). */
  topicId: string;
  prompt: string;
  options: string[];
  /** The correct option index. Used only to read the attempt — never shown as a score. */
  correctIndex: number;
  marks: number;
}

/** One short-answer question — a free-text response, model answer for the review. */
export interface ShortQuestion {
  kind: 'short';
  id: string;
  topicId: string;
  prompt: string;
  /** A model answer, revealed in the review only — to learn from, not to grade against. */
  modelAnswer: string;
  marks: number;
}

export type MockQuestion = McqQuestion | ShortQuestion;

/** One section of the paper (e.g. "Section A — Objective"). */
export interface MockSection {
  id: string;
  /** "A", "B" … */
  letter: string;
  title: string;
  /** A short instruction line the real paper would carry. */
  instruction: string;
  questions: MockQuestion[];
}

/** A full, sittable paper. */
export interface MockPaper {
  blueprintId: string;
  subject: string;
  /** Minutes the real paper allows. */
  durationMinutes: number;
  sections: MockSection[];
}

/** Total marks across every section — derived, so it can never drift from the paper. */
export function paperTotalMarks(paper: MockPaper): number {
  return paper.sections.reduce(
    (sum, s) => sum + s.questions.reduce((q, item) => q + item.marks, 0),
    0,
  );
}

/** Every question across sections, in paper order — for the navigator and counts. */
export function paperQuestions(paper: MockPaper): MockQuestion[] {
  return paper.sections.flatMap((s) => s.questions);
}

// ---------------------------------------------------------------------------
// The papers. One per catalogue blueprint id (lib/mocksData). A paper that has
// no authored content falls back to the Mathematics paper shape so the session
// always has something real to sit.
// ---------------------------------------------------------------------------

const MATH_PAPER: MockPaper = {
  blueprintId: 'm1',
  subject: 'Mathematics',
  durationMinutes: 40,
  sections: [
    {
      id: 'm1-a',
      letter: 'A',
      title: 'Section A — Objective',
      instruction: 'Each question carries 1 mark. Choose the one best answer.',
      questions: [
        {
          kind: 'mcq',
          id: 'm1a1',
          topicId: IDS.tIrrational,
          prompt: 'Which of these is an irrational number?',
          options: ['0.75', '√2', '3/4', '−5'],
          correctIndex: 1,
          marks: 1,
        },
        {
          kind: 'mcq',
          id: 'm1a2',
          topicId: IDS.tPolyDegreeZeros,
          prompt: 'How many zeros does a quadratic polynomial have at most?',
          options: ['1', '2', '3', 'Unlimited'],
          correctIndex: 1,
          marks: 1,
        },
        {
          kind: 'mcq',
          id: 'm1a3',
          topicId: IDS.tTrigRatios,
          prompt: 'If sin θ = 3/5 in a right triangle, what is cos θ?',
          options: ['3/4', '4/5', '5/4', '5/3'],
          correctIndex: 1,
          marks: 1,
        },
        {
          kind: 'mcq',
          id: 'm1a4',
          topicId: IDS.tTrigRatios,
          prompt: 'The value of sin 30° + cos 60° is:',
          options: ['0', '1/2', '1', '2'],
          correctIndex: 2,
          marks: 1,
        },
      ],
    },
    {
      id: 'm1-b',
      letter: 'B',
      title: 'Section B — Short answer',
      instruction: 'Each question carries 3 marks. Show your working.',
      questions: [
        {
          kind: 'short',
          id: 'm1b1',
          topicId: IDS.tTrigRatios,
          prompt:
            'In a right triangle the side opposite an acute angle θ is 3 and the hypotenuse is 5. Find sin θ, cos θ and tan θ.',
          modelAnswer:
            'The third side is 4 (3² + 4² = 5²). So sin θ = 3/5, cos θ = 4/5, and tan θ = sin θ / cos θ = 3/4.',
          marks: 3,
        },
        {
          kind: 'short',
          id: 'm1b2',
          topicId: IDS.tPolyCoeffRel,
          prompt:
            'The zeros of a quadratic polynomial are 2 and −3. Write a polynomial with these zeros and state the sum and product of its zeros.',
          modelAnswer:
            'A polynomial is x² − (sum)x + (product) = x² + x − 6. Sum of zeros = 2 + (−3) = −1; product = 2 × (−3) = −6.',
          marks: 3,
        },
      ],
    },
  ],
};

const PHYS_PAPER: MockPaper = {
  blueprintId: 'm2',
  subject: 'Physics',
  durationMinutes: 35,
  sections: [
    {
      id: 'm2-a',
      letter: 'A',
      title: 'Section A — Objective',
      instruction: 'Each question carries 1 mark. Choose the one best answer.',
      questions: [
        {
          kind: 'mcq',
          id: 'm2a1',
          topicId: IDS.tReflectionLaws,
          prompt: 'The angle of incidence equals the angle of:',
          options: ['Refraction', 'Reflection', 'Deviation', 'Incidence doubled'],
          correctIndex: 1,
          marks: 1,
        },
        {
          kind: 'mcq',
          id: 'm2a2',
          topicId: IDS.tSphericalMirrors,
          prompt: 'A concave mirror forms a real, inverted image when the object is:',
          options: ['At the focus', 'Beyond the centre of curvature', 'Between pole and focus', 'At infinity only'],
          correctIndex: 1,
          marks: 1,
        },
        {
          kind: 'mcq',
          id: 'm2a3',
          topicId: IDS.tOhmsLaw,
          prompt: 'For a conductor at constant temperature, V is proportional to:',
          options: ['1/I', 'I²', 'I', '√I'],
          correctIndex: 2,
          marks: 1,
        },
      ],
    },
    {
      id: 'm2-b',
      letter: 'B',
      title: 'Section B — Short answer',
      instruction: 'Each question carries 3 marks. Show your working.',
      questions: [
        {
          kind: 'short',
          id: 'm2b1',
          topicId: IDS.tOhmsLaw,
          prompt:
            'A 6 V battery drives a current of 0.5 A through a resistor. State Ohm’s law and find the resistance.',
          modelAnswer:
            'Ohm’s law: V = IR at constant temperature. So R = V / I = 6 / 0.5 = 12 Ω.',
          marks: 3,
        },
        {
          kind: 'short',
          id: 'm2b2',
          topicId: IDS.tRefractionLaws,
          prompt:
            'Explain why a pencil appears bent when partly dipped in water. Name the phenomenon.',
          modelAnswer:
            'Light bends (refracts) as it passes between water and air because its speed changes; the rays from the submerged part reach the eye along a different direction, so the pencil looks displaced — the phenomenon is refraction.',
          marks: 3,
        },
      ],
    },
  ],
};

const PAPERS: Record<string, MockPaper> = {
  m1: MATH_PAPER,
  m2: PHYS_PAPER,
};

/** Resolve the sittable paper for a catalogue blueprint id (Maths shape on miss). */
export function paperForBlueprint(blueprintId: string): MockPaper {
  return PAPERS[blueprintId] ?? { ...MATH_PAPER, blueprintId };
}

// ---------------------------------------------------------------------------
// Reading a finished sitting — evidence-first, NEVER a raw score to the student.
// We compute the internal correct/attempted counts to find the topic that needs
// the most attention, then express the whole thing in plain language.
// ---------------------------------------------------------------------------

export type Responses = Record<string, number | string>;

/** A plain-language read of a sitting — bands and a next focus, never a mark. */
export interface MockReading {
  /** Of all questions, how many were attempted (engagement, framed as coverage). */
  attempted: number;
  total: number;
  /** A plain band for how the sitting went, never a percentage. */
  band: 'strong' | 'steady' | 'building';
  /** A warm headline. */
  headline: string;
  /** A plain-language paragraph. */
  read: string;
  /** The topic (by name) most worth revisiting next, if any. */
  nextFocusTopic?: string;
  nextFocusTopicId?: string;
  /** Per-question review rows — outcome + the topic, to learn from. */
  review: MockReviewRow[];
}

export interface MockReviewRow {
  id: string;
  section: string;
  prompt: string;
  topic: string;
  /** right | close | next — never a tick-vs-cross score line. */
  outcome: 'right' | 'close' | 'next' | 'skipped';
  /** For MCQ: the model option text; for short: the model answer. */
  model: string;
  marks: number;
}

/**
 * Read a sitting. For MCQ we know correctness; for short-answer (no auto-grade,
 * by design) we treat a substantive attempt as "close" — the student reflects
 * against the model answer rather than being machine-marked. This keeps the
 * permission ladder intact: the system proposes a read, it never sits in
 * judgement on free reasoning.
 */
export function readSitting(paper: MockPaper, responses: Responses): MockReading {
  const review: MockReviewRow[] = [];
  let attempted = 0;
  let mcqCorrect = 0;
  let mcqTotal = 0;
  const missByTopic = new Map<string, { id: string; weight: number }>();

  for (const section of paper.sections) {
    for (const q of section.questions) {
      const info = topicInfo(q.topicId);
      const given = responses[q.id];
      const hasResponse =
        q.kind === 'mcq'
          ? typeof given === 'number'
          : typeof given === 'string' && given.trim().length > 0;
      if (hasResponse) attempted += 1;

      let outcome: MockReviewRow['outcome'];
      let model: string;

      if (q.kind === 'mcq') {
        mcqTotal += 1;
        model = q.options[q.correctIndex] ?? '';
        if (!hasResponse) {
          outcome = 'skipped';
        } else if (given === q.correctIndex) {
          outcome = 'right';
          mcqCorrect += 1;
        } else {
          outcome = 'next';
          const cur = missByTopic.get(q.topicId);
          missByTopic.set(q.topicId, { id: q.topicId, weight: (cur?.weight ?? 0) + q.marks });
        }
      } else {
        model = q.modelAnswer;
        outcome = hasResponse ? 'close' : 'skipped';
        if (!hasResponse) {
          const cur = missByTopic.get(q.topicId);
          missByTopic.set(q.topicId, { id: q.topicId, weight: (cur?.weight ?? 0) + q.marks });
        }
      }

      review.push({
        id: q.id,
        section: section.letter,
        prompt: q.prompt,
        topic: info.name,
        outcome,
        model,
        marks: q.marks,
      });
    }
  }

  const total = review.length;
  // The band is read from the OBJECTIVE portion only (the part we can read
  // honestly), tempered by engagement — never surfaced as a number.
  const objectiveRatio = mcqTotal > 0 ? mcqCorrect / mcqTotal : attempted / Math.max(total, 1);
  const band: MockReading['band'] = objectiveRatio >= 0.75 ? 'strong' : objectiveRatio >= 0.45 ? 'steady' : 'building';

  // The single topic worth the most attention next.
  let nextFocusTopicId: string | undefined;
  let heaviest = 0;
  for (const { id, weight } of missByTopic.values()) {
    if (weight > heaviest) {
      heaviest = weight;
      nextFocusTopicId = id;
    }
  }
  const nextFocusTopic = nextFocusTopicId ? topicInfo(nextFocusTopicId).name : undefined;

  const headline =
    band === 'strong'
      ? 'A confident sitting'
      : band === 'steady'
        ? 'A solid, steady sitting'
        : 'A useful first pass';

  const read =
    band === 'strong'
      ? 'You moved through this paper with real command. The objective section landed cleanly; the short answers show you can reason it out under exam conditions.'
      : band === 'steady'
        ? 'You held the paper well. A few items are exactly the kind a short review would tidy up — and the short answers show your method is sound.'
        : 'This was a genuinely useful pass — sitting the real shape is half the work. A couple of ideas need another look, and that is exactly what the review below names.';

  return {
    attempted,
    total,
    band,
    headline,
    read,
    nextFocusTopic,
    nextFocusTopicId,
    review,
  };
}
