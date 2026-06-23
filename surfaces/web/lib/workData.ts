/* ============================================================================
   lib/workData.ts — typed mock for Student Work (d9): the assignment inbox and
   the group-project view.

   Mirrors modules/coursework (assignments.py + groups.py): assignments carry an
   ontology-mapped kind (quick-check / homework / project), a due date, and a
   status that moves through a small, explicit lifecycle. Submission is
   CONSEQUENTIAL — it is permission-laddered and never auto-fires; the inbox only
   ever PREPARES a submission and waits for an explicit human confirm.

   A shared, in-memory assignment list is the seam that makes the loop visible: a
   check the teacher prepares in /teacher/assign is appended here, so it appears
   in the student inbox. The live path is the gateway + coursework service; this
   is the graceful-degradation fallback. Labels are generic; no PII, no pricing.
   ============================================================================ */

import { SEED_ONTOLOGY_IDS } from '@classess/contracts';
import { CLASS_LABEL, topicInfo } from './loopData';

const IDS = SEED_ONTOLOGY_IDS;

/** The kind of work — mirrors coursework AssignmentKind, plain labels. */
export type WorkKind = 'quick-check' | 'homework' | 'project';

export const WORK_KIND_LABEL: Record<WorkKind, string> = {
  'quick-check': 'Quick check',
  homework: 'Homework',
  project: 'Project',
};

/**
 * The status of one assignment for the learner. A small, explicit lifecycle:
 *   todo -> in-progress -> submitted -> returned.
 * Submission is the consequential step; it is confirmed by the learner, never
 * fired automatically.
 */
export type WorkStatus = 'todo' | 'in-progress' | 'submitted' | 'returned';

export const WORK_STATUS_LABEL: Record<WorkStatus, string> = {
  todo: 'To do',
  'in-progress': 'In progress',
  submitted: 'Submitted',
  returned: 'Returned with feedback',
};

/** The legal next statuses from a given status. The inbox enforces this ladder. */
export const STATUS_TRANSITIONS: Record<WorkStatus, WorkStatus[]> = {
  todo: ['in-progress'],
  'in-progress': ['submitted'],
  // Submitting is final from the learner's side until the teacher returns it.
  submitted: [],
  returned: [],
};

/** Whether a learner may move an item from `from` to `to`. Pure + testable. */
export function canTransition(from: WorkStatus, to: WorkStatus): boolean {
  return STATUS_TRANSITIONS[from].includes(to);
}

/** Whether the consequential submit step is available from this status. */
export function canSubmit(status: WorkStatus): boolean {
  return canTransition(status, 'submitted');
}

/**
 * Apply a transition, returning the next status. Returns the SAME status when
 * the transition is not allowed — the ladder never silently jumps a rung.
 */
export function applyTransition(from: WorkStatus, to: WorkStatus): WorkStatus {
  return canTransition(from, to) ? to : from;
}

export interface AssignmentItem {
  id: string;
  title: string;
  kind: WorkKind;
  topicId: string;
  /** Plain-language due — calm, never an order. */
  due: string;
  status: WorkStatus;
  /** A plain one-line description of what the work asks. */
  brief: string;
  /** Number of items, for a quick check / homework. */
  itemCount?: number;
  /** Plain-language feedback once returned. Never a raw score. */
  feedback?: string;
}

export interface AssignmentView extends AssignmentItem {
  kindLabel: string;
  statusLabel: string;
  topicName: string;
  subjectName: string;
}

export function toAssignmentView(a: AssignmentItem): AssignmentView {
  const t = topicInfo(a.topicId);
  return {
    ...a,
    kindLabel: WORK_KIND_LABEL[a.kind],
    statusLabel: WORK_STATUS_LABEL[a.status],
    topicName: t.name,
    subjectName: t.subjectName,
  };
}

// ---------------------------------------------------------------------------
// The seed inbox — a realistic spread of kinds and statuses.
// ---------------------------------------------------------------------------

const SEED_INBOX: AssignmentItem[] = [
  {
    id: 'wk-1',
    title: 'Quick check — trigonometric ratios',
    kind: 'quick-check',
    topicId: IDS.tTrigRatios,
    due: 'Due before the next Mathematics class',
    status: 'todo',
    brief: 'Five short items on finding ratios from a right triangle.',
    itemCount: 5,
  },
  {
    id: 'wk-2',
    title: 'Homework — polynomial zeros',
    kind: 'homework',
    topicId: IDS.tPolyDegreeZeros,
    due: 'Due Friday',
    status: 'in-progress',
    brief: 'Work through the set; you can use a guided start when you need one.',
    itemCount: 8,
  },
  {
    id: 'wk-3',
    title: 'Quick check — laws of reflection',
    kind: 'quick-check',
    topicId: IDS.tReflectionLaws,
    due: 'Submitted yesterday',
    status: 'submitted',
    brief: 'Four items on stating and applying the laws of reflection.',
    itemCount: 4,
  },
  {
    id: 'wk-4',
    title: 'Homework — Ohm’s law practice',
    kind: 'homework',
    topicId: IDS.tOhmsLaw,
    due: 'Returned this morning',
    status: 'returned',
    brief: 'Relate voltage, current, and resistance across a few circuits.',
    itemCount: 6,
    feedback: 'Your method is sound. Work on the units before the next set — that is where the slips were.',
  },
];

/* ----------------------------------------------------------------------------
   The shared, in-memory assignment list — the loop seam. The teacher prepares a
   check in /teacher/assign and APPROVES it; that appends here, so it appears in
   the student inbox. Module-level so both pages see the same list within a
   session. (The live path replaces this with the gateway.)
   ---------------------------------------------------------------------------- */

const assignedFromTeacher: AssignmentItem[] = [];
let assignSeq = 0;

type Listener = () => void;
const listeners = new Set<Listener>();

export function subscribeWork(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function notify(): void {
  for (const l of listeners) l();
}

/**
 * Append a check the teacher just approved in /teacher/assign. Lands in the
 * learner inbox as `todo`. This is the visible Student <-> Teacher loop.
 */
export function pushAssignedCheck(input: {
  topicIds: string[];
  itemCount: number;
}): AssignmentItem {
  assignSeq += 1;
  const primary = input.topicIds[0] ?? IDS.tTrigRatios;
  const t = topicInfo(primary);
  const item: AssignmentItem = {
    id: `wk-live-${assignSeq}`,
    title: `Quick check — ${t.name.toLowerCase()}`,
    kind: 'quick-check',
    topicId: primary,
    due: 'Due before the next class',
    status: 'todo',
    brief: `${input.itemCount} items just assigned to ${CLASS_LABEL}, mapped to the curriculum.`,
    itemCount: input.itemCount,
  };
  assignedFromTeacher.unshift(item);
  notify();
  return item;
}

/** Reset the live list — for tests so they stay isolated. */
export function resetAssignedChecks(): void {
  assignedFromTeacher.length = 0;
  assignSeq = 0;
  notify();
}

/**
 * Resolve the inbox: live teacher-assigned checks first, then the seed. Never
 * throws (graceful degradation). The store seam is read opportunistically.
 */
export function loadInbox(store?: unknown): AssignmentView[] {
  try {
    const slice = (store as { work?: { inbox?: AssignmentItem[] } } | undefined)?.work?.inbox;
    const seed = Array.isArray(slice) && slice.length > 0 ? slice : SEED_INBOX;
    return [...assignedFromTeacher, ...seed].map(toAssignmentView);
  } catch {
    return [...assignedFromTeacher, ...SEED_INBOX].map(toAssignmentView);
  }
}

// ---------------------------------------------------------------------------
// Group project — balanced team, milestones, individual contribution.
// Mirrors coursework groups.py (balance evidence) in plain language.
// ---------------------------------------------------------------------------

export type MilestoneState = 'done' | 'active' | 'upcoming';

export const MILESTONE_LABEL: Record<MilestoneState, string> = {
  done: 'Done',
  active: 'In progress',
  upcoming: 'Coming up',
};

export interface ProjectMilestone {
  id: string;
  title: string;
  state: MilestoneState;
  /** Calm, plain-language due. */
  due: string;
}

export interface ProjectMember {
  /** Generic label — never a real name. */
  label: string;
  /** The role this member is carrying, in plain language. */
  contribution: string;
  /** Whether this is the current learner. */
  isYou?: boolean;
}

export interface GroupProject {
  id: string;
  title: string;
  topicId: string;
  due: string;
  /** Plain-language balance note — never a raw balance metric. */
  balanceNote: string;
  /** Whether the team reads as well-balanced (the groups.py balanced flag, plainly). */
  balanced: boolean;
  members: ProjectMember[];
  milestones: ProjectMilestone[];
}

export const GROUP_PROJECT: GroupProject = {
  id: 'proj-1',
  title: 'Optics in everyday life — a small investigation',
  topicId: IDS.tRefractionLaws,
  due: 'Final piece due in two weeks',
  balanceNote:
    'Your team was built to be balanced — each member brings a different strength, so no one carries it alone.',
  balanced: true,
  members: [
    { label: 'You', contribution: 'Writing up the refraction findings', isYou: true },
    { label: 'Student C', contribution: 'Gathering the everyday examples' },
    { label: 'Student E', contribution: 'Drawing the ray diagrams' },
    { label: 'Student G', contribution: 'Pulling the final piece together' },
  ],
  milestones: [
    { id: 'm1', title: 'Agree the question and split the work', state: 'done', due: 'Last week' },
    { id: 'm2', title: 'Collect examples and first diagrams', state: 'active', due: 'This week' },
    { id: 'm3', title: 'Draft the write-up together', state: 'upcoming', due: 'Next week' },
    { id: 'm4', title: 'Review, polish, and submit', state: 'upcoming', due: 'In two weeks' },
  ],
};

export function loadProject(): GroupProject {
  return GROUP_PROJECT;
}
