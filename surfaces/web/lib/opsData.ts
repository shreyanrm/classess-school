/* ============================================================================
   lib/opsData.ts — PII-free data shapes for the ADMIN operational workflows +
   the academic-planner Gantt the v2->v3 experience map names for the admin role.

   These are the v2 "operational" screens (Leave Management, Staff Attendance,
   Discipline Log) and the "Academic Planner" Gantt — re-expressed in the v3
   grammar and seeded with generic, fictional, PII-free shapes so each surface
   renders REAL-SHAPED data with an observable fallback. They degrade gracefully
   through the same gateway-first seam (lib/vizReads / useAdminConfig); these
   seeds are the last-known read surfaced honestly with a SourceNote.

   v3 grammar carried here:
     • Leave approval rides the PERMISSION LADDER — prepared -> a human approves
       or declines; nothing auto-fires, and the ladder names who may decide.
     • Staff attendance is plain counts + cover, never a ranking or a judgement.
     • Discipline is NON-PUNITIVE: a calm "support log", a pattern to notice and
       a prepared restorative step — never a tally of punishments, never a score.
     • The academic planner is a year x month subject Gantt on the COOL accent
       palette (never coral); depth = hairline + tonal step, no shadow.

   Confidentiality: every label is generic + fictional (Teacher A, Section 10-B,
   Campus North). No real names, no codenames, no real pricing, no emoji.
   ============================================================================ */

import type { SubjectAccent, Confidence } from '@classess/design-system';
import type { PaperAnalysis } from './vizData';

/* ---------------------------------------------------------------------------
   1) LEAVE APPROVAL — the v2 Leave Management screen, in the v3 permission
   ladder. Counts (pending / approved / declined / flagged), a request list, a
   detail drawer (leave details + requester info + approve/reject), and the
   ladder that names who may decide at each tier. Nothing auto-approves.
   --------------------------------------------------------------------------- */

export type LeaveStatus = 'pending' | 'approved' | 'declined' | 'flagged';
export type LeaveKind = 'casual' | 'sick' | 'duty' | 'family';

/**
 * The permission tier a request needs to clear. A short leave a coordinator may
 * approve; a long / overlapping one is held for the principal. The ladder names
 * the decider — the surface gates the approve control on the caller's role.
 */
export type LeaveTier = 'coordinator' | 'principal';

/** One leave request row. PII-free: a generic requester label + a relationship. */
export interface LeaveRequest {
  id: string;
  /** Generic requester label — "Teacher A", "Student C (10-B)". */
  requester: string;
  /** Whether the requester is staff or a student (drives the routing copy). */
  who: 'staff' | 'student';
  kind: LeaveKind;
  /** Plain "from -> to" token — no real dates needed for the read. */
  span: string;
  /** Working days the leave covers (the count the decider weighs). */
  days: number;
  reason: string;
  status: LeaveStatus;
  /** Which tier must clear it — the permission ladder. */
  tier: LeaveTier;
  /** When flagged, the plain reason it needs a closer look (never alarming). */
  flagNote?: string;
  /** Who already actioned it, when decided (a role label, never a name). */
  decidedBy?: string;
  /** For staff leave — whether cover is already arranged. */
  coverArranged?: boolean;
}

export interface LeaveBoard {
  scopeLabel: string;
  requests: LeaveRequest[];
}

export const LEAVE_FALLBACK: LeaveBoard = {
  scopeLabel: 'Campus North',
  requests: [
    {
      id: 'lv1',
      requester: 'Teacher A',
      who: 'staff',
      kind: 'casual',
      span: 'Thu -> Thu',
      days: 1,
      reason: 'Personal appointment in the afternoon.',
      status: 'pending',
      tier: 'coordinator',
      coverArranged: false,
    },
    {
      id: 'lv2',
      requester: 'Teacher B',
      who: 'staff',
      kind: 'sick',
      span: 'Mon -> Wed',
      days: 3,
      reason: 'Recovering from a viral fever; a note is attached.',
      status: 'pending',
      tier: 'coordinator',
      coverArranged: true,
    },
    {
      id: 'lv3',
      requester: 'Teacher C',
      who: 'staff',
      kind: 'family',
      span: 'next week, 5 days',
      days: 5,
      reason: 'A family event out of town.',
      status: 'flagged',
      tier: 'principal',
      flagNote: 'Overlaps the periodic-test window for two of their sections — worth checking cover before approving.',
      coverArranged: false,
    },
    {
      id: 'lv4',
      requester: 'Student C (10-B)',
      who: 'student',
      kind: 'family',
      span: 'Fri -> Mon',
      days: 2,
      reason: 'Travelling for a family function; parent has requested.',
      status: 'pending',
      tier: 'coordinator',
    },
    {
      id: 'lv5',
      requester: 'Teacher D',
      who: 'staff',
      kind: 'duty',
      span: 'Tue (half day)',
      days: 1,
      reason: 'Accompanying the inter-school team — school duty.',
      status: 'approved',
      tier: 'coordinator',
      decidedBy: 'Coordinator, Campus North',
      coverArranged: true,
    },
    {
      id: 'lv6',
      requester: 'Teacher E',
      who: 'staff',
      kind: 'casual',
      span: 'last Fri',
      days: 1,
      reason: 'Requested at short notice; class was already covered.',
      status: 'declined',
      tier: 'coordinator',
      decidedBy: 'Coordinator, Campus North',
    },
  ],
};

export const LEAVE_KIND_LABEL: Record<LeaveKind, string> = {
  casual: 'Casual',
  sick: 'Sick',
  duty: 'On duty',
  family: 'Family',
};

export const LEAVE_TIER_LABEL: Record<LeaveTier, string> = {
  coordinator: 'A coordinator may decide',
  principal: 'Held for the principal',
};

/** Roles allowed to decide at each tier — the permission ladder, web-side. */
export const LEAVE_TIER_DECIDERS: Record<LeaveTier, string[]> = {
  coordinator: ['admin', 'coordinator', 'principal', 'owner'],
  principal: ['admin', 'principal', 'owner'],
};

/** Whether the caller's role may decide a request at this tier. */
export function canDecideLeave(tier: LeaveTier, role?: string): boolean {
  if (!role) return false;
  return LEAVE_TIER_DECIDERS[tier].includes(role);
}

/** The headline counts for the leave board's stat matrix. */
export function leaveCounts(board: LeaveBoard = LEAVE_FALLBACK) {
  const c = { pending: 0, approved: 0, declined: 0, flagged: 0 };
  for (const r of board.requests) c[r.status] += 1;
  return c;
}

/**
 * The shape a requester-side leave application carries (mirrors the store's
 * LeaveApplication without importing it — opsData stays free of the store so it
 * can seed the admin board independently). The operations page passes its own
 * submitted applications in this shape to merge them into the queue.
 */
export interface SubmittedLeave {
  id: string;
  who: 'staff' | 'student';
  kind: LeaveKind;
  span: string;
  days: number;
  reason: string;
}

/**
 * Merge requester-side applications onto a leave board so what a teacher /
 * student SUBMITTED shows up in the admin approval queue as a fresh pending
 * request. The tier follows the same rule the ladder names: a short leave is a
 * coordinator's to clear; a longer one (>= 3 days) is held for the principal.
 * Submitted requests are prepended so the newest sits at the top of the queue.
 */
export function mergeSubmittedLeave(
  board: LeaveBoard,
  submitted: SubmittedLeave[],
): LeaveBoard {
  if (submitted.length === 0) return board;
  const mapped: LeaveRequest[] = submitted.map((s) => ({
    id: s.id,
    requester: 'You (this account)',
    who: s.who,
    kind: s.kind,
    span: s.span,
    days: s.days,
    reason: s.reason,
    status: 'pending' as LeaveStatus,
    tier: s.days >= 3 ? 'principal' : 'coordinator',
    coverArranged: s.who === 'staff' ? false : undefined,
  }));
  return { ...board, requests: [...mapped, ...board.requests] };
}

/* ---------------------------------------------------------------------------
   2) STAFF ATTENDANCE — the v2 Staff Attendance screen. Plain counts per state,
   department grouping, a roster with reason + cover. Never a ranking, never a
   judgement — a calm operational read so a gap is covered, not policed.
   --------------------------------------------------------------------------- */

export type StaffState = 'present' | 'leave' | 'late' | 'cover' | 'absent';

/** One staff row in today's attendance. PII-free: a generic label + dept. */
export interface StaffRow {
  id: string;
  label: string;
  department: string;
  state: StaffState;
  /** A short plain note — the reason / the cover arrangement. */
  note: string;
}

export interface StaffAttendance {
  scopeLabel: string;
  /** The total on the staff roster (the denominator). */
  total: number;
  rows: StaffRow[];
}

export const STAFF_ATTENDANCE_FALLBACK: StaffAttendance = {
  scopeLabel: 'Campus North',
  total: 24,
  rows: [
    { id: 's1', label: 'Teacher A', department: 'Mathematics', state: 'present', note: 'On the timetable as planned.' },
    { id: 's2', label: 'Teacher B', department: 'Science', state: 'leave', note: 'Approved sick leave; cover arranged.' },
    { id: 's3', label: 'Teacher C', department: 'English', state: 'late', note: 'Arrived for second period; first was a free slot.' },
    { id: 's4', label: 'Teacher D', department: 'Social Studies', state: 'cover', note: 'Covering 10-B period 3 for Teacher B.' },
    { id: 's5', label: 'Teacher E', department: 'Mathematics', state: 'present', note: 'On the timetable as planned.' },
    { id: 's6', label: 'Teacher F', department: 'Science', state: 'absent', note: 'Not marked in; a quiet check-in is queued.' },
    { id: 's7', label: 'Teacher G', department: 'English', state: 'present', note: 'On the timetable as planned.' },
    { id: 's8', label: 'Teacher H', department: 'Social Studies', state: 'cover', note: 'Covering 9-A period 5 for Teacher F.' },
  ],
};

export const STAFF_STATE_LABEL: Record<StaffState, string> = {
  present: 'Present',
  leave: 'On leave',
  late: 'Late in',
  cover: 'Covering',
  absent: 'Not marked',
};

export const STAFF_STATE_TONE: Record<StaffState, 'success' | 'info' | 'warning' | 'neutral'> = {
  present: 'success',
  leave: 'info',
  late: 'warning',
  cover: 'info',
  absent: 'warning',
};

/** The per-state counts for the staff-attendance matrix. */
export function staffCounts(data: StaffAttendance = STAFF_ATTENDANCE_FALLBACK) {
  const c: Record<StaffState, number> = { present: 0, leave: 0, late: 0, cover: 0, absent: 0 };
  for (const r of data.rows) c[r.state] += 1;
  return c;
}

/* ---------------------------------------------------------------------------
   3) DISCIPLINE / SUPPORT LOG — the v2 Discipline Log, re-expressed NON-
   PUNITIVELY. Not a tally of punishments: a calm support log of patterns to
   notice, each routing to a human with a PREPARED restorative step (never an
   auto-applied consequence, never a score). Counts read as "needs a look" /
   "supported" / "resolved" — never "offenders".
   --------------------------------------------------------------------------- */

export type SupportStatus = 'needs-look' | 'supporting' | 'resolved';

/** One support-log entry. PII-free: a generic learner label + a calm pattern. */
export interface SupportEntry {
  id: string;
  /** Generic learner label — "Student D (9-A)". */
  learner: string;
  section: string;
  /** The plain pattern noticed — never a verdict, never a punishment. */
  pattern: string;
  /** Whether the pattern has repeated (the only "escalation" signal). */
  repeated: boolean;
  status: SupportStatus;
  /** The prepared restorative step — approvable, never auto-applied. */
  preparedStep: string;
  /** Who is holding it (a role label, never a name). */
  heldBy: string;
}

export interface SupportLog {
  scopeLabel: string;
  entries: SupportEntry[];
}

export const SUPPORT_LOG_FALLBACK: SupportLog = {
  scopeLabel: 'Campus North',
  entries: [
    {
      id: 'd1',
      learner: 'Student D (9-A)',
      section: '9-A',
      pattern: 'Disengaging in the afternoon block over the last fortnight — head down, not participating.',
      repeated: true,
      status: 'needs-look',
      preparedStep: 'A short, private check-in with the class teacher is prepared — to understand, not to reprimand. It waits for you.',
      heldBy: 'Class teacher, 9-A',
    },
    {
      id: 'd2',
      learner: 'Student G (10-B)',
      section: '10-B',
      pattern: 'Two late arrivals this week; both followed a missed school bus.',
      repeated: false,
      status: 'supporting',
      preparedStep: 'A calm note to the family about the morning routine is drafted — supportive, not a warning. Sending waits for a human.',
      heldBy: 'Coordinator, Campus North',
    },
    {
      id: 'd3',
      learner: 'Student H (8-C)',
      section: '8-C',
      pattern: 'A disagreement between two learners in the corridor; both have since talked it through.',
      repeated: false,
      status: 'resolved',
      preparedStep: 'Resolved with a restorative conversation. Logged so the pattern is visible if it recurs — closed for now.',
      heldBy: 'Counsellor',
    },
  ],
};

export const SUPPORT_STATUS_LABEL: Record<SupportStatus, string> = {
  'needs-look': 'Needs a look',
  supporting: 'Being supported',
  resolved: 'Resolved',
};

export const SUPPORT_STATUS_TONE: Record<SupportStatus, 'warning' | 'info' | 'success'> = {
  'needs-look': 'warning',
  supporting: 'info',
  resolved: 'success',
};

/** The headline counts for the support log's stat matrix. */
export function supportCounts(log: SupportLog = SUPPORT_LOG_FALLBACK) {
  const needsLook = log.entries.filter((e) => e.status === 'needs-look').length;
  const supporting = log.entries.filter((e) => e.status === 'supporting').length;
  const resolved = log.entries.filter((e) => e.status === 'resolved').length;
  const repeated = log.entries.filter((e) => e.repeated).length;
  return { needsLook, supporting, resolved, repeated };
}

/* ---------------------------------------------------------------------------
   3b) SCHOOL-SCOPE PAPER ANALYSIS — the v2 paper-analysis at the WHOLE-SCHOOL
   scope (the admin lens): a target-band distribution (below / on / above) across
   every section that sat the cycle, a per-period breakdown that reads by grade,
   and prepared cross-section remedial groups. Reuses the PaperAnalysis shape so
   the same SharedViz <PaperAnalysis> renders it. Bands, never raw marks.
   --------------------------------------------------------------------------- */

export const SCHOOL_PAPER_FALLBACK: PaperAnalysis = {
  title: 'Mid-term cycle — whole school',
  classLabel: 'Campus North · all sections',
  total: 412,
  overall: { below: 74, on: 248, above: 90 },
  periods: [
    {
      label: 'Grade 8 — across subjects',
      subject: 'cobalt',
      distribution: { below: 22, on: 78, above: 28 },
      note: 'On the calm band overall; the below-target cluster is concentrated in two sections.',
    },
    {
      label: 'Grade 9 — across subjects',
      subject: 'emerald',
      distribution: { below: 28, on: 86, above: 30 },
      note: 'Science practicals lifted the above-target share; writing tenses holds the below-target group.',
    },
    {
      label: 'Grade 10 — across subjects',
      subject: 'violet',
      distribution: { below: 24, on: 84, above: 32 },
      note: 'Independence is rising; the below-target group maps to the prerequisite gaps already flagged.',
    },
  ],
  remedial: [
    {
      topic: 'Equivalent fractions (Grade 8)',
      subject: 'cobalt',
      members: ['Section 8-A', 'Section 8-C'],
      preparedStep: 'A cross-section fractions reset is prepared for the two flagged sections, before the ratios unit. It waits for a coordinator’s approval.',
    },
    {
      topic: 'Tenses in writing (Grade 9)',
      subject: 'violet',
      members: ['Section 9-A', 'Section 9-B'],
      preparedStep: 'A scaffolded writing-practice block is prepared school-wide for the below-target group. Nothing is assigned until approved.',
    },
  ],
  confidence: 'high' as Confidence,
};

/* ---------------------------------------------------------------------------
   4) ACADEMIC PLANNER — the v2 Gantt-style multi-subject academic planner. A
   year x month grid of subject blocks (which unit runs which months), on the
   COOL accent palette. Each bar is one unit spanning a from..to month range.
   A planning lens, never a learner score.
   --------------------------------------------------------------------------- */

/** One scheduled unit on the planner — a subject bar spanning a month range. */
export interface PlannerUnit {
  id: string;
  subject: SubjectAccent;
  subjectName: string;
  unit: string;
  /** 0-based start month index into the planner's month labels. */
  startMonth: number;
  /** Span in months (>=1). */
  span: number;
  /** Whether this unit is the one currently in delivery (the "now" bar). */
  current?: boolean;
}

export interface AcademicPlanner {
  scopeLabel: string;
  /** The academic-year month labels, in order — "Apr".."Mar". */
  months: string[];
  /** 0-based index of the current month (for the "now" rule). */
  currentMonth: number;
  units: PlannerUnit[];
}

export const ACADEMIC_PLANNER_FALLBACK: AcademicPlanner = {
  scopeLabel: 'Grade 10',
  months: ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'],
  currentMonth: 2,
  units: [
    { id: 'u1', subject: 'cobalt', subjectName: 'Mathematics', unit: 'Real numbers', startMonth: 0, span: 2 },
    { id: 'u2', subject: 'cobalt', subjectName: 'Mathematics', unit: 'Trigonometry', startMonth: 2, span: 3, current: true },
    { id: 'u3', subject: 'cobalt', subjectName: 'Mathematics', unit: 'Statistics', startMonth: 8, span: 2 },
    { id: 'u4', subject: 'emerald', subjectName: 'Science', unit: 'Light & reflection', startMonth: 1, span: 2 },
    { id: 'u5', subject: 'emerald', subjectName: 'Science', unit: 'Life processes', startMonth: 3, span: 3, current: true },
    { id: 'u6', subject: 'emerald', subjectName: 'Science', unit: 'Periodic table', startMonth: 9, span: 2 },
    { id: 'u7', subject: 'violet', subjectName: 'English', unit: 'Prose & poetry', startMonth: 0, span: 4 },
    { id: 'u8', subject: 'violet', subjectName: 'English', unit: 'Writing skills', startMonth: 5, span: 3 },
    { id: 'u9', subject: 'indigo', subjectName: 'Social Studies', unit: 'Nationalism', startMonth: 1, span: 3 },
    { id: 'u10', subject: 'indigo', subjectName: 'Social Studies', unit: 'Resources', startMonth: 6, span: 3 },
  ],
};
