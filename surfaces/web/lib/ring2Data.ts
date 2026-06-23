/* ============================================================================
   Ring 2 surface mock data — admin integrations, the AI control centre,
   teacher growth coaching, and the multi-campus network view.

   Generic labels only (Connector, Campus North, Section 10-B). No real personal
   names, no real pricing, no codenames, no emoji, no exclamation marks. Where a
   contract shape exists we lean on it; otherwise these are plain typed mocks
   that degrade gracefully until the gateway + event store is wired (env var
   names live in lib/runtime.ts). Track 1 (external/standards) and Track 2
   (proprietary/edge) are kept SEPARATE in the control-centre model, per the
   separation invariant.
   ============================================================================ */

import type { TagTone } from '@classess/design-system';

/* ------------------------------------------------------------------ Connectors */

/**
 * A connector health state. `enabled` connectors are syncing; `available`
 * connectors are present but switched off; `attention` ones synced with a
 * warning; `error` ones failed their last sync; `pending` ones are awaiting a
 * human approval before they may turn on (enabling is consequential and never
 * auto-fires).
 */
export type ConnectorState =
  | 'enabled'
  | 'available'
  | 'attention'
  | 'error'
  | 'pending';

/** Which integration track a connector belongs to — kept separate in config. */
export type ConnectorTrack = 'standards' | 'platform';

export interface Connector {
  id: string;
  /** Short standard/protocol name, generic. */
  name: string;
  /** One-line plain-language description of what it moves. */
  summary: string;
  track: ConnectorTrack;
  state: ConnectorState;
  /** Plain-language last-sync phrase, or null when never synced. */
  lastSync: string | null;
  /** True when turning this on sends/writes data outward (consequential). */
  consequential: boolean;
}

/**
 * The connector matrix. A board-agnostic set of education-interop standards and
 * platform bridges. Health states are mixed so every first-class state renders.
 */
export const CONNECTORS: Connector[] = [
  {
    id: 'lti',
    name: 'LTI',
    summary: 'Launch and roster bridge to an external learning tool.',
    track: 'standards',
    state: 'enabled',
    lastSync: 'Synced 6 minutes ago',
    consequential: false,
  },
  {
    id: 'oneroster',
    name: 'OneRoster',
    summary: 'Class, section, and enrolment roster exchange.',
    track: 'standards',
    state: 'enabled',
    lastSync: 'Synced 18 minutes ago',
    consequential: false,
  },
  {
    id: 'xapi',
    name: 'xAPI',
    summary: 'Learning-experience statements into the event store.',
    track: 'standards',
    state: 'attention',
    lastSync: 'Synced 2 hours ago, some records held for review',
    consequential: false,
  },
  {
    id: 'qti',
    name: 'QTI',
    summary: 'Question and test interoperability for item banks.',
    track: 'standards',
    state: 'available',
    lastSync: null,
    consequential: false,
  },
  {
    id: 'scorm',
    name: 'SCORM',
    summary: 'Packaged courseware import and completion tracking.',
    track: 'standards',
    state: 'error',
    lastSync: 'Last attempt failed 40 minutes ago',
    consequential: false,
  },
  {
    id: 'clever',
    name: 'Clever',
    summary: 'Single sign-on and roster sync from the identity bridge.',
    track: 'platform',
    state: 'enabled',
    lastSync: 'Synced 11 minutes ago',
    consequential: false,
  },
  {
    id: 'ed-fi',
    name: 'Ed-Fi',
    summary: 'District data standard for cross-system reporting.',
    track: 'platform',
    state: 'pending',
    lastSync: null,
    consequential: true,
  },
  {
    id: 'case',
    name: 'CASE',
    summary: 'Competencies and academic standards framework import.',
    track: 'standards',
    state: 'available',
    lastSync: null,
    consequential: false,
  },
  {
    id: 'mcp',
    name: 'MCP',
    summary: 'Model context bridge for tool and resource access.',
    track: 'platform',
    state: 'pending',
    lastSync: null,
    consequential: true,
  },
];

/** Map a connector state to a calm tag tone and a plain-language label. */
export const CONNECTOR_STATE_META: Record<
  ConnectorState,
  { tone: TagTone; label: string }
> = {
  enabled: { tone: 'success', label: 'Connected' },
  available: { tone: 'neutral', label: 'Available' },
  attention: { tone: 'warning', label: 'Needs a look' },
  error: { tone: 'danger', label: 'Sync failed' },
  pending: { tone: 'info', label: 'Awaiting approval' },
};

export const TRACK_LABEL: Record<ConnectorTrack, string> = {
  standards: 'Track 1 — open standards',
  platform: 'Track 2 — platform and edge',
};

/** Count connectors by health, for the hub summary stats. */
export function connectorHealth(connectors: Connector[] = CONNECTORS) {
  return {
    connected: connectors.filter((c) => c.state === 'enabled').length,
    awaitingApproval: connectors.filter((c) => c.state === 'pending').length,
    needsAttention: connectors.filter(
      (c) => c.state === 'attention' || c.state === 'error',
    ).length,
    total: connectors.length,
  };
}

/* ----------------------------------------------------- AI control centre */

/**
 * Model-usage rollup, split by track. Track 1 is external/standards-aligned
 * models; Track 2 is the proprietary/edge models. The two tracks NEVER share a
 * config block — they are reported, and governed, apart.
 */
export interface TrackUsage {
  track: ConnectorTrack;
  /** Plain-language label for the model family. Generic, no vendor lock-in. */
  modelLabel: string;
  /** Calls in the current window. */
  calls: number;
  /** Share of calls that passed the confidence gate (provisional-auto). */
  passed: number;
  /** Share withheld for human review by the gate. */
  withheld: number;
}

export const TRACK_USAGE: TrackUsage[] = [
  {
    track: 'standards',
    modelLabel: 'External reasoning model',
    calls: 4820,
    passed: 4316,
    withheld: 504,
  },
  {
    track: 'platform',
    modelLabel: 'Proprietary edge model',
    calls: 1960,
    passed: 1712,
    withheld: 248,
  },
];

/** Confidence-gate totals across both tracks. */
export function gateTotals(usage: TrackUsage[] = TRACK_USAGE) {
  const calls = usage.reduce((n, u) => n + u.calls, 0);
  const passed = usage.reduce((n, u) => n + u.passed, 0);
  const withheld = usage.reduce((n, u) => n + u.withheld, 0);
  return {
    calls,
    passed,
    withheld,
    /** Pass rate as a whole-number percent, clamped 0..100. */
    passRate: calls === 0 ? 0 : Math.round((passed / calls) * 100),
  };
}

/** A break-glass / lineage record — append-only, immutable, human-attributed. */
export interface LineageRecord {
  id: string;
  when: string;
  /** Role label of the human authority, never a real name. */
  actor: string;
  action: string;
  /** Whether this was a break-glass elevation. */
  breakGlass: boolean;
}

export const LINEAGE_LOG: LineageRecord[] = [
  {
    id: 'ln1',
    when: 'Today, 09:41',
    actor: 'Principal',
    action: 'Reviewed and released 12 withheld evaluations after a human read',
    breakGlass: false,
  },
  {
    id: 'ln2',
    when: 'Today, 08:02',
    actor: 'IT, Campus North',
    action: 'Engaged break-glass to inspect a failed roster sync; time-boxed',
    breakGlass: true,
  },
  {
    id: 'ln3',
    when: 'Yesterday, 17:20',
    actor: 'Coordinator, Campus North',
    action: 'Adjusted a confidence-gate threshold for short-answer marking',
    breakGlass: false,
  },
];

/* --------------------------------------------------- Teacher growth coaching */

/**
 * A teacher coaching signal — framed as growth, never judgement. Every signal
 * carries the teacher's own value, a calm range that good practice lives in, and
 * a plain-language read. There is no score, no ranking, no comparison to peers.
 */
export type GrowthDirection = 'in-range' | 'grow' | 'celebrate';

export interface GrowthSignal {
  id: string;
  label: string;
  /** Plain-language statement of what this signal measures. */
  meaning: string;
  /** The teacher's own current read, in plain language. */
  yourValue: string;
  /** What good practice tends to look like — a range, not a target to beat. */
  healthyRange: string;
  direction: GrowthDirection;
  /** A single, gentle next experiment to try. */
  tryThis: string;
}

export const GROWTH_SIGNALS: GrowthSignal[] = [
  {
    id: 'talk-ratio',
    label: 'Talk ratio',
    meaning: 'How much of the lesson is your voice versus the class talking.',
    yourValue: 'You spoke for most of the lesson',
    healthyRange: 'Lessons feel alive when students talk for around half',
    direction: 'grow',
    tryThis: 'Pick one explanation and let a pair reconstruct it aloud first.',
  },
  {
    id: 'questioning',
    label: 'Questioning',
    meaning: 'The mix of recall questions and questions that open thinking.',
    yourValue: 'Mostly recall, a few open prompts',
    healthyRange: 'A steady stream of open prompts keeps reasoning visible',
    direction: 'grow',
    tryThis: 'Follow one correct answer with a quiet "how did you know".',
  },
  {
    id: 'equity-of-voice',
    label: 'Equity of voice',
    meaning: 'Whether participation is spread or held by a few students.',
    yourValue: 'A handful of students carried the discussion',
    healthyRange: 'Most students contribute across a week',
    direction: 'grow',
    tryThis: 'Try a no-hands cold-warm call so quieter students get the floor.',
  },
  {
    id: 'wait-time',
    label: 'Wait time',
    meaning: 'The pause you leave after asking before taking an answer.',
    yourValue: 'You gave room to think after each question',
    healthyRange: 'A few unhurried seconds invites more considered answers',
    direction: 'celebrate',
    tryThis: 'Keep it. This is one of the hardest habits to build.',
  },
];

export const GROWTH_DIRECTION_META: Record<
  GrowthDirection,
  { tone: TagTone; label: string }
> = {
  'in-range': { tone: 'neutral', label: 'Holding steady' },
  grow: { tone: 'info', label: 'Room to grow' },
  celebrate: { tone: 'success', label: 'Working well' },
};

/** The single coaching insight to surface first — one at a time, never a list of failings. */
export function nextGrowthInsight(
  signals: GrowthSignal[] = GROWTH_SIGNALS,
): GrowthSignal | null {
  if (signals.length === 0) return null;
  // Lead with a growth signal if there is one; otherwise celebrate what works.
  return signals.find((s) => s.direction === 'grow') ?? signals[0]!;
}

/* ---------------------------------------------------- Network leadership view */

export type NetworkLevel = 'group' | 'region' | 'campus';

/**
 * A node in the group -> region -> campus tree. Each carries a mastery rollup
 * (plain-language share moving toward independent) and an intervention count,
 * so leadership manages by exception — only the nodes that need a look surface.
 */
export interface NetworkNode {
  id: string;
  level: NetworkLevel;
  label: string;
  /** Parent node id, or null for the group root. */
  parentId: string | null;
  /** Share of learners trending toward independent, 0..100 (a rollup, not a grade). */
  masteryTrend: number;
  /** Open interventions rolled up under this node. */
  openInterventions: number;
  /** True when this node is outside the calm band and needs a look. */
  needsAttention: boolean;
  /** Plain-language exception note when it needs attention. */
  exceptionNote?: string;
}

export const NETWORK_NODES: NetworkNode[] = [
  {
    id: 'grp',
    level: 'group',
    label: 'The group',
    parentId: null,
    masteryTrend: 71,
    openInterventions: 23,
    needsAttention: false,
  },
  {
    id: 'reg-n',
    level: 'region',
    label: 'Region North',
    parentId: 'grp',
    masteryTrend: 76,
    openInterventions: 8,
    needsAttention: false,
  },
  {
    id: 'reg-s',
    level: 'region',
    label: 'Region South',
    parentId: 'grp',
    masteryTrend: 64,
    openInterventions: 15,
    needsAttention: true,
    exceptionNote: 'Mastery trend is below the calm band for a second week.',
  },
  {
    id: 'cmp-n1',
    level: 'campus',
    label: 'Campus North One',
    parentId: 'reg-n',
    masteryTrend: 79,
    openInterventions: 3,
    needsAttention: false,
  },
  {
    id: 'cmp-n2',
    level: 'campus',
    label: 'Campus North Two',
    parentId: 'reg-n',
    masteryTrend: 73,
    openInterventions: 5,
    needsAttention: false,
  },
  {
    id: 'cmp-s1',
    level: 'campus',
    label: 'Campus South One',
    parentId: 'reg-s',
    masteryTrend: 58,
    openInterventions: 11,
    needsAttention: true,
    exceptionNote: 'Eleven open interventions and a falling trend; needs support.',
  },
  {
    id: 'cmp-s2',
    level: 'campus',
    label: 'Campus South Two',
    parentId: 'reg-s',
    masteryTrend: 70,
    openInterventions: 4,
    needsAttention: false,
  },
];

/** Children of a node, in declared order. */
export function childrenOf(
  parentId: string | null,
  nodes: NetworkNode[] = NETWORK_NODES,
): NetworkNode[] {
  return nodes.filter((n) => n.parentId === parentId);
}

/** Only the nodes leadership must look at — the manage-by-exception list. */
export function exceptions(nodes: NetworkNode[] = NETWORK_NODES): NetworkNode[] {
  return nodes.filter((n) => n.needsAttention);
}

/** The group root, or null if the tree is empty. */
export function networkRoot(nodes: NetworkNode[] = NETWORK_NODES): NetworkNode | null {
  return nodes.find((n) => n.level === 'group') ?? null;
}
