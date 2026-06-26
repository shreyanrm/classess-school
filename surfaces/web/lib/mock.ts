/* ============================================================================
   Typed mock data for the web surface.

   A single Class 10-B teacher's day. All names are deliberately fictional and
   generic (Student A, Class 10-B) — never a real personal name, per the
   confidentiality scrub. No real pricing appears anywhere. Where a shape exists
   in @classess/contracts we reuse its type so the surface stays bound to the
   contract; the live data path is the gateway + event store (env vars named in
   lib/runtime.ts), and these mocks are the graceful-degradation fallback until
   that path is wired.
   ============================================================================ */

import type { SubjectAccent, Confidence } from '@classess/design-system';
import type { MasteryBand, GapType } from '@classess/contracts';

export type Role = 'teacher' | 'student' | 'admin' | 'parent';

export const ROLE_LABELS: Record<Role, string> = {
  teacher: 'Teacher',
  student: 'Student',
  admin: 'Admin',
  parent: 'Parent',
};

/** The teacher's identity for the calm greeting. Generic, fictional. */
export const TEACHER = {
  shortName: 'there',
  homeClass: 'Class 10-B',
};

/** Subject identity colours, drawn from the design-system subject accents. */
export interface SubjectInfo {
  name: string;
  code: string;
  accent: SubjectAccent;
}

export const SUBJECTS: SubjectInfo[] = [
  { name: 'Mathematics', code: 'MATH', accent: 'cobalt' },
  { name: 'Science', code: 'SCI', accent: 'emerald' },
  { name: 'English', code: 'ENG', accent: 'violet' },
  { name: 'Social Studies', code: 'SST', accent: 'indigo' },
];

/** The plain-language phrase for each mastery band — never a number. */
export const BAND_PHRASE: Record<MasteryBand, string> = {
  'not-started': 'Not started yet',
  emerging: 'Showing the idea, with support',
  developing: 'Works with hints',
  secure: 'Reliable, not yet on their own',
  independent: 'Can do this on their own',
};

/** A briefing item — the Today unit on the teacher home. Carries the same
 *  explainable-intelligence fields as a recommendation: a confidence band, an
 *  owner, a due, the consequence of ignoring it, the evidence lineage, and a
 *  plain "why am I seeing this." The primary action routes to a real page. */
export interface Briefing {
  id: string;
  title: string;
  nextAction: string;
  /** Where the primary action goes — a real, navigable page. Never a dead button. */
  target: string;
  minutes: number;
  why: string;
  builds: string;
  subject: SubjectAccent;
  confidence: Confidence;
  owner: string;
  due: string;
  consequence: string;
  evidence: string[];
  whySeeing: string;
}

export const BRIEFINGS: Briefing[] = [
  {
    id: 'b1',
    title: 'Next class: fractions recap with Class 10-B',
    nextAction: 'Open the ready lesson',
    target: '/teacher/plan',
    minutes: 12,
    why: 'Six students slipped on equivalent fractions in the last check.',
    builds: 'Closes a prerequisite gap before the ratios unit next week.',
    subject: 'cobalt',
    confidence: 'high',
    owner: 'You (Class 10-B teacher)',
    due: 'Before the next Mathematics class',
    consequence: 'The ratios unit will stand on a weak prerequisite and the gap will widen.',
    evidence: [
      'Diagnostic check on 18 Jun — 6 of 31 below the prerequisite line.',
      'Worksheet on 20 Jun — the same students needed a worked start.',
    ],
    whySeeing: 'A prerequisite gap was confirmed from fresh, repeated evidence — not a single low score.',
  },
  {
    id: 'b2',
    title: 'Eight evaluations waiting on your sign-off',
    nextAction: 'Review the flagged answers',
    target: '/teacher/evaluate',
    minutes: 9,
    why: 'Three were marked at building confidence and need a human read.',
    builds: 'Returns feedback to students inside the same day.',
    subject: 'emerald',
    confidence: 'high',
    owner: 'You (Class 10-B teacher)',
    due: 'Today',
    consequence: 'Feedback slips a day and the same-day learning loop breaks.',
    evidence: [
      'Eight sessions left at building confidence since this morning.',
      'Three carry low-agreement reads that need a human decision.',
    ],
    whySeeing: 'These were staged for review because finalising a grade is consequential and never auto-fires.',
  },
  {
    id: 'b3',
    title: 'One private coaching insight',
    nextAction: 'See the suggestion',
    target: '/teacher/growth',
    minutes: 4,
    why: 'Your questioning ran ahead of the slower group on Tuesday.',
    builds: 'A small change that lifts the support-dependent third.',
    subject: 'violet',
    confidence: 'middle',
    owner: 'You (Class 10-B teacher)',
    due: 'This week',
    consequence: 'The support-dependent third keeps falling behind the pace of questioning.',
    evidence: [
      'Tuesday lesson — response gap widened between groups after the third prompt.',
      'Exit poll — the slower group named the pace as the sticking point.',
    ],
    whySeeing: 'This is a private coaching note from the growth layer — only you see it, never a leaderboard.',
  },
];

/** Mastery rows for the insights page — plain language, independent vs supported. */
export interface MasteryRow {
  topic: string;
  subject: SubjectAccent;
  band: MasteryBand;
  independent: boolean;
  note: string;
}

export const MASTERY_ROWS: MasteryRow[] = [
  {
    topic: 'Equivalent fractions',
    subject: 'cobalt',
    band: 'developing',
    independent: false,
    note: 'Most of the class still leans on a worked example to start.',
  },
  {
    topic: 'Linear equations',
    subject: 'cobalt',
    band: 'independent',
    independent: true,
    note: 'Solved cleanly without prompts across two fresh checks.',
  },
  {
    topic: 'Photosynthesis',
    subject: 'emerald',
    band: 'secure',
    independent: false,
    note: 'Reliable when guided; falters when asked to explain unprompted.',
  },
  {
    topic: 'Tenses in writing',
    subject: 'violet',
    band: 'emerging',
    independent: false,
    note: 'The idea is there; execution needs scaffolded practice.',
  },
];

/** Class-level stats for the insights matrix. Plain counts, never a formula. */
export interface ClassStat {
  label: string;
  value: number | string;
  detail: string;
}

export const CLASS_STATS: ClassStat[] = [
  { label: 'Working independently', value: 18, detail: 'of 31 students, this week' },
  { label: 'Need support', value: 9, detail: 'flagged across two topics' },
  { label: 'Revision now due', value: 4, detail: 'retention decayed since April' },
  { label: 'Newly secured', value: 6, detail: 'crossed into reliable this week' },
];

/** A proactive recommendation with full explainability per the dossier. */
export interface Recommendation {
  id: string;
  title: string;
  gapType: GapType;
  evidenceSummary: string;
  evidence: string[];
  confidence: Confidence;
  owner: string;
  due: string;
  consequence: string;
  whySeeing: string;
  /** The prepared next action's verb — the rise-fill primary on the card. */
  actionLabel: string;
  /**
   * Consequential (send/submit/publish/delete/charge/grade) -> the action raises
   * the ApprovalControl and commits ONLY on Approve. Reversible/safe-automatic
   * actions execute directly and offer an undo toast. (Permission ladder, `11`.)
   */
  consequential: boolean;
  /** Where Approve/Execute routes the human after it commits — a real page. */
  target: string;
  /**
   * When this recommendation closes a learner's support-dependency/prerequisite
   * gap into independent mastery, executing it surfaces the CrystallizeNode
   * moment + a `gap.resolved` line. Optional: the plain-language mastery line.
   */
  crystallizes?: string;
}

export const RECOMMENDATIONS: Recommendation[] = [
  {
    id: 'r1',
    title: 'Run a 15-minute fractions reset before the ratios unit',
    gapType: 'prerequisite',
    evidenceSummary:
      'Six students in Class 10-B missed equivalent-fraction items across the last two checks.',
    evidence: [
      'Diagnostic check on 18 Jun — 6 of 31 below the prerequisite line.',
      'Worksheet on 20 Jun — the same students needed a worked start.',
      'Exit poll — most named simplifying as the sticking point.',
    ],
    confidence: 'high',
    owner: 'You (Class 10-B teacher)',
    due: 'Before the next Mathematics class',
    consequence: 'The ratios unit will stand on a weak prerequisite and the gap will widen.',
    whySeeing:
      'A prerequisite gap was confirmed from fresh, repeated evidence — not a single low score.',
    // Preparing a reset block is reversible and policy-permitted -> executes
    // directly with an undo. The teacher still reviews it on the plan page.
    actionLabel: 'Prepare the reset',
    consequential: false,
    target: '/teacher/plan',
  },
  {
    id: 'r2',
    title: 'Offer Student A a scaffolded-autonomy task in Science',
    gapType: 'support-dependency',
    evidenceSummary:
      'Student A performs well with help on photosynthesis but cannot yet do it unprompted.',
    evidence: [
      'Three guided attempts correct on 12, 15 and 19 Jun.',
      'One unprompted attempt incomplete on 21 Jun.',
      'Independence dimension reads low while performance reads high.',
    ],
    confidence: 'middle',
    owner: 'You (Class 10-B teacher)',
    due: 'This week',
    consequence: 'Support dependency hardens and the student stays reliant on prompts.',
    whySeeing:
      'The independence dimension separated "can do with help" from "can do alone" and flagged the gap.',
    // Assigning to a student is consequential -> ApprovalControl, commit on
    // Approve only. Clearing the support-dependency gap is the crystallize moment.
    actionLabel: 'Assign the task',
    consequential: true,
    target: '/teacher/assign',
    crystallizes: 'Student A can now do this on their own',
  },
];

/** Suggestion chips beneath the composer — the quiet proactive layer. */
export const HOME_CHIPS: Record<Role, string[]> = {
  teacher: [
    'Fix fractions, 15 min',
    'Build a quick check for Class 10-B',
    'Who needs attention today',
    'Draft tomorrow’s prep',
  ],
  student: [
    'What should I do next',
    'Explain this where I am stuck',
    'Quick practice, 10 min',
    'What am I weakest at',
  ],
  admin: [
    'Which classes are behind',
    'Open parent concerns',
    'Blocking approvals',
    'What improved last week',
  ],
  parent: [
    'How is my child this week',
    'What needs attention',
    'Show a recent win',
    'Next steps to support at home',
  ],
};

/* ============================================================================
   Admin surface — manage by exception. Generic labels only (Campus North,
   Section 10-B); no real names, no real pricing, board-agnostic.
   ============================================================================ */

/** A morning-briefing attention item for the admin Today. */
export interface AdminBriefing {
  id: string;
  title: string;
  detail: string;
  owner: string;
  /** A plain-language status tone for the leading dot. */
  tone: 'info' | 'warning' | 'danger' | 'success';
  nextAction: string;
  /** Where the primary action goes — a real, navigable page. Never a dead button. */
  target: string;
  confidence: Confidence;
  due: string;
  consequence: string;
  evidence: string[];
  whySeeing: string;
}

/** Classes that are behind on pacing — surfaced for review, never auto-actioned. */
export const ADMIN_BRIEFINGS: AdminBriefing[] = [
  {
    id: 'ab1',
    title: 'Section 10-B is two topics behind on the Mathematics pacing plan',
    detail:
      'The ratios unit has not started; the prerequisite fractions check flagged six students last week.',
    owner: 'Coordinator, Campus North',
    tone: 'warning',
    nextAction: 'Open the pacing view',
    target: '/admin/intelligence',
    confidence: 'high',
    due: 'This week',
    consequence: 'The section falls a full unit behind and the term plan slips for the whole cohort.',
    evidence: [
      'Pacing plan vs delivered topics — two units behind as of this week.',
      'Prerequisite fractions check flagged six students last week.',
    ],
    whySeeing: 'Surfaced by manage-by-exception: only sections that drift past the pacing threshold appear here.',
  },
  {
    id: 'ab2',
    title: 'A teacher in Section 9-A needs support with the new evaluation flow',
    detail:
      'Three evaluation sessions were left at building confidence without a human read for over two days.',
    owner: 'Head of Department, Science',
    tone: 'info',
    nextAction: 'See the coaching note',
    target: '/admin/control-centre',
    confidence: 'middle',
    due: 'This week',
    consequence: 'Students wait days for feedback and the teacher stays unsupported on the new flow.',
    evidence: [
      'Three evaluation sessions stalled at building confidence for over two days.',
      'No human read recorded against the flagged sessions.',
    ],
    whySeeing: 'The coaching layer flags a teacher who may need support — a private note, never a performance score.',
  },
  {
    id: 'ab3',
    title: 'Two students crossed into reliable on linear equations',
    detail:
      'A targeted reset two weeks ago moved both from support-dependent to independent on a fresh check.',
    owner: 'Section 10-B teacher',
    tone: 'success',
    nextAction: 'See what changed',
    target: '/admin/intelligence',
    confidence: 'high',
    due: 'No action needed',
    consequence: 'A working intervention goes unrecognised and is less likely to be repeated.',
    evidence: [
      'Targeted reset delivered two weeks ago to the support-dependent group.',
      'Fresh check — both students solved unprompted, moving to independent.',
    ],
    whySeeing: 'Improvements surface too, so what works can be recognised and repeated across sections.',
  },
];

/** A student flagged for possible intervention — evidence-led, never a single score. */
export interface InterventionFlag {
  id: string;
  label: string;
  section: string;
  reason: string;
  confidence: Confidence;
}

export const ADMIN_INTERVENTIONS: InterventionFlag[] = [
  {
    id: 'iv1',
    label: 'Student A',
    section: 'Section 10-B',
    reason: 'Support-dependent on photosynthesis across three guided attempts; one unprompted attempt incomplete.',
    confidence: 'middle',
  },
  {
    id: 'iv2',
    label: 'Student B',
    section: 'Section 9-A',
    reason: 'Attendance and engagement both dipped over the last fortnight; two missed checks.',
    confidence: 'high',
  },
];

/** An open concern raised by a parent, in the admin's queue (no PII, generic label). */
export interface AdminConcern {
  id: string;
  from: string;
  topic: string;
  raised: string;
  status: 'new' | 'in-review';
}

export const ADMIN_CONCERNS: AdminConcern[] = [
  { id: 'c1', from: 'Parent, Section 10-B', topic: 'Homework load this week', raised: 'Yesterday', status: 'new' },
  { id: 'c2', from: 'Parent, Section 8-C', topic: 'PTM scheduling', raised: 'Two days ago', status: 'in-review' },
];

/** School-wide stats for the intelligence matrix. Plain counts, never a formula. */
export const SCHOOL_STATS: ClassStat[] = [
  { label: 'Sections on track', value: 14, detail: 'of 18, against the current pacing plan' },
  { label: 'Sections behind', value: 4, detail: 'flagged for a coordinator review' },
  { label: 'Students working independently', value: 612, detail: 'across the school, this week' },
  { label: 'Students needing support', value: 188, detail: 'flagged on at least one topic' },
  { label: 'Teachers needing support', value: 3, detail: 'surfaced from the coaching layer' },
  { label: 'Open parent concerns', value: 2, detail: 'awaiting a response' },
];

/** A plain-language mastery trend line for the school. */
export interface TrendLine {
  topic: string;
  subject: SubjectAccent;
  direction: 'up' | 'flat' | 'down';
  note: string;
}

export const SCHOOL_TRENDS: TrendLine[] = [
  {
    topic: 'Equivalent fractions',
    subject: 'cobalt',
    direction: 'up',
    note: 'More sections can now start unprompted after the targeted resets in May.',
  },
  {
    topic: 'Photosynthesis',
    subject: 'emerald',
    direction: 'flat',
    note: 'Reliable with guidance school-wide; independence is not yet moving.',
  },
  {
    topic: 'Tenses in writing',
    subject: 'violet',
    direction: 'down',
    note: 'Two sections slipped this fortnight; scaffolded practice is recommended.',
  },
];

/** A scored timetable / substitution alternative — shown for approval, never auto-committed. */
export interface ScheduleAlternative {
  id: string;
  summary: string;
  fitNote: string;
  /** A plain-language fit read; the human approves, the system never commits. */
  fit: Confidence;
  tradeoff: string;
}

export const SUBSTITUTION_NEED = {
  context: 'Section 10-B, Mathematics, third period — the assigned teacher is on approved leave on Thursday.',
};

export const SCHEDULE_ALTERNATIVES: ScheduleAlternative[] = [
  {
    id: 'sa1',
    summary: 'Move the free-period Mathematics teacher from Section 9-C',
    fitNote: 'Same subject, no clash, keeps the ratios sequence intact.',
    fit: 'high',
    tradeoff: 'Section 9-C loses a planning period this week.',
  },
  {
    id: 'sa2',
    summary: 'Swap with Thursday afternoon Science and run a guided revision block',
    fitNote: 'No new staff needed; preserves total teaching minutes.',
    fit: 'middle',
    tradeoff: 'Pushes the Science practical to Friday.',
  },
  {
    id: 'sa3',
    summary: 'Assign the Mathematics HOD for one period',
    fitNote: 'Strong subject fit; useful for the at-risk students in this section.',
    fit: 'high',
    tradeoff: 'HOD office hours move to the afternoon.',
  },
];

/** A governance permission row — who may do what, with the human-authority note. */
export interface PermissionRow {
  capability: string;
  /** The roles allowed to perform it. */
  roles: string;
  /** Whether the action is consequential (needs explicit human approval, never auto-fires). */
  consequential: boolean;
}

export const PERMISSION_MATRIX: PermissionRow[] = [
  { capability: 'View school-wide intelligence', roles: 'Owner, Principal, Coordinator, HOD', consequential: false },
  { capability: 'Approve a timetable or substitution', roles: 'Principal, Coordinator', consequential: true },
  { capability: 'Publish a report to parents', roles: 'Principal, Examination', consequential: true },
  { capability: 'Finalise a grade', roles: 'Teacher (own sections), Examination', consequential: true },
  { capability: 'Send a message to a parent', roles: 'Teacher, Coordinator, Principal', consequential: true },
  { capability: 'Draft a recommendation (no action)', roles: 'The platform (Vidya)', consequential: false },
];

/** AI control-centre toggles — autonomy is bounded by the permission ladder. */
export interface AiControl {
  id: string;
  label: string;
  description: string;
  /** Whether autonomy is permitted for this capability at all. */
  defaultOn: boolean;
  /** True when this capability is consequential and so can never auto-fire. */
  locked: boolean;
}

export const AI_CONTROLS: AiControl[] = [
  {
    id: 'ai1',
    label: 'Surface proactive recommendations',
    description: 'Let the platform observe and recommend. Every recommendation still waits for a human decision.',
    defaultOn: true,
    locked: false,
  },
  {
    id: 'ai2',
    label: 'Auto-send messages or reports',
    description: 'Sending is consequential and never auto-fires. This stays off and cannot be enabled.',
    defaultOn: false,
    locked: true,
  },
  {
    id: 'ai3',
    label: 'Auto-finalise grades',
    description: 'Grading is consequential. The system may prepare, but a human always finalises.',
    defaultOn: false,
    locked: true,
  },
  {
    id: 'ai4',
    label: 'Prepare drafts in the background',
    description: 'Low-risk, in-policy preparation (worksheets, draft notes) the platform may stage for review.',
    defaultOn: true,
    locked: false,
  },
];

/** A recent governance / approval audit entry — append-only, immutable. */
export interface AuditEntry {
  id: string;
  when: string;
  actor: string;
  action: string;
}

export const AUDIT_LOG: AuditEntry[] = [
  { id: 'au1', when: 'Today, 08:12', actor: 'Coordinator, Campus North', action: 'Approved a substitution for Section 10-B' },
  { id: 'au2', when: 'Yesterday, 16:40', actor: 'Principal', action: 'Declined a proactive pacing change, pending review' },
  { id: 'au3', when: 'Yesterday, 11:05', actor: 'Section 10-B teacher', action: 'Finalised eight evaluations after a human read' },
];

/** Setup wizard steps — a calm, multi-step blueprint flow. */
export interface SetupStep {
  id: string;
  title: string;
  summary: string;
  fields: string[];
}

export const SETUP_STEPS: SetupStep[] = [
  {
    id: 'st1',
    title: 'Structure',
    summary: 'Define the campuses, grades, and sections. Board-agnostic; you name the levels.',
    fields: ['Campuses', 'Grades and sections', 'Subjects per grade'],
  },
  {
    id: 'st2',
    title: 'Roles',
    summary: 'Assign owners, principals, coordinators, HODs, and teachers. Roles scope what each person sees.',
    fields: ['Owner and principal', 'Coordinators by campus', 'Heads of department', 'Teachers by section'],
  },
  {
    id: 'st3',
    title: 'Policies',
    summary: 'Set the pacing approach, consent defaults, and which actions require explicit approval.',
    fields: ['Pacing approach', 'Consent for cross-context reads', 'Approval-required actions'],
  },
  {
    id: 'st4',
    title: 'Review',
    summary: 'Review the blueprint in plain language. Nothing is created until you confirm.',
    fields: ['Confirm the structure', 'Confirm the roles', 'Confirm the policies'],
  },
];

/** The greeting copy per role — sentence case, no exclamation, no emoji. */
export const GREETING: Record<Role, string> = {
  teacher: 'Good morning. Here is your day with Class 10-B.',
  student: 'Welcome back. Here is your next step.',
  admin: 'Good morning. Here is what needs your attention.',
  parent: 'Welcome. Here is a calm look at this week.',
};
