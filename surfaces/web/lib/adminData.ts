/* ============================================================================
   lib/adminData.ts — typed data for the admin governance + intelligence
   surfaces that go beyond the Ring-1/Ring-2 mocks: the agent roster the control
   centre governs, the versioned policy ledger, and the intelligence views the
   spec calls by name (study quadrant, trajectory, pacing).

   Generic labels only (no real names, no real pricing, no codenames, no emoji,
   no exclamation marks). Mastery is read in PLAIN LANGUAGE — a direction, never
   a raw score shown to a learner/parent. These degrade gracefully until the
   gateway + event store answer the same shapes; the surfaces read them
   gateway-first and fall back here on degrade.
   ============================================================================ */

import type { Confidence } from '@classess/design-system';

/* ----------------------------------------------------------------- AI agents */

/**
 * A governed agent in the institution's AI control centre. Each carries the
 * tools it may reach and a model-routing track. Enabling/disabling persists
 * (admin config is real configuration). A consequential agent can only ever
 * PREPARE — it never auto-fires; the permission ladder gates the act.
 */
export interface Agent {
  id: string;
  /** Plain-language role label, generic — never a codename. */
  name: string;
  /** One-line plain-language statement of what it does. */
  purpose: string;
  /** The tools it is permitted to reach, plain-language. */
  tools: string[];
  /** Which model-routing track it runs on (kept separate, never blended). */
  track: 'standards' | 'platform';
  /** Whether it is enabled by default (the baseline an un-touched config reads). */
  defaultOn: boolean;
  /**
   * True when its prepared output is consequential (send/submit/publish/delete/
   * charge/grade). A consequential agent can prepare but never act on its own.
   */
  consequential: boolean;
}

export const AGENTS: Agent[] = [
  {
    id: 'observer',
    name: 'The proactive observer',
    purpose: 'Watches the loop and surfaces what needs a human look, with evidence.',
    tools: ['Read mastery and gaps', 'Read the event store', 'Compose a recommendation'],
    track: 'standards',
    defaultOn: true,
    consequential: false,
  },
  {
    id: 'planner',
    name: 'The pacing planner',
    purpose: 'Prepares recovery plans when a section falls behind the pacing plan.',
    tools: ['Read coverage', 'Read the calendar', 'Draft a recovery plan'],
    track: 'standards',
    defaultOn: true,
    consequential: false,
  },
  {
    id: 'evaluator',
    name: 'The evaluation assistant',
    purpose: 'Reads responses into correct / incomplete / misunderstood for a human to finalise.',
    tools: ['Read submissions', 'Propose a provisional mark'],
    track: 'platform',
    defaultOn: true,
    consequential: true,
  },
  {
    id: 'communicator',
    name: 'The family communicator',
    purpose: 'Drafts plain-language notes to families. Sending always waits for a human.',
    tools: ['Read a child read', 'Draft a message'],
    track: 'standards',
    defaultOn: true,
    consequential: true,
  },
  {
    id: 'steward',
    name: 'The ontology steward',
    purpose: 'Proposes curriculum mappings and prerequisite edges for a human to confirm.',
    tools: ['Read the ontology', 'Propose a mapping'],
    track: 'platform',
    defaultOn: false,
    consequential: false,
  },
];

/** Resolve an agent's effective enabled state given the persisted overrides. */
export function agentEnabled(agent: Agent, overrides?: Record<string, boolean>): boolean {
  const v = overrides?.[agent.id];
  return typeof v === 'boolean' ? v : agent.defaultOn;
}

/* ------------------------------------------------------------- Policy ledger */

/** One immutable version of a policy — versioned with an effective date. */
export interface PolicyVersion {
  /** Version label, e.g. "v3". */
  version: string;
  /** ISO-like plain date the version takes effect. */
  effective: string;
  /** Plain-language summary of what this version changed. */
  summary: string;
  /** Role label of the human who set it (never a real name). */
  setBy: string;
}

/**
 * A governed policy with its version history. Policies flow down the tree and
 * are versioned with effective dates + audit. The latest version is the head;
 * older versions are an immutable record.
 */
export interface Policy {
  id: string;
  name: string;
  /** The scope level the policy governs. */
  domain: string;
  /** Versions newest-first; [0] is the current head unless overridden. */
  versions: PolicyVersion[];
}

export const POLICIES: Policy[] = [
  {
    id: 'ai-usage',
    name: 'AI usage',
    domain: 'Whole institution',
    versions: [
      {
        version: 'v3',
        effective: '2026-06-01',
        summary: 'Consequential actions require explicit human approval; no agent holds credentials.',
        setBy: 'Principal',
      },
      {
        version: 'v2',
        effective: '2026-01-15',
        summary: 'Added the confidence gate: low-confidence output is withheld for a human read.',
        setBy: 'Principal',
      },
      {
        version: 'v1',
        effective: '2025-09-01',
        summary: 'First AI usage policy — recommendations permitted, sending always human-gated.',
        setBy: 'Owner',
      },
    ],
  },
  {
    id: 'grading',
    name: 'Grading and moderation',
    domain: 'Examination',
    versions: [
      {
        version: 'v2',
        effective: '2026-04-01',
        summary: 'Short-answer marks are provisional until a human finalises; scan quality never penalised.',
        setBy: 'Examination',
      },
      {
        version: 'v1',
        effective: '2025-09-01',
        summary: 'Baseline mark schemes and grade-point mapping established.',
        setBy: 'Examination',
      },
    ],
  },
  {
    id: 'data-retention',
    name: 'Data retention',
    domain: 'Whole institution',
    versions: [
      {
        version: 'v2',
        effective: '2026-03-10',
        summary: 'Deletion severs the PII link; aggregate intelligence is retained without it.',
        setBy: 'Coordinator, Campus North',
      },
      {
        version: 'v1',
        effective: '2025-09-01',
        summary: 'Retention schedules set per record class; export and correction made first-class.',
        setBy: 'Owner',
      },
    ],
  },
];

/** The version in force for a policy given the persisted overrides (default: head). */
export function policyInForce(policy: Policy, overrides?: Record<string, string>): PolicyVersion {
  const head = policy.versions[0]!;
  const chosen = overrides?.[policy.id];
  if (!chosen) return head;
  return policy.versions.find((v) => v.version === chosen) ?? head;
}

/* ----------------------------------------------------------- Study quadrant */

/** A learner placed on the study quadrant by independence and consistency. */
export interface QuadrantPoint {
  id: string;
  /** Generic label, never a real name. */
  label: string;
  section: string;
  /** 0..100 — share of attempts done independently (a direction, not a grade). */
  independence: number;
  /** 0..100 — consistency of that independence over the fortnight. */
  consistency: number;
}

/** The four bands of the study quadrant. */
export type QuadrantBand = 'star' | 'emerging' | 'potential' | 'at-risk';

export const QUADRANT_META: Record<
  QuadrantBand,
  { label: string; tone: 'success' | 'info' | 'warning' | 'danger'; suggestion: string }
> = {
  star: {
    label: 'Working on their own',
    tone: 'success',
    suggestion: 'Stretch with richer, more open problems.',
  },
  emerging: {
    label: 'Independent but uneven',
    tone: 'info',
    suggestion: 'Steady the routine so the independence holds.',
  },
  potential: {
    label: 'Consistent with support',
    tone: 'warning',
    suggestion: 'Fade the scaffolding one rung to build independence.',
  },
  'at-risk': {
    label: 'Needs support and a routine',
    tone: 'danger',
    suggestion: 'Start a small-group remedial set with close support.',
  },
};

/** Place a point into its band by the independence x consistency split. */
export function bandOf(p: QuadrantPoint): QuadrantBand {
  const indep = p.independence >= 55;
  const cons = p.consistency >= 55;
  if (indep && cons) return 'star';
  if (indep && !cons) return 'emerging';
  if (!indep && cons) return 'potential';
  return 'at-risk';
}

export const QUADRANT_POINTS: QuadrantPoint[] = [
  { id: 'q1', label: 'Student A', section: '10-B', independence: 82, consistency: 78 },
  { id: 'q2', label: 'Student B', section: '10-B', independence: 71, consistency: 64 },
  { id: 'q3', label: 'Student C', section: '9-A', independence: 68, consistency: 41 },
  { id: 'q4', label: 'Student D', section: '9-A', independence: 60, consistency: 35 },
  { id: 'q5', label: 'Student E', section: '8-C', independence: 44, consistency: 70 },
  { id: 'q6', label: 'Student F', section: '8-C', independence: 38, consistency: 62 },
  { id: 'q7', label: 'Student G', section: '10-B', independence: 31, consistency: 33 },
  { id: 'q8', label: 'Student H', section: '9-A', independence: 26, consistency: 40 },
  { id: 'q9', label: 'Student I', section: '8-C', independence: 49, consistency: 52 },
];

/** Group the points into the four bands, with the suggested set per band. */
export function quadrantGroups(points: QuadrantPoint[] = QUADRANT_POINTS) {
  const groups: Record<QuadrantBand, QuadrantPoint[]> = {
    star: [],
    emerging: [],
    potential: [],
    'at-risk': [],
  };
  for (const p of points) groups[bandOf(p)].push(p);
  return groups;
}

/* -------------------------------------------------------------- Trajectory */

/**
 * A trajectory series — the share of a cohort moving toward independent over
 * the term, with the actual (solid) points and the predicted (dotted) tail. A
 * direction, never a grade; recalculated as time and weightage change.
 */
export interface TrajectorySeries {
  topic: string;
  /** Actual readings to date, oldest first (0..100, share trending independent). */
  actual: number[];
  /** Predicted continuation, continuing from the last actual (0..100). */
  predicted: number[];
  /** Plain-language read of where it is heading. */
  read: string;
}

export const TRAJECTORY: TrajectorySeries = {
  topic: 'Grade 10 Mathematics — independence trend',
  actual: [48, 52, 55, 59, 63],
  predicted: [63, 67, 70, 72],
  read: 'On the current pace this cohort reaches a steady majority working on their own by term end. Recovering the two behind sections lifts the predicted tail.',
};

/* ----------------------------------------------------------------- Pacing */

/** A pacing row — planned vs delivered for a section, with a recovery read. */
export interface PacingRow {
  id: string;
  section: string;
  subject: string;
  /** Periods planned to date. */
  planned: number;
  /** Periods actually delivered to date. */
  delivered: number;
  /** Plain-language recovery recommendation when behind. */
  recovery: string;
  /** Confidence in the recovery recommendation. */
  confidence: Confidence;
  /** Whether the recovery is low-risk enough to automate within policy. */
  lowRisk: boolean;
}

export const PACING_ROWS: PacingRow[] = [
  {
    id: 'p1',
    section: 'Section 10-B',
    subject: 'Mathematics',
    planned: 42,
    delivered: 36,
    recovery: 'Add two revision periods next week and reallocate one free slot to close the gap.',
    confidence: 'high',
    lowRisk: true,
  },
  {
    id: 'p2',
    section: 'Section 9-A',
    subject: 'Science',
    planned: 38,
    delivered: 34,
    recovery: 'Fold the missed practical into a combined block; no calendar change needed.',
    confidence: 'middle',
    lowRisk: true,
  },
  {
    id: 'p3',
    section: 'Section 8-C',
    subject: 'English',
    planned: 40,
    delivered: 31,
    recovery: 'A larger gap — propose an added period and a coordinator review before committing.',
    confidence: 'middle',
    lowRisk: false,
  },
];

/** Pacing summary counts for the dashboard stats. */
export function pacingSummary(rows: PacingRow[] = PACING_ROWS) {
  const behind = rows.filter((r) => r.delivered < r.planned);
  const lost = rows.reduce((n, r) => n + Math.max(0, r.planned - r.delivered), 0);
  return {
    sections: rows.length,
    behind: behind.length,
    periodsLost: lost,
    autoEligible: behind.filter((r) => r.lowRisk).length,
  };
}
