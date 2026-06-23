/* ============================================================================
   lib/loopData.ts — typed Slice-1 scenario data for the Student <-> Teacher
   loop, built on the real ontology seed (Class 10, Mathematics + Physics).

   One class (Class 10-B), a roster of generic students (Student A..H), and a
   set of seed attempt/score events — a deliberate mix of independent and
   supported work — so lib/engine.ts can compute live mastery and gaps in the
   browser with no provider and no gateway.

   CONFIDENTIALITY: every learner is a generic label (Student A..H); every id is
   an opaque token from the seed. Nothing here is or derives from PII. The board
   is the neutral "Example State Board" from the seed — no real board lock-in.
   No real pricing appears.
   ============================================================================ */

import { SEED_ONTOLOGY, SEED_ONTOLOGY_IDS } from '@classess/contracts';
import type { AssistanceLevel, Edge } from '@classess/contracts';
import type { SubjectAccent } from '@classess/design-system';
import { computeMastery, type EngineEvent, type MasteryResult } from './engine';

const IDS = SEED_ONTOLOGY_IDS;

// ---------------------------------------------------------------------------
// The class and its roster. Opaque canonical refs, generic display labels.
// ---------------------------------------------------------------------------
export const CLASS_LABEL = 'Class 10-B';

export interface Student {
  /** Opaque canonical_uuid — the ONLY identity in behavioural data. */
  ref: string;
  /** Generic display label — never a real name (confidentiality scrub). */
  label: string;
}

/** A roster of eight generic students. Refs are opaque, deterministic tokens. */
export const ROSTER: Student[] = [
  { ref: 'a0000000-0000-4000-8000-00000000000a', label: 'Student A' },
  { ref: 'a0000000-0000-4000-8000-00000000000b', label: 'Student B' },
  { ref: 'a0000000-0000-4000-8000-00000000000c', label: 'Student C' },
  { ref: 'a0000000-0000-4000-8000-00000000000d', label: 'Student D' },
  { ref: 'a0000000-0000-4000-8000-00000000000e', label: 'Student E' },
  { ref: 'a0000000-0000-4000-8000-00000000000f', label: 'Student F' },
  { ref: 'a0000000-0000-4000-8000-000000000010', label: 'Student G' },
  { ref: 'a0000000-0000-4000-8000-000000000011', label: 'Student H' },
];

export function studentLabel(ref: string): string {
  return ROSTER.find((s) => s.ref === ref)?.label ?? 'Student';
}

/** The current student for the student-end pages — Student A. */
export const CURRENT_STUDENT = ROSTER[0]!;

// ---------------------------------------------------------------------------
// Topic + subject lookups over the seed, with display accents. Mathematics is
// cobalt, Physics is emerald — one vivid per surface, colour carries meaning.
// ---------------------------------------------------------------------------
export interface TopicInfo {
  id: string;
  name: string;
  subjectId: string;
  subjectName: string;
  accent: SubjectAccent;
  chapterName: string;
}

const SUBJECT_ACCENT: Record<string, SubjectAccent> = {
  [IDS.subjMath]: 'cobalt',
  [IDS.subjPhys]: 'emerald',
};

function buildTopicIndex(): Record<string, TopicInfo> {
  const chapterById = new Map(SEED_ONTOLOGY.chapters.map((c) => [c.id, c]));
  const unitById = new Map(SEED_ONTOLOGY.units.map((u) => [u.id, u]));
  const subjectById = new Map(SEED_ONTOLOGY.subjects.map((s) => [s.id, s]));
  const index: Record<string, TopicInfo> = {};
  for (const t of SEED_ONTOLOGY.topics) {
    const chapter = chapterById.get(t.chapter_id);
    const unit = chapter ? unitById.get(chapter.unit_id) : undefined;
    const subject = unit ? subjectById.get(unit.subject_id) : undefined;
    index[t.id] = {
      id: t.id,
      name: t.name,
      subjectId: subject?.id ?? '',
      subjectName: subject?.name ?? '',
      accent: subject ? (SUBJECT_ACCENT[subject.id] ?? 'cobalt') : 'cobalt',
      chapterName: chapter?.name ?? '',
    };
  }
  return index;
}

export const TOPIC_INDEX: Record<string, TopicInfo> = buildTopicIndex();

export function topicInfo(id: string): TopicInfo {
  return (
    TOPIC_INDEX[id] ?? {
      id,
      name: 'Topic',
      subjectId: '',
      subjectName: '',
      accent: 'cobalt',
      chapterName: '',
    }
  );
}

/** All topics for a subject, in sequence — for the blueprint-lite picker. */
export function topicsForSubject(subjectId: string): TopicInfo[] {
  return SEED_ONTOLOGY.topics
    .filter((t) => topicInfo(t.id).subjectId === subjectId)
    .map((t) => topicInfo(t.id));
}

export const MATH_SUBJECT_ID = IDS.subjMath;
export const PHYS_SUBJECT_ID = IDS.subjPhys;

/** The confirmed + proposed prerequisite edges from the seed, for the engine. */
export const EDGES: Edge[] = SEED_ONTOLOGY.edges;

/** The topic the live loop centres on: Trigonometric Ratios. */
export const LOOP_TOPIC_ID = IDS.tTrigRatios;
/** Its confirmed prerequisite for the prerequisite-gap path: Trig Identities depends on Ratios. */
export const LOOP_DEPENDENT_TOPIC_ID = IDS.tTrigIdentities;

// ---------------------------------------------------------------------------
// Seed event construction. Attempts and scores are immutable, append-only,
// attributed to an opaque canonical ref. Times are relative to a fixed "now"
// so the scenario is deterministic regardless of the wall clock.
// ---------------------------------------------------------------------------

/** A fixed reference instant the scenario is authored against. */
export const SCENARIO_NOW = Date.parse('2026-06-22T09:00:00.000Z');

const DAY = 86_400_000;

let seedSeq = 0;
function seedEventId(): string {
  seedSeq += 1;
  return `e0000000-0000-4000-8000-${String(seedSeq).padStart(12, '0')}`;
}

interface AttemptSpec {
  student: string;
  topicId: string;
  daysAgo: number;
  independent: boolean;
  assistance: AssistanceLevel;
  correct: boolean;
  score?: number;
  difficulty: number;
  timeMs: number;
}

function attempt(spec: AttemptSpec): EngineEvent {
  const occurred = new Date(SCENARIO_NOW - spec.daysAgo * DAY).toISOString();
  return {
    event_id: seedEventId(),
    occurred_at: occurred,
    canonical_uuid: spec.student,
    type: 'attempt.recorded',
    payload: {
      attempt_id: seedEventId(),
      ontology: { topic_id: spec.topicId },
      mode: spec.independent ? 'independent' : 'supported',
      assistance_level: spec.assistance,
      correct: spec.correct,
      score: spec.score,
      difficulty: spec.difficulty,
      time_taken_ms: spec.timeMs,
      attempt_number: 1,
    },
  };
}

const A = ROSTER[0]!.ref;
const B = ROSTER[1]!.ref;
const C = ROSTER[2]!.ref;
const D = ROSTER[3]!.ref;
const E = ROSTER[4]!.ref;
const F = ROSTER[5]!.ref;
const G = ROSTER[6]!.ref;
const H = ROSTER[7]!.ref;

/**
 * The seed attempt/score events — a hand-authored evidence trail across the
 * roster that produces a realistic spread of mastery bands and gap types when
 * replayed through lib/engine.ts. Each student tells one clear story:
 *
 *   A — support-dependency on Trig Ratios (strong with help, fails unaided).
 *   B — independent mastery on Trig Ratios (clean unaided successes).
 *   C — prerequisite gap on Trig Identities (weak here AND on Ratios).
 *   D — retention: secured Reflection long ago, evidence has decayed.
 *   E — accuracy slips on Ohm's Law (near-misses, method right).
 *   F — conceptual gap on Refraction (near-zero even with support).
 *   G — application gap on Spherical Mirrors (easy ok, harder items fail).
 *   H — speed gap on Polynomial zeros (correct but consistently slow).
 */
export const SEED_EVENTS: EngineEvent[] = [
  // A — support dependency on Trig Ratios.
  attempt({ student: A, topicId: IDS.tTrigRatios, daysAgo: 9, independent: false, assistance: 'Coach', correct: true, score: 0.9, difficulty: 0.5, timeMs: 60_000 }),
  attempt({ student: A, topicId: IDS.tTrigRatios, daysAgo: 6, independent: false, assistance: 'Hint', correct: true, score: 0.85, difficulty: 0.5, timeMs: 55_000 }),
  attempt({ student: A, topicId: IDS.tTrigRatios, daysAgo: 3, independent: true, assistance: 'Independent', correct: false, score: 0.3, difficulty: 0.5, timeMs: 70_000 }),
  // A — also secured Spherical Mirrors independently a while back, now decayed:
  // strong-but-stale, so the engine reads revision-due (feeds the revision plan).
  attempt({ student: A, topicId: IDS.tSphericalMirrors, daysAgo: 64, independent: true, assistance: 'Independent', correct: true, score: 0.95, difficulty: 0.5, timeMs: 42_000 }),
  attempt({ student: A, topicId: IDS.tSphericalMirrors, daysAgo: 58, independent: true, assistance: 'Independent', correct: true, score: 0.9, difficulty: 0.55, timeMs: 44_000 }),

  // B — independent mastery on Trig Ratios (clean, recent, unaided).
  attempt({ student: B, topicId: IDS.tTrigRatios, daysAgo: 5, independent: true, assistance: 'Independent', correct: true, score: 1, difficulty: 0.55, timeMs: 40_000 }),
  attempt({ student: B, topicId: IDS.tTrigRatios, daysAgo: 2, independent: true, assistance: 'Independent', correct: true, score: 1, difficulty: 0.6, timeMs: 38_000 }),
  attempt({ student: B, topicId: IDS.tTrigRatios, daysAgo: 0, independent: true, assistance: 'Independent', correct: true, score: 1, difficulty: 0.65, timeMs: 36_000 }),

  // C — prerequisite gap: weak on Trig Identities AND on its prerequisite Ratios.
  attempt({ student: C, topicId: IDS.tTrigRatios, daysAgo: 7, independent: true, assistance: 'Independent', correct: false, score: 0.4, difficulty: 0.4, timeMs: 65_000 }),
  attempt({ student: C, topicId: IDS.tTrigRatios, daysAgo: 5, independent: false, assistance: 'Hint', correct: false, score: 0.45, difficulty: 0.4, timeMs: 70_000 }),
  attempt({ student: C, topicId: IDS.tTrigIdentities, daysAgo: 3, independent: true, assistance: 'Independent', correct: false, score: 0.35, difficulty: 0.6, timeMs: 80_000 }),
  attempt({ student: C, topicId: IDS.tTrigIdentities, daysAgo: 2, independent: false, assistance: 'Coach', correct: false, score: 0.4, difficulty: 0.6, timeMs: 85_000 }),

  // D — retention: strong Reflection evidence, but old (decayed).
  attempt({ student: D, topicId: IDS.tReflectionLaws, daysAgo: 75, independent: true, assistance: 'Independent', correct: true, score: 0.95, difficulty: 0.5, timeMs: 45_000 }),
  attempt({ student: D, topicId: IDS.tReflectionLaws, daysAgo: 70, independent: true, assistance: 'Independent', correct: true, score: 0.9, difficulty: 0.5, timeMs: 47_000 }),

  // E — accuracy slips on Ohm's Law (near-misses, right method).
  attempt({ student: E, topicId: IDS.tOhmsLaw, daysAgo: 6, independent: true, assistance: 'Independent', correct: false, score: 0.7, difficulty: 0.5, timeMs: 50_000 }),
  attempt({ student: E, topicId: IDS.tOhmsLaw, daysAgo: 4, independent: true, assistance: 'Independent', correct: false, score: 0.75, difficulty: 0.5, timeMs: 52_000 }),
  attempt({ student: E, topicId: IDS.tOhmsLaw, daysAgo: 2, independent: true, assistance: 'Independent', correct: false, score: 0.8, difficulty: 0.6, timeMs: 48_000 }),

  // F — conceptual gap on Refraction (near-zero even with support).
  attempt({ student: F, topicId: IDS.tRefractionLaws, daysAgo: 6, independent: false, assistance: 'Coach', correct: false, score: 0.2, difficulty: 0.5, timeMs: 75_000 }),
  attempt({ student: F, topicId: IDS.tRefractionLaws, daysAgo: 3, independent: false, assistance: 'Coach', correct: false, score: 0.15, difficulty: 0.5, timeMs: 80_000 }),

  // G — application gap on Spherical Mirrors (easy ok, hard fails).
  attempt({ student: G, topicId: IDS.tSphericalMirrors, daysAgo: 7, independent: true, assistance: 'Independent', correct: true, score: 0.9, difficulty: 0.3, timeMs: 40_000 }),
  attempt({ student: G, topicId: IDS.tSphericalMirrors, daysAgo: 4, independent: true, assistance: 'Independent', correct: false, score: 0.3, difficulty: 0.8, timeMs: 90_000 }),
  attempt({ student: G, topicId: IDS.tSphericalMirrors, daysAgo: 2, independent: true, assistance: 'Independent', correct: false, score: 0.35, difficulty: 0.7, timeMs: 88_000 }),

  // H — speed gap on Polynomial zeros (correct but slow).
  attempt({ student: H, topicId: IDS.tPolyDegreeZeros, daysAgo: 5, independent: true, assistance: 'Independent', correct: true, score: 1, difficulty: 0.5, timeMs: 120_000 }),
  attempt({ student: H, topicId: IDS.tPolyDegreeZeros, daysAgo: 3, independent: true, assistance: 'Independent', correct: true, score: 1, difficulty: 0.5, timeMs: 110_000 }),
];

// ---------------------------------------------------------------------------
// Derived reads — every surface AND Vidya read ONE coherent layer. Rather than
// hardcode "revision due" lists per page, derive them from the SAME engine
// (computeMastery) over the SAME seed events, at the SAME SCENARIO_NOW. A topic
// is revision-due when strong-but-stale evidence has aged (engine.revisionDue),
// so the student mocks page reads identically to /student/progress and Vidya.
// ---------------------------------------------------------------------------

/** One revision item, derived from the engine — plain language, never a score. */
export interface RevisionItem {
  topicId: string;
  topic: string;
  subject: string;
  /** When to touch it — sooner if the read is independent (more worth keeping). */
  when: string;
  /** A calm, plain-language reason, shaped by the engine read. */
  why: string;
  /** Urgent when it was an independent demonstration that is now fading. */
  urgent: boolean;
}

/** The ordered list of topics the learner has evidence on, for derivations. */
function topicsWithEvidenceFor(student: string): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const ev of SEED_EVENTS) {
    if (ev.canonical_uuid !== student) continue;
    const topicId = ev.type === 'attempt.recorded' ? ev.payload.ontology.topic_id : ev.payload.ontology.topic_id;
    if (!seen.has(topicId)) {
      seen.add(topicId);
      ordered.push(topicId);
    }
  }
  return ordered;
}

/**
 * Derive the spaced-revision plan for a student from the engine. Surfaces a
 * topic only when the engine says revision is genuinely due (decayed evidence),
 * never on a fixed nag timer. Pure + deterministic at SCENARIO_NOW.
 */
export function studentRevisionPlan(student: string = CURRENT_STUDENT.ref): RevisionItem[] {
  const items: RevisionItem[] = [];
  for (const topicId of topicsWithEvidenceFor(student)) {
    const m: MasteryResult = computeMastery(SEED_EVENTS, student, topicId, SCENARIO_NOW);
    if (!m.revisionDue) continue;
    const info = topicInfo(topicId);
    const urgent = m.reading.independent || m.reading.band === 'secure';
    items.push({
      topicId,
      topic: info.name,
      subject: info.subjectName,
      when: urgent ? 'Today' : 'This weekend',
      why: urgent
        ? 'You had this solid, and it is starting to fade — a short review now keeps it.'
        : 'On your natural forgetting curve for this. No rush, just a touch-up.',
      urgent,
    });
  }
  // Urgent first; otherwise keep the evidence order so it is stable.
  return items.sort((a, b) => Number(b.urgent) - Number(a.urgent));
}

/** A fresh, opaque event id for events produced live in the loop or practice. */
let liveSeq = 0;
export function liveEventId(): string {
  liveSeq += 1;
  return `11ee0000-0000-4000-8000-${String(liveSeq).padStart(12, '0')}`;
}

export type { EngineEvent } from './engine';
