/* ============================================================================
   lib/vizData.ts — the SHARED visualization + report DATA layer.

   Every reusable viz the v2->v3 experience map needs (attendance heatmap,
   holistic progress card, project rubric, paper analysis, Bloom distribution,
   performance trend, success-probability gauge, calendar, timetable) reads its
   data from HERE. The components themselves are pure + data-driven (they take
   data props only); this module owns the SHAPES + the PII-free fallback seed.

   Where the v2 experience needs data points v3 doesn't have yet (attendance
   history, Bloom distribution, rubric scores, timetable, leave records), they
   are ADDED here as PII-free mock shapes so the viz renders real-shaped data
   with an OBSERVABLE fallback. The live path is gateway-first (lib/vizReads +
   /api/viz); these seeds are the graceful-degradation read, surfaced honestly
   with a SourceNote on every consuming surface.

   Confidentiality: every label is generic + fictional (Student A, Section 10-B,
   Campus North). No real personal names, no orchestrator/board lock-in, no real
   pricing. Mastery is expressed as plain-language BANDS (independent vs
   supported) and target bands (below/on/above) — never a raw single score
   shown to students or parents. The six-dimension rubric reasoning is the
   teacher-only diagnostic lens.
   ============================================================================ */

import type { SubjectAccent, Confidence } from '@classess/design-system';

/** What source actually answered a viz read — surfaced for the SourceNote. */
export type ReadSource = 'gateway' | 'fallback';

/* ---------------------------------------------------------------------------
   1) ATTENDANCE — the month x day heatmap states + history.
   Cool/brand hues only; no warm-orange. The per-day state is the calm,
   non-punitive read (present / half / leave / absent / holiday / future).
   --------------------------------------------------------------------------- */

export type AttendanceState =
  | 'present'
  | 'half'
  | 'leave'
  | 'absent'
  | 'holiday'
  | 'weekend'
  | 'future'
  | 'none';

/** One calendar month of per-day states for one row (a student, or a class). */
export interface AttendanceMonth {
  /** A short month label — "Apr", "May". The grid never needs the year. */
  label: string;
  /** Day-of-month index 1..N as the array index 0..N-1; each is a state. */
  days: AttendanceState[];
  /** The weekday (0=Sun..6=Sat) the 1st of this month falls on, for alignment. */
  startWeekday: number;
}

/** A full-history attendance read for one row (the heatmap's data prop). */
export interface AttendanceRecord {
  /** Generic, fictional row label — "Student A", "Section 10-B". */
  rowLabel: string;
  months: AttendanceMonth[];
  /** Plain counts behind the per-row %, never a single opaque figure. */
  counts: {
    present: number;
    half: number;
    leave: number;
    absent: number;
    /** School days that have occurred (the % denominator). */
    schoolDays: number;
  };
  /** A short, plain-language read of the pattern — calm, never alarming. */
  note: string;
}

/** Build a month of mostly-present days with a few seeded exceptions. */
function seedMonth(
  label: string,
  days: number,
  startWeekday: number,
  exceptions: Record<number, AttendanceState>,
  futureFrom?: number,
): AttendanceMonth {
  const out: AttendanceState[] = [];
  for (let d = 1; d <= days; d++) {
    const weekday = (startWeekday + (d - 1)) % 7;
    if (futureFrom != null && d >= futureFrom) {
      out.push('future');
    } else if (exceptions[d]) {
      out.push(exceptions[d]!);
    } else if (weekday === 0) {
      out.push('weekend');
    } else {
      out.push('present');
    }
  }
  return { label, days: out, startWeekday };
}

/** The fallback attendance record — one student's term, ~92% present. PII-free. */
export const ATTENDANCE_FALLBACK: AttendanceRecord = {
  rowLabel: 'Student A',
  months: [
    seedMonth('Apr', 30, 2, { 4: 'holiday', 11: 'absent', 18: 'leave', 25: 'half' }),
    seedMonth('May', 31, 5, { 1: 'holiday', 9: 'absent', 10: 'absent', 22: 'half', 30: 'leave' }),
    seedMonth('Jun', 30, 1, { 5: 'half', 16: 'leave', 20: 'holiday' }, 26),
  ],
  counts: { present: 58, half: 3, leave: 3, absent: 4, schoolDays: 68 },
  note: 'Steady attendance through the term. Two absences fell on the same week in May — worth a calm check-in, not a concern on its own.',
};

/* ---------------------------------------------------------------------------
   2) HOLISTIC PROGRESS — the report card's composite read.
   Competency distribution (plain bands), foundational literacy/numeracy bars,
   a performance trend, attendance analytics, observations + interventions.
   --------------------------------------------------------------------------- */

/** A competency slice for the distribution donut — plain band, never a grade. */
export interface CompetencySlice {
  /** Plain-language band — "Independent", "Proficient", "Emerging", "Beginning". */
  band: string;
  /** How many topics sit in this band (the slice weight). */
  count: number;
  /** The slice hue — a cool/brand subject accent (never warm-orange). */
  accent: SubjectAccent;
}

/** A foundational literacy / numeracy strand — a 0..1 strength + plain read. */
export interface FoundationalStrand {
  label: string;
  /** 0..1 — drives the bar width; never shown as a bare number to learners. */
  strength: number;
  read: string;
}

/** A single point on the performance trend — plain direction, no marks shown. */
export interface TrendPoint {
  /** A short period label — "T1", "Apr", "Unit 3". */
  label: string;
  /** 0..100 share working independently at this reading (shape, not a grade). */
  value: number;
}

/** A teacher observation or a prepared intervention — evidence-first. */
export interface ObservationLine {
  text: string;
  /** "observation" reads calm; "intervention" is a prepared, approvable step. */
  kind: 'strength' | 'focus' | 'intervention';
}

export interface HolisticProgress {
  /** Generic, fictional — "Student A", "Section 10-B". */
  subjectLabel: string;
  classLabel: string;
  term: string;
  /** A plain-language executive summary — no raw score, no judgement. */
  summary: string;
  competencies: CompetencySlice[];
  foundational: FoundationalStrand[];
  trend: TrendPoint[];
  /** Attendance analytics — the same counts the heatmap reads from. */
  attendance: {
    present: number;
    absent: number;
    half: number;
    leave: number;
    schoolDays: number;
  };
  observations: ObservationLine[];
  /** The verification confidence behind the whole read — a band, never a score. */
  confidence: Confidence;
}

export const HOLISTIC_FALLBACK: HolisticProgress = {
  subjectLabel: 'Student A',
  classLabel: 'Section 10-B',
  term: 'Term 1',
  summary:
    'Working on their own across most of Mathematics and English, and reliably with light guidance in Science. The clearest next step is moving from "can do with help" to "can do alone" on photosynthesis.',
  competencies: [
    { band: 'Independent', count: 9, accent: 'cobalt' },
    { band: 'Proficient', count: 6, accent: 'emerald' },
    { band: 'Emerging', count: 3, accent: 'violet' },
    { band: 'Beginning', count: 2, accent: 'indigo' },
  ],
  foundational: [
    { label: 'Reading', strength: 0.82, read: 'Reads grade-level texts unaided and explains the gist.' },
    { label: 'Writing', strength: 0.68, read: 'Structures a paragraph with support; tense use is still settling.' },
    { label: 'Numeracy', strength: 0.88, read: 'Fluent with operations and equivalent fractions on their own.' },
    { label: 'Reasoning', strength: 0.74, read: 'Strong on routine problems; multi-step reasoning is building.' },
  ],
  trend: [
    { label: 'Apr', value: 48 },
    { label: 'May', value: 57 },
    { label: 'Jun', value: 64 },
    { label: 'Now', value: 71 },
  ],
  attendance: { present: 58, absent: 4, half: 3, leave: 3, schoolDays: 68 },
  observations: [
    { kind: 'strength', text: 'Starts independent tasks without waiting to be prompted.' },
    { kind: 'strength', text: 'Asks precise questions when genuinely stuck — a sign of self-monitoring.' },
    { kind: 'focus', text: 'Photosynthesis: reliable with a worked start, not yet unprompted.' },
    {
      kind: 'intervention',
      text: 'A short scaffolded-autonomy task in Science, prepared for your approval — it waits, it never auto-sends.',
    },
  ],
  confidence: 'high',
};

/* ---------------------------------------------------------------------------
   3) PROJECT RUBRIC — the six-dimension criteria x Level 1-4 grid + submission
   tracking. Teacher-only diagnostic lens (the six dimensions); never shown raw
   to a student/parent.
   --------------------------------------------------------------------------- */

/** One rubric criterion — six per project — with its four level descriptors. */
export interface RubricCriterion {
  label: string;
  /** Four plain descriptors, Level 1 (lowest) .. Level 4 (highest). */
  levels: [string, string, string, string];
  /** The awarded level (1..4), or null when not yet evaluated. */
  awarded: 1 | 2 | 3 | 4 | null;
}

/** A submission row in the project's tracking grid. PII-free, generic labels. */
export interface SubmissionRow {
  label: string;
  status: 'submitted' | 'in-progress' | 'not-submitted';
  /** A short, human "when" token — "Submitted Tue", "Due Fri". */
  when: string;
}

export interface ProjectRubric {
  title: string;
  classLabel: string;
  subject: SubjectAccent;
  criteria: RubricCriterion[];
  submissions: SubmissionRow[];
  confidence: Confidence;
}

export const RUBRIC_FALLBACK: ProjectRubric = {
  title: 'Water in our city — investigation',
  classLabel: 'Section 10-B',
  subject: 'emerald',
  criteria: [
    {
      label: 'Inquiry & question',
      levels: ['Question unclear', 'Question stated', 'Focused, testable question', 'Original, well-scoped question'],
      awarded: 3,
    },
    {
      label: 'Evidence & method',
      levels: ['Little evidence', 'Some evidence', 'Relevant evidence, sound method', 'Strong, well-triangulated evidence'],
      awarded: 3,
    },
    {
      label: 'Analysis & reasoning',
      levels: ['Describes only', 'Begins to explain', 'Explains with reasoning', 'Reasons across sources'],
      awarded: 2,
    },
    {
      label: 'Communication',
      levels: ['Hard to follow', 'Mostly clear', 'Clear and structured', 'Compelling and precise'],
      awarded: 4,
    },
    {
      label: 'Collaboration',
      levels: ['Worked alone', 'Some sharing', 'Contributed fairly', 'Lifted the whole team'],
      awarded: 3,
    },
    {
      label: 'Independence',
      levels: ['Needed steps given', 'Needed prompts', 'Mostly self-directed', 'Fully self-directed'],
      awarded: 2,
    },
  ],
  submissions: [
    { label: 'Student A', status: 'submitted', when: 'Submitted Tue' },
    { label: 'Student B', status: 'submitted', when: 'Submitted Mon' },
    { label: 'Student C', status: 'in-progress', when: 'Draft saved' },
    { label: 'Student D', status: 'submitted', when: 'Submitted Wed' },
    { label: 'Student E', status: 'not-submitted', when: 'Due Fri' },
    { label: 'Student F', status: 'submitted', when: 'Submitted Tue' },
  ],
  confidence: 'middle',
};

/* ---------------------------------------------------------------------------
   4) PAPER ANALYSIS — target-band distribution (below/on/above) + per-period
   breakdown + remedial grouping. Bands, never raw marks shown to learners.
   --------------------------------------------------------------------------- */

export type TargetBand = 'below' | 'on' | 'above';

/** The overall + per-period target-band counts for one assessment. */
export interface BandDistribution {
  below: number;
  on: number;
  above: number;
}

/** One period (section / topic) within the paper, with its own distribution. */
export interface PaperPeriod {
  label: string;
  subject: SubjectAccent;
  distribution: BandDistribution;
  /** A short plain read of where this period landed. */
  note: string;
}

/** A prepared remedial group — who, on what, the prepared next step. PII-free. */
export interface RemedialGroup {
  topic: string;
  subject: SubjectAccent;
  /** Generic member labels — "Student A", "Student C". */
  members: string[];
  /** The prepared step — approvable, never auto-fired. */
  preparedStep: string;
}

export interface PaperAnalysis {
  title: string;
  classLabel: string;
  total: number;
  overall: BandDistribution;
  periods: PaperPeriod[];
  remedial: RemedialGroup[];
  confidence: Confidence;
}

export const PAPER_FALLBACK: PaperAnalysis = {
  title: 'Periodic check — Unit 3',
  classLabel: 'Section 10-B',
  total: 31,
  overall: { below: 6, on: 17, above: 8 },
  periods: [
    {
      label: 'Equivalent fractions',
      subject: 'cobalt',
      distribution: { below: 6, on: 18, above: 7 },
      note: 'The below-target group is the same six flagged on the prerequisite check.',
    },
    {
      label: 'Photosynthesis',
      subject: 'emerald',
      distribution: { below: 4, on: 20, above: 7 },
      note: 'Most are reliable with guidance; few are independent yet.',
    },
    {
      label: 'Tenses in writing',
      subject: 'violet',
      distribution: { below: 8, on: 16, above: 7 },
      note: 'Scaffolded practice is recommended for the below-target group.',
    },
  ],
  remedial: [
    {
      topic: 'Equivalent fractions',
      subject: 'cobalt',
      members: ['Student A', 'Student C', 'Student E'],
      preparedStep: 'A 15-minute fractions reset, prepared for your approval before the ratios unit.',
    },
    {
      topic: 'Tenses in writing',
      subject: 'violet',
      members: ['Student B', 'Student D'],
      preparedStep: 'A scaffolded tense-practice set, prepared and waiting for you.',
    },
  ],
  confidence: 'high',
};

/* ---------------------------------------------------------------------------
   5) BLOOM DISTRIBUTION + PERFORMANCE TREND + SUCCESS PROBABILITY.
   Bloom is a donut of cognitive levels; the trend reuses TrendPoint; the gauge
   is an honest probability (direction, not a promise) — for students it is
   re-expressed as a plain READ, never a percentage.
   --------------------------------------------------------------------------- */

/** One Bloom cognitive level slice. Cool/brand hues only. */
export interface BloomSlice {
  /** "Remembering", "Understanding", "Applying", "Analysing", "Creating". */
  level: string;
  /** The share of demonstrated work at this level (0..100, sums to ~100). */
  share: number;
  accent: SubjectAccent;
}

export interface BloomDistribution {
  topicLabel: string;
  slices: BloomSlice[];
  read: string;
  confidence: Confidence;
}

export const BLOOM_FALLBACK: BloomDistribution = {
  topicLabel: 'Across this term',
  slices: [
    { level: 'Remembering', share: 22, accent: 'cobalt' },
    { level: 'Understanding', share: 28, accent: 'cyan' },
    { level: 'Applying', share: 24, accent: 'emerald' },
    { level: 'Analysing', share: 16, accent: 'violet' },
    { level: 'Creating', share: 10, accent: 'indigo' },
  ],
  read: 'Most demonstrated work sits at understanding and applying. The next stretch is more analysing — asking "why" and "what if", not just "what".',
  confidence: 'middle',
};

/** A success-probability read — an honest direction, recalculated as evidence
 *  arrives. For students it renders as a plain READ; the % is teacher/parent. */
export interface SuccessProbability {
  /** 0..1 — drives the gauge arc. Never shown bare to a student. */
  probability: number;
  /** The plain-language read — what the shape means, calm and honest. */
  read: string;
  /** What lifts it fastest — the actionable lever. */
  lever: string;
  confidence: Confidence;
}

export const SUCCESS_FALLBACK: SuccessProbability = {
  probability: 0.78,
  read: 'On the current pace, reaching a steady independent standing by term end is likely — not certain. It recalculates as fresh evidence arrives.',
  lever: 'Closing the photosynthesis support-dependency lifts the predicted tail fastest.',
  confidence: 'middle',
};

/** A standalone performance trend (actual + plain read) for the line chart. */
export interface PerformanceTrend {
  topicLabel: string;
  points: TrendPoint[];
  /** The predicted continuation (dotted) — a direction, never a promise. */
  predicted: TrendPoint[];
  read: string;
}

export const TREND_FALLBACK: PerformanceTrend = {
  topicLabel: 'Independence — this term',
  points: [
    { label: 'Apr', value: 48 },
    { label: 'May', value: 57 },
    { label: 'Jun', value: 64 },
    { label: 'Now', value: 71 },
  ],
  predicted: [
    { label: 'Now', value: 71 },
    { label: 'Jul', value: 76 },
    { label: 'Aug', value: 80 },
    { label: 'Term end', value: 84 },
  ],
  read: 'The shape is rising steadily. The dotted line projects the same trend forward; it shifts as time and weightage change.',
};

/* ---------------------------------------------------------------------------
   6) CALENDAR + TIMETABLE — a monthly event grid + a weekly period grid.
   Event types are cool/brand coded; never a warm-orange.
   --------------------------------------------------------------------------- */

export type EventType = 'exam' | 'ptm' | 'holiday' | 'homework' | 'activity';

/** One dated event on the monthly calendar. PII-free. */
export interface CalendarEvent {
  /** Day-of-month (1..N). */
  day: number;
  type: EventType;
  label: string;
}

export interface CalendarMonth {
  label: string;
  /** Days in the month. */
  days: number;
  /** Weekday (0=Sun..6=Sat) of the 1st. */
  startWeekday: number;
  events: CalendarEvent[];
}

export const CALENDAR_FALLBACK: CalendarMonth = {
  label: 'June',
  days: 30,
  startWeekday: 1,
  events: [
    { day: 5, type: 'homework', label: 'Fractions worksheet due' },
    { day: 11, type: 'exam', label: 'Periodic check — Unit 3' },
    { day: 16, type: 'ptm', label: 'Parent-teacher meeting' },
    { day: 20, type: 'holiday', label: 'School holiday' },
    { day: 24, type: 'activity', label: 'Science investigation showcase' },
    { day: 27, type: 'homework', label: 'Tense practice due' },
  ],
};

/** One block in the weekly timetable — a period at a day x time slot. */
export interface TimetableBlock {
  /** 0=Mon..5=Sat (the grid columns). */
  day: number;
  /** Row index into the period times array. */
  period: number;
  subject: SubjectAccent;
  label: string;
  /** Optional room / detail — generic, no PII. */
  detail?: string;
}

export interface Timetable {
  /** Day column headers — "Mon".."Sat". */
  dayLabels: string[];
  /** Period row labels — the time bands. */
  periodLabels: string[];
  blocks: TimetableBlock[];
}

export const TIMETABLE_FALLBACK: Timetable = {
  dayLabels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
  periodLabels: ['08:30', '09:30', '10:45', '11:45', '13:30'],
  blocks: [
    { day: 0, period: 0, subject: 'cobalt', label: 'Mathematics', detail: 'Room 12' },
    { day: 0, period: 1, subject: 'emerald', label: 'Science', detail: 'Lab 2' },
    { day: 0, period: 3, subject: 'violet', label: 'English', detail: 'Room 12' },
    { day: 1, period: 0, subject: 'indigo', label: 'Social Studies', detail: 'Room 9' },
    { day: 1, period: 2, subject: 'cobalt', label: 'Mathematics', detail: 'Room 12' },
    { day: 2, period: 1, subject: 'emerald', label: 'Science', detail: 'Lab 2' },
    { day: 2, period: 4, subject: 'violet', label: 'English', detail: 'Room 12' },
    { day: 3, period: 0, subject: 'cobalt', label: 'Mathematics', detail: 'Room 12' },
    { day: 3, period: 3, subject: 'indigo', label: 'Social Studies', detail: 'Room 9' },
    { day: 4, period: 1, subject: 'emerald', label: 'Science', detail: 'Lab 2' },
    { day: 4, period: 2, subject: 'violet', label: 'English', detail: 'Room 12' },
  ],
};

/* ---------------------------------------------------------------------------
   7) ASSIGNMENTS — the chapter-grouped assignment list (Homework / Quiz /
   Project), with submissions % (from plain counts, never a single figure), a
   due token, and a calm published/awaiting/closed status. The v2 "Assignments
   by chapter" tracker, in the v3 grammar: bands of completion, not a raw mark.
   --------------------------------------------------------------------------- */

export type AssignmentKind = 'homework' | 'quiz' | 'project';
export type AssignmentStatus = 'awaiting' | 'in-window' | 'closed';

/** One assignment row in the chapter-grouped list. PII-free, generic labels. */
export interface AssignmentRow {
  id: string;
  title: string;
  kind: AssignmentKind;
  subject: SubjectAccent;
  /** A short, human "when" token — "Due Fri", "Published Mon". */
  published: string;
  due: string;
  /** Submissions, as plain counts — the % is derived, never stored opaque. */
  submitted: number;
  total: number;
  status: AssignmentStatus;
}

/** A chapter group in the assignment list — chapter name + its assignments. */
export interface AssignmentChapter {
  chapter: string;
  subject: SubjectAccent;
  assignments: AssignmentRow[];
}

export interface AssignmentBoard {
  classLabel: string;
  chapters: AssignmentChapter[];
}

export const ASSIGNMENTS_FALLBACK: AssignmentBoard = {
  classLabel: 'Section 10-B',
  chapters: [
    {
      chapter: 'Real Numbers',
      subject: 'cobalt',
      assignments: [
        { id: 'a1', title: 'Equivalent fractions — practice set', kind: 'homework', subject: 'cobalt', published: 'Published Mon', due: 'Due Fri', submitted: 24, total: 31, status: 'in-window' },
        { id: 'a2', title: 'Number line quick check', kind: 'quiz', subject: 'cobalt', published: 'Published Tue', due: 'Closed', submitted: 31, total: 31, status: 'closed' },
      ],
    },
    {
      chapter: 'Light — Reflection',
      subject: 'emerald',
      assignments: [
        { id: 'a3', title: 'Water in our city — investigation', kind: 'project', subject: 'emerald', published: 'Published last week', due: 'Due Fri', submitted: 4, total: 6, status: 'in-window' },
        { id: 'a4', title: 'Refraction worksheet', kind: 'homework', subject: 'emerald', published: 'Scheduled', due: 'Opens Mon', submitted: 0, total: 31, status: 'awaiting' },
      ],
    },
    {
      chapter: 'Tenses in writing',
      subject: 'violet',
      assignments: [
        { id: 'a5', title: 'Past-tense paragraph', kind: 'homework', subject: 'violet', published: 'Published Wed', due: 'Due Tue', submitted: 18, total: 31, status: 'in-window' },
        { id: 'a6', title: 'Tense recognition quiz', kind: 'quiz', subject: 'violet', published: 'Published Thu', due: 'Closed', submitted: 29, total: 31, status: 'closed' },
      ],
    },
  ],
};

/* ---------------------------------------------------------------------------
   8) TEST PAPERS — section-wise mark distribution (MCQ / Assertion-Reasoning /
   Long Answer …) with per-section question counts + marks. The v2 Test-Papers
   detail, in v3: a calm prepared paper that waits for approval; section marks
   are a structure, never a learner-facing score.
   --------------------------------------------------------------------------- */

/** One section of a test paper — a question type, its count, and its marks. */
export interface PaperSection {
  label: string;
  /** "MCQ", "Assertion-Reasoning", "Long answer" — the question type. */
  questionType: string;
  questions: number;
  marksEach: number;
  subject: SubjectAccent;
}

export interface TestPaper {
  title: string;
  classLabel: string;
  /** "Periodic test", "Term exam" — the assessment kind. */
  kind: string;
  sections: PaperSection[];
  /** Whether the prepared paper has been approved for use (permission ladder). */
  approved: boolean;
  confidence: Confidence;
}

export const TEST_PAPER_FALLBACK: TestPaper = {
  title: 'Periodic test — Unit 3',
  classLabel: 'Section 10-B',
  kind: 'Periodic test',
  sections: [
    { label: 'Section A', questionType: 'MCQ', questions: 10, marksEach: 1, subject: 'cobalt' },
    { label: 'Section B', questionType: 'Assertion-Reasoning', questions: 4, marksEach: 2, subject: 'emerald' },
    { label: 'Section C', questionType: 'Short answer', questions: 4, marksEach: 3, subject: 'violet' },
    { label: 'Section D', questionType: 'Long answer', questions: 2, marksEach: 5, subject: 'indigo' },
  ],
  approved: false,
  confidence: 'middle',
};

/* ---------------------------------------------------------------------------
   9) TEACHING STATS — the teacher's own teaching load + leave read. Plain
   counts (classes this week/month/year, substitutions covered, leave taken),
   never a ranking or a judgement.
   --------------------------------------------------------------------------- */

export interface TeachingStats {
  classesThisWeek: number;
  classesThisMonth: number;
  classesThisYear: number;
  substitutionsCovered: number;
  leaveTaken: number;
  leaveBalance: number;
}

export const TEACHING_STATS_FALLBACK: TeachingStats = {
  classesThisWeek: 22,
  classesThisMonth: 86,
  classesThisYear: 742,
  substitutionsCovered: 5,
  leaveTaken: 3,
  leaveBalance: 9,
};

/* ---------------------------------------------------------------------------
   10) QUIZ RESULT — a student-facing, evidence-first review of one completed
   check. Bloom-tagged per-question review (right / close / missed) and a
   thinking-level mix, expressed in PLAIN LANGUAGE — never a raw % or a single
   score shown to the learner. The v2 "Test Session Results" modal (which led
   with a score %), re-expressed in the v3 grammar: a review you learn from,
   tied to the cognitive level each question asked of you.
   --------------------------------------------------------------------------- */

export type QuestionOutcome = 'right' | 'close' | 'missed';

/** One reviewed question — its Bloom level, how it went, and a plain note. */
export interface QuizQuestion {
  /** The cognitive level this question asked of you — a Bloom level. */
  level: string;
  outcome: QuestionOutcome;
  /** Whether it was attempted unaided (the line that matters), not with a hint. */
  unaided: boolean;
  /** A short, plain note — what it was about, never a mark. */
  note: string;
}

export interface QuizResult {
  topicLabel: string;
  /** How many questions were on the check (the review covers each). */
  total: number;
  /** A plain-language headline read — calm, evidence-first, never a score. */
  read: string;
  /** The Bloom mix this check drew on — reuses the donut shape. */
  bloom: BloomSlice[];
  /** The per-question review rows, in order. */
  questions: QuizQuestion[];
  confidence: Confidence;
}

export const QUIZ_RESULT_FALLBACK: QuizResult = {
  topicLabel: 'Trigonometric ratios — quick check',
  total: 8,
  read: 'You handled the recall and "use it" questions on your own. The two that asked you to reason across steps are the next stretch — that is exactly where a little practice goes furthest.',
  bloom: [
    { level: 'Remembering', share: 25, accent: 'cobalt' },
    { level: 'Understanding', share: 25, accent: 'cyan' },
    { level: 'Applying', share: 30, accent: 'emerald' },
    { level: 'Analysing', share: 20, accent: 'violet' },
  ],
  questions: [
    { level: 'Remembering', outcome: 'right', unaided: true, note: 'Naming the ratio for a given side pair.' },
    { level: 'Remembering', outcome: 'right', unaided: true, note: 'Recalling the value of a standard angle.' },
    { level: 'Understanding', outcome: 'right', unaided: true, note: 'Explaining why two ratios are equal.' },
    { level: 'Understanding', outcome: 'close', unaided: true, note: 'Reading the diagram the right way round — a small slip.' },
    { level: 'Applying', outcome: 'right', unaided: true, note: 'Using a known ratio to find a missing side.' },
    { level: 'Applying', outcome: 'right', unaided: false, note: 'Worked it through after one hint — nearly unaided.' },
    { level: 'Analysing', outcome: 'close', unaided: true, note: 'Choosing which step comes first across two ratios.' },
    { level: 'Analysing', outcome: 'missed', unaided: true, note: 'Reasoning across steps — the clear next focus.' },
  ],
  confidence: 'middle',
};

/* ---------------------------------------------------------------------------
   11) MARKBOOK — the v2 grade-entry grid (students × periods/terms), in v3.
   Cells are PLAIN-LANGUAGE BANDS, never a raw % shown to a learner: each cell
   carries a band (below / on / above / exemplary / not-yet) the teacher SETS,
   with an optional remark. Setup mode lets the teacher set a cell's band;
   View mode is the calm read. The band is the teacher's recorded judgement
   against the period target — colour-coded by band, never a number on a child.
   --------------------------------------------------------------------------- */

/** A plain-language markbook band — the recorded standing, never a raw score. */
export type MarkBand = 'exemplary' | 'above' | 'on' | 'below' | 'not-yet';

/** One cell in the markbook grid — a band against a period, plus a remark. */
export interface MarkCell {
  /** The recorded band, or null when nothing has been entered yet. */
  band: MarkBand | null;
  /** An optional short remark the teacher attached (evidence-first, plain). */
  remark?: string;
}

/** One row in the markbook — a generic student label + a roll token + cells. */
export interface MarkRow {
  /** Generic, fictional — "Student A". Never a real name. */
  label: string;
  /** A short roll token — "01", "02". Opaque, not an identifier. */
  roll: string;
  /** One cell per period column (same order as `periods`). */
  cells: MarkCell[];
}

export interface MarkBook {
  classLabel: string;
  subject: SubjectAccent;
  /** The period / term column headers — "Unit 1", "Term 1", "Periodic 2". */
  periods: string[];
  rows: MarkRow[];
  confidence: Confidence;
}

export const MARKBOOK_FALLBACK: MarkBook = {
  classLabel: 'Section 10-B',
  subject: 'cobalt',
  periods: ['Unit 1', 'Periodic 1', 'Unit 2', 'Term 1'],
  rows: [
    { label: 'Student A', roll: '01', cells: [{ band: 'on' }, { band: 'above' }, { band: 'above', remark: 'Strong on multi-step reasoning.' }, { band: 'exemplary' }] },
    { label: 'Student B', roll: '02', cells: [{ band: 'below', remark: 'Fractions reset recommended.' }, { band: 'on' }, { band: 'on' }, { band: 'on' }] },
    { label: 'Student C', roll: '03', cells: [{ band: 'on' }, { band: 'on' }, { band: 'below', remark: 'Stopped one step short on the proof.' }, { band: 'on' }] },
    { label: 'Student D', roll: '04', cells: [{ band: 'above' }, { band: 'above' }, { band: 'exemplary' }, { band: 'exemplary' }] },
    { label: 'Student E', roll: '05', cells: [{ band: 'below' }, { band: 'below', remark: 'Same below-target cluster as the prerequisite check.' }, { band: 'on' }, { band: null }] },
    { label: 'Student F', roll: '06', cells: [{ band: 'on' }, { band: 'on' }, { band: 'above' }, { band: 'above' }] },
  ],
  confidence: 'high',
};

/* ---------------------------------------------------------------------------
   12) QUESTION-PAPER PREVIEW — the v2 paper preview + answer-key render.
   The prepared paper laid out as a DOCUMENT: section headings, numbered
   questions (MCQ options / short / long / assertion-reasoning), point values,
   then a separate Answer-Key view with model answers. The paper is PREPARED
   and waits behind the approval ladder; model answers are the teacher's key,
   never shown to a learner. Marks describe the paper, never a child's score.
   --------------------------------------------------------------------------- */

export type PaperQuestionType = 'mcq' | 'short' | 'long' | 'assertion-reasoning';

/** One question in the rendered paper — its prompt, type, marks, and key. */
export interface PaperQuestion {
  /** Question number within its section — "1", "2". */
  number: string;
  type: PaperQuestionType;
  prompt: string;
  marks: number;
  /** A–D options, for MCQ / assertion-reasoning. Empty for short/long. */
  options?: string[];
  /** The model answer / answer key for this question (teacher-only). */
  modelAnswer: string;
}

/** One section of the rendered paper — a heading, instruction, and questions. */
export interface PaperPreviewSection {
  label: string;
  /** A short instruction line for the section — "Answer all questions." */
  instruction: string;
  subject: SubjectAccent;
  questions: PaperQuestion[];
}

export interface PaperPreview {
  title: string;
  classLabel: string;
  kind: string;
  /** Time allowed — "1 hour", "3 hours". A structure, never a learner score. */
  duration: string;
  sections: PaperPreviewSection[];
  /** Whether the prepared paper has been approved (permission ladder). */
  approved: boolean;
  confidence: Confidence;
}

export const PAPER_PREVIEW_FALLBACK: PaperPreview = {
  title: 'Periodic test — Unit 3',
  classLabel: 'Section 10-B',
  kind: 'Periodic test',
  duration: '1 hour',
  sections: [
    {
      label: 'Section A',
      instruction: 'Multiple choice. Choose the one best answer. 1 mark each.',
      subject: 'cobalt',
      questions: [
        {
          number: '1',
          type: 'mcq',
          prompt: 'Which fraction is equivalent to 3/4?',
          marks: 1,
          options: ['6/9', '9/12', '5/8', '4/6'],
          modelAnswer: 'B — 9/12. Multiply numerator and denominator by 3.',
        },
        {
          number: '2',
          type: 'mcq',
          prompt: 'The value of sin 30° is:',
          marks: 1,
          options: ['1', '1/2', '√3/2', '0'],
          modelAnswer: 'B — 1/2. A standard-angle value to recall.',
        },
      ],
    },
    {
      label: 'Section B',
      instruction: 'Assertion-Reasoning. Mark whether the reason explains the assertion. 2 marks each.',
      subject: 'emerald',
      questions: [
        {
          number: '3',
          type: 'assertion-reasoning',
          prompt:
            'Assertion: Photosynthesis needs light. Reason: Chlorophyll absorbs light energy to drive the reaction.',
          marks: 2,
          options: [
            'Both true; reason explains assertion',
            'Both true; reason does not explain',
            'Assertion true, reason false',
            'Assertion false, reason true',
          ],
          modelAnswer: 'A — both are true and the reason correctly explains the assertion.',
        },
      ],
    },
    {
      label: 'Section C',
      instruction: 'Short answer. Show your working. 3 marks each.',
      subject: 'violet',
      questions: [
        {
          number: '4',
          type: 'short',
          prompt: 'Given sin θ = 3/5 in a right triangle, find cos θ. Show your method.',
          marks: 3,
          modelAnswer:
            'Use the Pythagorean relationship: cos θ = √(1 − sin²θ) = √(1 − 9/25) = 4/5. Award method marks for setting up the relationship even if arithmetic slips.',
        },
      ],
    },
    {
      label: 'Section D',
      instruction: 'Long answer. Answer in full sentences. 5 marks each.',
      subject: 'indigo',
      questions: [
        {
          number: '5',
          type: 'long',
          prompt:
            'Explain, with one worked example, how to find an equivalent fraction, and why the value does not change.',
          marks: 5,
          modelAnswer:
            'Multiply (or divide) numerator and denominator by the same non-zero number; the ratio — and so the value — is unchanged. Worked example, e.g. 1/2 = 2/4. Award marks for the worked example, the reasoning about the unchanged ratio, and clear communication.',
        },
      ],
    },
  ],
  approved: false,
  confidence: 'middle',
};

/* ---------------------------------------------------------------------------
   13) TEACHER PTM — the teacher-side parent-teacher-meeting management read,
   the counterpart to the parent's /parent/together. The teacher publishes a
   day's slots with availability, reads incoming parent QUERIES (each carrying
   a prepared talking point), and records a meeting SUMMARY after a slot. A
   slot is held only when a request is matched — nothing is auto-booked. All
   labels are generic + fictional (Parent of Student A); no real names, no PII.
   --------------------------------------------------------------------------- */

export type PtmSlotStatus = 'open' | 'requested' | 'booked';

/** One time slot the teacher has opened for the PTM day. */
export interface PtmSlot {
  id: string;
  /** A human time token — "09:00", "09:20". */
  time: string;
  status: PtmSlotStatus;
  /** When requested/booked, the generic parent label — "Parent of Student A". */
  withLabel?: string;
}

/** An incoming parent query the teacher prepares for, before a meeting. */
export interface PtmQuery {
  id: string;
  /** Generic, fictional — "Parent of Student A". */
  fromLabel: string;
  childLabel: string;
  subject: SubjectAccent;
  /** The parent's question, in plain language. */
  question: string;
  /** A prepared talking point the teacher can bring — evidence-first. */
  preparedPoint: string;
  /** Whether the teacher has marked this query as prepared. */
  prepared: boolean;
}

/** A recorded summary of a completed meeting — calm, plain, shareable. */
export interface PtmSummary {
  id: string;
  withLabel: string;
  childLabel: string;
  when: string;
  /** The plain-language summary of what was agreed — never a raw score. */
  note: string;
  /** Agreed next steps, each a short plain line. */
  agreed: string[];
}

export interface TeacherPtm {
  classLabel: string;
  /** The PTM day label — "Saturday, 28 June". */
  day: string;
  slots: PtmSlot[];
  queries: PtmQuery[];
  summaries: PtmSummary[];
  confidence: Confidence;
}

export const TEACHER_PTM_FALLBACK: TeacherPtm = {
  classLabel: 'Section 10-B',
  day: 'Saturday, 28 June',
  slots: [
    { id: 's1', time: '09:00', status: 'booked', withLabel: 'Parent of Student A' },
    { id: 's2', time: '09:20', status: 'requested', withLabel: 'Parent of Student C' },
    { id: 's3', time: '09:40', status: 'open' },
    { id: 's4', time: '10:00', status: 'open' },
    { id: 's5', time: '10:20', status: 'booked', withLabel: 'Parent of Student E' },
    { id: 's6', time: '10:40', status: 'open' },
  ],
  queries: [
    {
      id: 'q1',
      fromLabel: 'Parent of Student A',
      childLabel: 'Student A',
      subject: 'cobalt',
      question: 'How can we support fractions practice at home without it becoming a battle?',
      preparedPoint:
        'Student A is on target on fractions and moving toward independent — suggest 10 warm minutes of equivalent-fractions card games, not drilling.',
      prepared: true,
    },
    {
      id: 'q2',
      fromLabel: 'Parent of Student C',
      childLabel: 'Student C',
      subject: 'emerald',
      question: 'Is the science project on track? We are not sure what is expected.',
      preparedPoint:
        'Walk through the project rubric — Student C is strong on communication, and the next step is reasoning across sources. Share the level descriptors.',
      prepared: false,
    },
  ],
  summaries: [
    {
      id: 'm1',
      withLabel: 'Parent of Student E',
      childLabel: 'Student E',
      when: 'Last term',
      note: 'Agreed a calm check-in routine after the two clustered absences in May. Attendance has been steady since.',
      agreed: ['A short Friday reading routine at home', 'A scaffolded fractions reset before the ratios unit'],
    },
  ],
  confidence: 'high',
};

/* ---------------------------------------------------------------------------
   The bundle — one read returns every viz shape for a surface, each carrying
   its own source so a surface can degrade observably per-section.
   --------------------------------------------------------------------------- */

export interface VizBundle {
  attendance: AttendanceRecord;
  holistic: HolisticProgress;
  rubric: ProjectRubric;
  paper: PaperAnalysis;
  bloom: BloomDistribution;
  success: SuccessProbability;
  trend: PerformanceTrend;
  calendar: CalendarMonth;
  timetable: Timetable;
  assignments: AssignmentBoard;
  testPaper: TestPaper;
  teachingStats: TeachingStats;
  quizResult: QuizResult;
  markbook: MarkBook;
  paperPreview: PaperPreview;
  teacherPtm: TeacherPtm;
}

/** The complete fallback bundle — the observable, real-shaped degrade read. */
export const VIZ_FALLBACK: VizBundle = {
  attendance: ATTENDANCE_FALLBACK,
  holistic: HOLISTIC_FALLBACK,
  rubric: RUBRIC_FALLBACK,
  paper: PAPER_FALLBACK,
  bloom: BLOOM_FALLBACK,
  success: SUCCESS_FALLBACK,
  trend: TREND_FALLBACK,
  calendar: CALENDAR_FALLBACK,
  timetable: TIMETABLE_FALLBACK,
  assignments: ASSIGNMENTS_FALLBACK,
  testPaper: TEST_PAPER_FALLBACK,
  teachingStats: TEACHING_STATS_FALLBACK,
  quizResult: QUIZ_RESULT_FALLBACK,
  markbook: MARKBOOK_FALLBACK,
  paperPreview: PAPER_PREVIEW_FALLBACK,
  teacherPtm: TEACHER_PTM_FALLBACK,
};

/** The viz kinds the gateway-first read can request individually. */
export type VizKind = keyof VizBundle;
