/* ============================================================================
   lib/vidya.ts — the browser side of the autonomous Vidya text orchestrator.

   Vidya is AI-native: the model reasons, then REQUESTS server-side tools that
   run against the real in-browser intelligence engine (lib/engine.ts) over the
   seed events (lib/loopData.ts) and the mock data layer (lib/mock.ts). The
   server route (app/api/vidya/chat/route.ts) runs the tool-use loop and returns
   Vidya's final text plus a small set of CLIENT ACTIONS:

     - navigate : route the user to a real page (the client uses next/navigation;
                  the server NEVER navigates and NEVER auto-fires anything).
     - render   : a small, typed component spec the thread renders inline
                  (a mastery card, a gap read, a recommendation, an approval
                  draft, or a plain explanation).

   PERMISSION LADDER: anything consequential (publishing a check, sending a
   message) returns requires_approval and never executes here. The human acts.

   GRACEFUL DEGRADATION: the route returns { degraded: true } whenever the
   provider key is unset or the provider fails. The caller then falls back to
   the offline responder (app/_components/respond.ts). This client NEVER throws
   on a transport/provider failure — it resolves to { degraded: true }.

   The provider key lives ONLY server-side (CLSS_AIFABRIC_DEV_GEMINI_API_KEY).
   It is never read, named for value, or exposed here.
   ============================================================================ */

import type { Role } from './mock';
import { readStore } from './store';
export type { Role } from './mock';

export const VIDYA_CHAT_ROUTE = '/api/vidya/chat';

/** A turn in the conversation as the orchestrator sees it. */
export interface VidyaTurn {
  role: 'user' | 'vidya';
  text: string;
}

/** The real, navigable routes Vidya may direct the client to. The orchestrator
 *  validates against this set; an unknown target is dropped, never followed. */
export const NAV_TARGETS = [
  '/',
  '/loop',
  '/teacher',
  '/teacher/assign',
  '/teacher/evaluate',
  '/teacher/students',
  '/teacher/attendance',
  '/teacher/plan',
  '/classroom',
  '/student/learn',
  '/student/practice',
  '/student/progress',
  '/student/mocks',
  '/student/work',
  '/student/portfolio',
  '/content',
  '/teacher/growth',
  '/admin',
  '/admin/intelligence',
  '/admin/exams',
  '/admin/curriculum',
  '/admin/governance',
  '/admin/network',
  '/admin/integrations',
  '/admin/calendar',
  '/admin/control-centre',
  '/admin/setup',
  '/messages',
  '/proactive',
  '/insights',
  '/parent',
  '/parent/child',
  '/parent/reports',
  '/parent/together',
  '/profile',
  '/settings',
  '/student',
] as const;

export type NavTarget = (typeof NAV_TARGETS)[number];

export function isNavTarget(value: unknown): value is NavTarget {
  return typeof value === 'string' && (NAV_TARGETS as readonly string[]).includes(value);
}

/** Plain-language labels for the navigable routes — the single source of truth
 *  reused by the command palette's "Go to" section. Mirrors the rail wording. */
export const NAV_LABELS: Record<NavTarget, string> = {
  '/': 'Home',
  '/loop': 'The live loop',
  '/teacher': 'Teacher — your day',
  '/teacher/assign': 'Assign a quick check',
  '/teacher/evaluate': 'Evaluation review',
  '/teacher/students': 'Student insights',
  '/teacher/attendance': 'Attendance',
  '/teacher/plan': 'Class diary and plan',
  '/teacher/growth': 'Your growth',
  '/classroom': 'Classroom delivery',
  '/student': 'Student — today',
  '/student/learn': 'Learn',
  '/student/practice': 'Practice',
  '/student/progress': 'Your progress',
  '/student/mocks': 'Mocks and study plan',
  '/student/work': 'Your work',
  '/student/portfolio': 'Portfolio and credentials',
  '/content': 'Resource library',
  '/admin': 'Admin — morning briefing',
  '/admin/intelligence': 'School-wide intelligence',
  '/admin/exams': 'Exam operations',
  '/admin/curriculum': 'Curriculum and ontology',
  '/admin/governance': 'Governance and audit',
  '/admin/network': 'Network leadership',
  '/admin/integrations': 'Integrations',
  '/admin/calendar': 'Calendar and timetable',
  '/admin/control-centre': 'AI control centre',
  '/admin/setup': 'Setup and hierarchy',
  '/messages': 'Messages',
  '/proactive': 'Approval queue',
  '/insights': 'Class read',
  '/parent': 'Parent — this week',
  '/parent/child': 'The child view',
  '/parent/reports': 'Reports and feedback',
  '/parent/together': 'Learn alongside and PTM',
  '/profile': 'Profile',
  '/settings': 'Settings',
};

// ---------------------------------------------------------------------------
// Render specs — the small, typed component shapes the thread can render inline.
// Each is calm and explainable; a learner never sees a raw number or formula.
// ---------------------------------------------------------------------------

export type RenderConfidence = 'high' | 'middle' | 'low';

/** A plain-language mastery read for one topic. Never a composite or formula. */
export interface MasteryCardSpec {
  kind: 'mastery';
  topic: string;
  subject?: string;
  /** The plain-language band phrase, e.g. "you can do this with guidance". */
  plainLanguage: string;
  /** Whether it is an unaided, independent demonstration. */
  independent: boolean;
  /** Whether spaced revision is due (strong-but-stale evidence). */
  revisionDue: boolean;
  /** The six dimensions as plain rows {label, level} — level in {strong,growing,early}. */
  dimensions: Array<{ label: string; level: 'strong' | 'growing' | 'early' }>;
  observationCount: number;
}

/** A plain-language read of the gaps on a topic, evidence-led, never one score. */
export interface GapsCardSpec {
  kind: 'gaps';
  topic: string;
  gaps: Array<{
    label: string;
    rationale: string;
    confidence: RenderConfidence;
    confirmed: boolean;
  }>;
}

/** A draft quick check, prepared for human approval — never auto-published. */
export interface DraftCardSpec {
  kind: 'draft';
  title: string;
  topic: string;
  body: string;
  items: string[];
  confidence: RenderConfidence;
  /** Always true: a quick check is consequential and waits for a human. */
  requiresApproval: true;
  /** Where the human goes to review and set it live. */
  openHref: NavTarget;
  openLabel: string;
}

/** One proactive recommendation with full explainability per the dossier. */
export interface RecommendationCardSpec {
  kind: 'recommendation';
  title: string;
  why: string;
  evidence: string[];
  confidence: RenderConfidence;
  owner: string;
  due: string;
  consequence: string;
}

/** A short, plain-language explanation that protects the struggle (a hint). */
export interface ExplainCardSpec {
  kind: 'explain';
  concept: string;
  body: string;
}

/**
 * One step in a self-assembling derivation/explanation. Each step is generate-
 * and-verified: when it carries a deterministic arithmetic claim (`check`), the
 * client (and the pure verifier) confirms it before it is ever revealed.
 */
export interface DerivationStep {
  /** The plain-language line spoken/shown for this step. */
  text: string;
  /**
   * Optional deterministic arithmetic check for this step, e.g.
   * { lhs: '1/2 + 1/4', rhs: '3/4' }. When present it MUST verify, or the step
   * is dropped — nothing unverified is ever shown or taught (generate-and-verify).
   */
  check?: { lhs: string; rhs: string };
}

/**
 * A self-assembling derivation — ordered steps that reveal one-by-one, synced to
 * the spoken reply. Each step is generate-and-verified before it is shown.
 */
export interface StepsCardSpec {
  kind: 'steps';
  title: string;
  topic?: string;
  steps: DerivationStep[];
}

// ---------------------------------------------------------------------------
// GENERATIVE-UI — the SURFACE spec set. Vidya can summon and OPERATE a real,
// working surface INLINE in the conversation ("make a quiz on photosynthesis"
// returns a working quiz-builder; "show 9-B" returns a class-view). The set is
// SMALL, TYPED, and VERIFIED — never arbitrary HTML. Each surface is sanitised
// at the boundary, and any CONSEQUENTIAL affordance inside it (publish a quiz,
// adopt a plan, send a report) holds the permission ladder: it returns
// requires_approval and never auto-fires from inside the surface.
// ---------------------------------------------------------------------------

/** The closed set of surfaces Vidya may compose. Unknown kinds are dropped. */
export const SURFACE_KINDS = ['quiz-builder', 'class-view', 'plan-board', 'report-card'] as const;
export type SurfaceKind = (typeof SURFACE_KINDS)[number];

/**
 * One editable item inside a quiz-builder surface. Plain text only; no HTML.
 * `answer` is the teacher's private key — it is never shown to a learner.
 */
export interface QuizItem {
  prompt: string;
  /** Optional multiple-choice options (bounded, plain text). */
  options?: string[];
  /** The teacher-facing answer/key (never surfaced to a learner). */
  answer?: string;
}

/**
 * A WORKING quiz builder, operable inline. The teacher can read/edit the items
 * in the conversation; PUBLISHING is consequential — `publish.requiresApproval`
 * is always true and `publish.action` only ever PREPARES, routing the human to
 * the review page. Nothing publishes from inside the surface.
 */
export interface QuizBuilderSurface {
  kind: 'quiz-builder';
  title: string;
  topic: string;
  items: QuizItem[];
  /** The consequential affordance — always behind the approval control. */
  publish: SurfaceAction;
}

/** One row in a read-only class view — a generic label + a plain mastery band. */
export interface ClassViewRow {
  label: string;
  band: string;
  /** A plain attention flag, not a score. */
  needsAttention?: boolean;
}

/** A read-only class-view surface ("show 9-B"). No consequential affordance. */
export interface ClassViewSurface {
  kind: 'class-view';
  title: string;
  section: string;
  rows: ClassViewRow[];
  /** Optional plain-language summary line. */
  summary?: string;
}

/** One column/day in a plan board. */
export interface PlanColumn {
  heading: string;
  cards: string[];
}

/**
 * A lesson-plan board, operable inline. ADOPTING the plan is consequential —
 * `adopt.requiresApproval` is true and only PREPARES.
 */
export interface PlanBoardSurface {
  kind: 'plan-board';
  title: string;
  topic: string;
  columns: PlanColumn[];
  adopt: SurfaceAction;
}

/** A read-only plain-language report card for a parent. No raw scores. */
export interface ReportCardSurface {
  kind: 'report-card';
  title: string;
  /** Generic child label, never a real name. */
  childLabel: string;
  /** Plain-language lines a parent can read at a glance. */
  highlights: string[];
  /** Optional next step in plain language. */
  nextStep?: string;
}

/**
 * A consequential affordance INSIDE a surface. The permission ladder holds:
 * requiresApproval is always true and the action only PREPARES (routes the
 * human to review). It NEVER carries an "execute now" capability.
 */
export interface SurfaceAction {
  label: string;
  /** Always true — a consequential surface affordance waits for a human. */
  requiresApproval: true;
  /** Where the human goes to review and act. The surface never acts itself. */
  openHref: NavTarget;
}

export type SurfaceSpec =
  | QuizBuilderSurface
  | ClassViewSurface
  | PlanBoardSurface
  | ReportCardSurface;

/** A composed-surface render: a typed, sanitised, operable surface inline. */
export interface SurfaceCardSpec {
  kind: 'surface';
  surface: SurfaceSpec;
}

export type RenderSpec =
  | MasteryCardSpec
  | GapsCardSpec
  | DraftCardSpec
  | RecommendationCardSpec
  | ExplainCardSpec
  | StepsCardSpec
  | SurfaceCardSpec;

// ---------------------------------------------------------------------------
// VIDYA CANVAS — the on-demand floating drawing surface Vidya summons ONLY when
// it needs to SHOW something (draw a diagram, work a derivation, sketch an
// explanation). Content is a small, BOUNDED set of structured primitives the
// client renders as self-assembling SVG — never free-arbitrary HTML. The model
// emits the structure; the client draws it. Stroke-draw paths animate in; with
// prefers-reduced-motion everything appears at once.
// ---------------------------------------------------------------------------

/** A straight ink stroke between two points (canvas coordinate space 0..100). */
export interface CanvasLine {
  kind: 'line';
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  /** Optional plain label pinned at the midpoint. */
  label?: string;
}

/** An arc / curve (e.g. an angle mark or a smooth bend) drawn as an SVG arc. */
export interface CanvasArc {
  kind: 'arc';
  cx: number;
  cy: number;
  r: number;
  /** Start and end angle in degrees (0 = east, counter-clockwise positive). */
  startDeg: number;
  endDeg: number;
  label?: string;
}

/** An arrow (a line with a head) — for vectors, mappings, "this leads to". */
export interface CanvasArrow {
  kind: 'arrow';
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  label?: string;
}

/** A free-standing plain-language label placed on the canvas. */
export interface CanvasLabel {
  kind: 'label';
  x: number;
  y: number;
  text: string;
  /** A human-note "Caveat" annotation (script feel) vs a plain ink label. */
  annotation?: boolean;
}

/** A simple shape outline (rectangle, circle, triangle) by its bounding box. */
export interface CanvasShape {
  kind: 'shape';
  shape: 'rect' | 'circle' | 'triangle';
  x: number;
  y: number;
  w: number;
  h: number;
  label?: string;
}

/** A number line from `from` to `to` with optional ticked points. */
export interface CanvasNumberLine {
  kind: 'numberline';
  from: number;
  to: number;
  /** Marked points, each value within [from, to], with a short label. */
  points?: Array<{ value: number; label?: string }>;
}

/** A simple line graph of plotted points in the canvas coordinate space. */
export interface CanvasGraph {
  kind: 'graph';
  /** Ordered points (x,y in 0..100) drawn as a stroked polyline. */
  points: Array<{ x: number; y: number }>;
  xLabel?: string;
  yLabel?: string;
}

export type CanvasPrimitive =
  | CanvasLine
  | CanvasArc
  | CanvasArrow
  | CanvasLabel
  | CanvasShape
  | CanvasNumberLine
  | CanvasGraph;

export const CANVAS_PRIMITIVE_KINDS = new Set([
  'line',
  'arc',
  'arrow',
  'label',
  'shape',
  'numberline',
  'graph',
]);

/** The bounded content kinds the canvas can render. */
export type CanvasContent =
  /** A self-assembling, verified derivation rendered large on the canvas. */
  | { type: 'derivation'; steps: DerivationStep[] }
  /** A drawing built from a small set of SVG primitives. */
  | { type: 'diagram'; primitives: CanvasPrimitive[] }
  /** A written explanation that "writes on" — plain lines, handwriting feel. */
  | { type: 'written'; lines: string[] };

/**
 * One source / piece of evidence shown ALONGSIDE the answer on the canvas. The
 * verifier and the dossier require an answer to be evidence-led; this surfaces
 * the provenance the model leaned on (a topic, an observation, a reference). It
 * is plain text + an optional real in-app route — never an arbitrary URL.
 */
export interface CanvasSource {
  /** A short, plain-language label, e.g. "Your last three attempts on fractions". */
  label: string;
  /** An optional one-line note on why this source is relevant. */
  note?: string;
  /** An optional real in-app route the source lives on (validated to NAV_TARGETS). */
  href?: NavTarget;
}

/**
 * A floating-canvas spec — what Vidya wants SHOWN. It is a render kind so it
 * flows through the same action union, but the client routes it to the dedicated
 * VidyaCanvas surface (not an inline thread card).
 */
export interface CanvasCardSpec {
  kind: 'canvas';
  title: string;
  content: CanvasContent;
  /** An optional real page the canvas content also lives on ("open in its page"). */
  openHref?: NavTarget;
  openLabel?: string;
  /**
   * The sources / evidence shown beside the answer. Surfaced so the answer is
   * always explainable (evidence-led, per the dossier). Bounded + sanitised.
   */
  sources?: CanvasSource[];
}

// ---------------------------------------------------------------------------
// Client actions — the directives the route returns alongside Vidya's text.
// ---------------------------------------------------------------------------

export interface NavigateAction {
  type: 'navigate';
  target: NavTarget;
  /** A calm one-liner shown before the route changes. */
  reason?: string;
}

export interface RenderAction {
  type: 'render';
  spec: RenderSpec;
}

/**
 * Open the floating canvas and render structured content on it. This is the
 * "show it" action — Vidya summons the canvas only when the answer needs to be
 * DRAWN/DERIVED/SKETCHED, not for a simple spoken or short reply.
 */
export interface CanvasAction {
  type: 'canvas';
  spec: CanvasCardSpec;
}

// ---------------------------------------------------------------------------
// Speak-and-show — the structured visual actions Vidya returns so it can TEACH
// while it speaks: ring a region on the page, pin a calm margin note, or
// self-assemble a verified derivation step-by-step inside the orb panel.
// ---------------------------------------------------------------------------

/**
 * A named, highlightable on-screen region. The orb resolves a region to a real
 * element by its data-testid (preferred) or id, then rings/spotlights it. The
 * map is closed: an unknown region is dropped, never highlighted, so "look at
 * your trigonometry mastery" can only land on a registered, real target.
 */
export const HIGHLIGHT_REGIONS = {
  'mastery-band': 'The mastery band on the current view.',
  'topic-card': 'A topic card on the learn/practice surface.',
  'gap-list': 'The list of detected gaps.',
  'progress-stat': 'A headline progress statistic.',
  'recommendation': 'A proactive recommendation.',
  'approval-queue': 'The pending-approval queue.',
  'class-roster': 'The class roster / student list.',
  'attendance': 'The attendance capture.',
  'assignment': 'An assignment in the work inbox.',
  'portfolio-item': 'A portfolio credential or mastered-topic entry.',
  'vidya-steps': 'The self-assembling derivation inside the Vidya panel.',
} as const;

export type HighlightRegion = keyof typeof HIGHLIGHT_REGIONS;

export function isHighlightRegion(value: unknown): value is HighlightRegion {
  return typeof value === 'string' && Object.prototype.hasOwnProperty.call(HIGHLIGHT_REGIONS, value);
}

/**
 * Ring / spotlight a named on-screen region while Vidya speaks about it. Visual
 * only — it never mutates anything, so it is always safe on the voice path too.
 */
export interface HighlightAction {
  type: 'highlight';
  region: HighlightRegion;
  /** A calm one-liner shown beside the ring, e.g. "this is where you stand". */
  label?: string;
}

/**
 * Pin a small, calm margin note near a region — the human-note "Caveat" feel.
 * Used sparingly, for a single load-bearing aside. Visual only, always safe.
 */
export interface AnnotateAction {
  type: 'annotate';
  region: HighlightRegion;
  /** The short note text (one calm line; no emoji, no exclamation). */
  note: string;
}

export type VidyaAction =
  | NavigateAction
  | RenderAction
  | CanvasAction
  | HighlightAction
  | AnnotateAction;

/** The orchestrator's reply. `degraded` signals the caller to fall back. */
export interface VidyaChatResult {
  text: string;
  actions: VidyaAction[];
  degraded?: boolean;
  /** Internal reason on degrade (never a key, never a stack). */
  reason?: string;
}

// ---------------------------------------------------------------------------
// THE 5-PATH GENERATIVE-UI CLASSIFIER CONTRACT (spec 16.2).
//
// A request enters via the composer, a chip, voice, or Cmd-K. The orchestrator
// classifies it and takes EXACTLY ONE of five paths. The taxonomy is the
// contract the surface builds to. Rather than re-derive intent on the client,
// this is a PURE projection of the actions the orchestrator already returned
// onto the five-path taxonomy — one truth, no divergence between what the
// orchestrator did and how the home/dock describes it.
//
//   Path 1 — answer    : prose in the thread (+ sources + ConfidenceBand). No
//                        component manufactured. (no render/canvas/navigate.)
//   Path 2 — compose   : a live, verified component in-thread (border-draw
//                        reveal) — a surface, a derivation/canvas, a mastery/
//                        gaps/recommendation card. Carries ConfidenceBand +
//                        "Why this" + a primary action + "Open in <page>".
//   Path 3 — act        : the request is a task; Vidya PREPARES it and surfaces
//                        an ApprovalControl for anything consequential (a draft
//                        quick-check/plan, a composed quiz/plan-board the human
//                        must approve). The ladder is never bypassed in chat.
//   Path 4 — route+dock : the task needs a full workspace; Vidya opens the page
//                        and DOCKS itself (VidyaDock), pre-filled with context.
//   Path 5 — route+guide: the user MUST act (a decision, a credential, a manual
//                        step); Vidya routes AND draws an on-screen SVG guide —
//                        soft spotlight + hairline arrow + caption (VidyaSpotlight).
//
// When ambiguous, Vidya asks ONE clarifying question rather than guessing —
// that is a Path-1 answer with no actions (handled by the orchestrator prompt).
// ---------------------------------------------------------------------------

export type VidyaPath =
  | 'answer' // Path 1
  | 'compose' // Path 2
  | 'act' // Path 3
  | 'route-dock' // Path 4
  | 'route-guide'; // Path 5

/** True when a render spec is a CONSEQUENTIAL prepare — it carries an approval
 *  step (a draft) or a surface whose primary affordance is permission-laddered
 *  (a quiz to publish, a plan-board to adopt). Path 3 is exactly this set. */
function isConsequentialRender(spec: RenderSpec): boolean {
  if (spec.kind === 'draft') return true; // requiresApproval is always true
  if (spec.kind === 'surface') {
    return spec.surface.kind === 'quiz-builder' || spec.surface.kind === 'plan-board';
  }
  return false;
}

/**
 * Classify a turn into exactly one of the five paths from the actions the
 * orchestrator returned. Precedence (highest first) honours the spec decision
 * rule "the user must act → Path 5; needs a workspace → Path 4; an action Vidya
 * may take → Path 3; a view helps → Path 2; answerable → Path 1":
 *
 *   navigate + (highlight|annotate) -> route-guide  (Path 5: route + SVG guide)
 *   navigate alone                   -> route-dock   (Path 4: route + dock)
 *   render/canvas that is consequential -> act       (Path 3: prepare + approve)
 *   render/canvas otherwise          -> compose      (Path 2: live component)
 *   nothing renders/routes           -> answer       (Path 1: prose; clarify too)
 *
 * Pure and deterministic — the same projection on the home and the dock, so the
 * thread's "what just happened" line never disagrees with what Vidya did.
 */
export function classifyPath(actions: VidyaAction[]): VidyaPath {
  const navigates = actions.some((a) => a.type === 'navigate');
  const guides = actions.some((a) => a.type === 'highlight' || a.type === 'annotate');
  if (navigates && guides) return 'route-guide';
  if (navigates) return 'route-dock';
  const renders = actions.filter(
    (a): a is RenderAction | CanvasAction => a.type === 'render' || a.type === 'canvas',
  );
  if (renders.length > 0) {
    const consequential = renders.some((a) => a.type === 'render' && isConsequentialRender(a.spec));
    return consequential ? 'act' : 'compose';
  }
  return 'answer';
}

/** A calm, plain-language line naming the path Vidya took — shown quietly in the
 *  thread so the taxonomy is legible (spec 16.2). No orchestrator name; no PII. */
export function pathSummary(path: VidyaPath): string {
  switch (path) {
    case 'answer':
      return 'Answered inline';
    case 'compose':
      return 'Composed a live, verified view';
    case 'act':
      return 'Prepared this for your approval';
    case 'route-dock':
      return 'Opened the page and docked here';
    case 'route-guide':
      return 'Opened the page and drew the steps';
  }
}

/**
 * A MULTIMODAL attachment the orchestrator can understand: an image, a document,
 * or a screen capture. The bytes are base64 (no data: prefix); mimeType names
 * the kind. The orchestrator routes these to a multimodal model server-side and
 * degrades cleanly when no key is configured. Bounded + validated at the route.
 */
export interface VidyaAttachment {
  /** How the attachment was supplied — shapes the orchestrator's framing. */
  kind: 'image' | 'document' | 'screen';
  /** The IANA mime type, e.g. "image/png", "application/pdf". */
  mimeType: string;
  /** Base64-encoded bytes (NO data: prefix). */
  dataBase64: string;
  /** An optional, non-PII caption/filename hint. */
  name?: string;
}

/** The accepted attachment mime prefixes — anything else is rejected server-side. */
export const ATTACHMENT_MIME_PREFIXES = ['image/', 'application/pdf', 'text/'] as const;

/**
 * The hard upper bound on a single attachment's base64 payload length. The whole
 * staged set is POSTed inline to /api/vidya/chat and pushed verbatim as Gemini
 * inlineData, so an oversized image/PDF balloons the request body and risks a 413
 * from the Next/Vercel body-size limit (~4MB default). We cap a single base64
 * payload at ~5MB of characters (~3.7MB of raw bytes) so the orb never silently
 * stalls on a huge read; the route rejects anything above this too.
 */
export const MAX_ATTACH_BYTES = 5_000_000 as const;

/** Validate a multimodal attachment shape (defensive, used on both sides). */
export function isValidAttachment(value: unknown): value is VidyaAttachment {
  if (!value || typeof value !== 'object') return false;
  const a = value as Record<string, unknown>;
  if (a.kind !== 'image' && a.kind !== 'document' && a.kind !== 'screen') return false;
  if (typeof a.mimeType !== 'string') return false;
  if (!ATTACHMENT_MIME_PREFIXES.some((p) => (a.mimeType as string).startsWith(p))) return false;
  if (typeof a.dataBase64 !== 'string' || a.dataBase64.length === 0) return false;
  // Bound the payload so a large attachment can never balloon the request body.
  if (a.dataBase64.length > MAX_ATTACH_BYTES) return false;
  return true;
}

export interface VidyaChatRequest {
  messages: VidyaTurn[];
  role: Role;
  /**
   * Optional MULTIMODAL inputs attached to the latest turn (image/doc/screen).
   * The orchestrator understands them; with no multimodal key it degrades.
   */
  attachments?: VidyaAttachment[];
  /**
   * The OPAQUE account id (lib/store) — keys persistent per-user memory. Never
   * real PII. Absent for an anonymous turn (memory then stays empty).
   */
  accountId?: string;
  /**
   * Whether the holder consented to personalization. Memory is only recalled and
   * persisted when this is true (the consent gate, mirrored on the server).
   */
  memoryConsent?: boolean;
  /**
   * The PII-free salient-memory addendum the client distilled from the per-user
   * memory slice (lib/vidyaMemory). The route redacts it again and feeds it to
   * the orchestrator so Vidya is conditioned on who it is talking to. Empty when
   * there is nothing to recall or consent is off.
   */
  memoryNote?: string;
}

// ---------------------------------------------------------------------------
// Action parsing — the route returns JSON, but a defensive parser keeps the
// client crash-proof against a malformed action (drops unknown targets/specs).
// ---------------------------------------------------------------------------

const RENDER_KINDS = new Set(['mastery', 'gaps', 'draft', 'recommendation', 'explain', 'steps', 'surface']);

export function parseActions(raw: unknown): VidyaAction[] {
  if (!Array.isArray(raw)) return [];
  const out: VidyaAction[] = [];
  for (const a of raw) {
    if (!a || typeof a !== 'object') continue;
    const action = a as Record<string, unknown>;
    if (action.type === 'navigate' && isNavTarget(action.target)) {
      out.push({
        type: 'navigate',
        target: action.target,
        reason: typeof action.reason === 'string' ? action.reason : undefined,
      });
    } else if (action.type === 'render' && action.spec && typeof action.spec === 'object') {
      const spec = action.spec as Record<string, unknown>;
      if (typeof spec.kind === 'string' && RENDER_KINDS.has(spec.kind)) {
        // A steps spec is generate-and-verified at the boundary: any step that
        // carries a deterministic check that does NOT verify is dropped, so the
        // client never reveals an unverified teaching step.
        if (spec.kind === 'steps') {
          out.push({ type: 'render', spec: sanitiseSteps(spec) });
        } else if (spec.kind === 'surface') {
          // A composed surface is sanitised to the closed spec set; a malformed
          // or unknown surface is dropped entirely (never arbitrary content).
          const surface = sanitiseSurface(spec.surface);
          if (surface) out.push({ type: 'render', spec: { kind: 'surface', surface } });
        } else {
          out.push({ type: 'render', spec: spec as unknown as RenderSpec });
        }
      }
    } else if (action.type === 'canvas' && action.spec && typeof action.spec === 'object') {
      const spec = sanitiseCanvas(action.spec as Record<string, unknown>);
      // Only push a canvas that has something real to show after sanitisation.
      if (canvasHasContent(spec)) out.push({ type: 'canvas', spec });
    } else if (action.type === 'highlight' && isHighlightRegion(action.region)) {
      out.push({
        type: 'highlight',
        region: action.region,
        label: typeof action.label === 'string' ? action.label : undefined,
      });
    } else if (
      action.type === 'annotate' &&
      isHighlightRegion(action.region) &&
      typeof action.note === 'string' &&
      action.note.trim().length > 0
    ) {
      out.push({ type: 'annotate', region: action.region, note: action.note.trim() });
    }
  }
  return out;
}

/** Drop any derivation step whose deterministic check fails — generate-and-verify
 *  at the boundary so an unverified teaching step is never revealed. */
function sanitiseSteps(spec: Record<string, unknown>): StepsCardSpec {
  const rawSteps = Array.isArray(spec.steps) ? spec.steps : [];
  const steps: DerivationStep[] = [];
  for (const s of rawSteps) {
    if (!s || typeof s !== 'object') continue;
    const step = s as Record<string, unknown>;
    if (typeof step.text !== 'string' || step.text.trim().length === 0) continue;
    const check =
      step.check && typeof step.check === 'object'
        ? (step.check as { lhs?: unknown; rhs?: unknown })
        : undefined;
    if (check && typeof check.lhs === 'string' && typeof check.rhs === 'string') {
      if (!verifyStep(check.lhs, check.rhs)) continue; // unverified -> dropped
      steps.push({ text: step.text, check: { lhs: check.lhs, rhs: check.rhs } });
    } else {
      steps.push({ text: step.text });
    }
  }
  return {
    kind: 'steps',
    title: typeof spec.title === 'string' ? spec.title : 'Step by step',
    topic: typeof spec.topic === 'string' ? spec.topic : undefined,
    steps,
  };
}

// ---------------------------------------------------------------------------
// Surface sanitisation — the trust boundary for generative-UI. The model emits
// a typed surface; this clamps it to the CLOSED spec set, trims/bounds every
// field, drops anything unknown, and — crucially — REBUILDS any consequential
// affordance from scratch so the permission ladder cannot be overridden by the
// model: requiresApproval is forced true and openHref is validated against the
// real route set. A surface that does not parse to a known kind is dropped.
// ---------------------------------------------------------------------------

/** Cap an array of strings: trim, drop empties, bound count + length. */
function trimList(raw: unknown, maxItems: number, maxLen = 240): string[] {
  if (!Array.isArray(raw)) return [];
  const out: string[] = [];
  for (const v of raw) {
    const s = typeof v === 'string' ? v.trim().slice(0, maxLen) : '';
    if (s) out.push(s);
    if (out.length >= maxItems) break;
  }
  return out;
}

/**
 * Build a consequential SurfaceAction from the model's suggestion, FORCING the
 * permission ladder: requiresApproval is always true; openHref must be a real
 * route (defaults to a safe fallback) — the surface can only ever route a human
 * to review, never execute. The label is sanitised plain text.
 */
function buildSurfaceAction(raw: unknown, fallbackHref: NavTarget, fallbackLabel: string): SurfaceAction {
  const r = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const label = trimStr(r.label) ?? fallbackLabel;
  const openHref = isNavTarget(r.openHref) ? r.openHref : fallbackHref;
  return { label, requiresApproval: true, openHref };
}

/** Sanitise the composed-surface spec to the closed set; null if unrecognised. */
export function sanitiseSurface(raw: unknown): SurfaceSpec | null {
  if (!raw || typeof raw !== 'object') return null;
  const s = raw as Record<string, unknown>;
  const kind = s.kind;
  if (typeof kind !== 'string' || !(SURFACE_KINDS as readonly string[]).includes(kind)) return null;

  switch (kind) {
    case 'quiz-builder': {
      const rawItems = Array.isArray(s.items) ? s.items : [];
      const items: QuizItem[] = [];
      for (const it of rawItems.slice(0, 12)) {
        if (!it || typeof it !== 'object') continue;
        const item = it as Record<string, unknown>;
        const prompt = trimStr(item.prompt);
        if (!prompt) continue;
        items.push({
          prompt,
          options: item.options !== undefined ? trimList(item.options, 6, 160) : undefined,
          answer: trimStr(item.answer),
        });
      }
      if (items.length === 0) return null; // a quiz with nothing to ask is dropped
      return {
        kind: 'quiz-builder',
        title: trimStr(s.title) ?? 'Quick check',
        topic: trimStr(s.topic) ?? 'this topic',
        items,
        publish: buildSurfaceAction(s.publish, '/teacher/assign', 'Review and set live'),
      };
    }
    case 'class-view': {
      const rawRows = Array.isArray(s.rows) ? s.rows : [];
      const rows: ClassViewRow[] = [];
      for (const rw of rawRows.slice(0, 60)) {
        if (!rw || typeof rw !== 'object') continue;
        const row = rw as Record<string, unknown>;
        const label = trimStr(row.label);
        if (!label) continue;
        rows.push({ label, band: trimStr(row.band) ?? 'no read yet', needsAttention: row.needsAttention === true });
      }
      return {
        kind: 'class-view',
        title: trimStr(s.title) ?? 'Class view',
        section: trimStr(s.section) ?? 'this class',
        rows,
        summary: trimStr(s.summary),
      };
    }
    case 'plan-board': {
      const rawCols = Array.isArray(s.columns) ? s.columns : [];
      const columns: PlanColumn[] = [];
      for (const cl of rawCols.slice(0, 8)) {
        if (!cl || typeof cl !== 'object') continue;
        const col = cl as Record<string, unknown>;
        const heading = trimStr(col.heading);
        if (!heading) continue;
        columns.push({ heading, cards: trimList(col.cards, 10) });
      }
      if (columns.length === 0) return null;
      return {
        kind: 'plan-board',
        title: trimStr(s.title) ?? 'Lesson plan',
        topic: trimStr(s.topic) ?? 'this topic',
        columns,
        adopt: buildSurfaceAction(s.adopt, '/teacher/plan', 'Review and adopt'),
      };
    }
    case 'report-card': {
      const highlights = trimList(s.highlights, 8);
      if (highlights.length === 0) return null;
      return {
        kind: 'report-card',
        title: trimStr(s.title) ?? 'How your child is doing',
        childLabel: trimStr(s.childLabel) ?? 'your child',
        highlights,
        nextStep: trimStr(s.nextStep),
      };
    }
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Canvas sanitisation — the model emits structured canvas content; this is the
// boundary that keeps it BOUNDED and safe: unknown content/primitive kinds are
// dropped, coordinates are clamped to the 0..100 canvas space, text is trimmed,
// and a derivation reuses the SAME generate-and-verify gate as inline steps (a
// step whose deterministic check fails is dropped — never shown or drawn).
// ---------------------------------------------------------------------------

/** Clamp a numeric field into [min,max]; non-finite -> the lower bound. */
function clampNum(v: unknown, min = 0, max = 100): number {
  const n = Number(v);
  if (!Number.isFinite(n)) return min;
  return Math.max(min, Math.min(max, n));
}

function trimStr(v: unknown): string | undefined {
  return typeof v === 'string' && v.trim().length > 0 ? v.trim() : undefined;
}

/** Sanitise one canvas primitive; returns null if it is not a known/usable shape. */
function sanitisePrimitive(raw: unknown): CanvasPrimitive | null {
  if (!raw || typeof raw !== 'object') return null;
  const p = raw as Record<string, unknown>;
  const kind = p.kind;
  if (typeof kind !== 'string' || !CANVAS_PRIMITIVE_KINDS.has(kind)) return null;
  switch (kind) {
    case 'line':
      return {
        kind: 'line',
        x1: clampNum(p.x1),
        y1: clampNum(p.y1),
        x2: clampNum(p.x2),
        y2: clampNum(p.y2),
        label: trimStr(p.label),
      };
    case 'arrow':
      return {
        kind: 'arrow',
        x1: clampNum(p.x1),
        y1: clampNum(p.y1),
        x2: clampNum(p.x2),
        y2: clampNum(p.y2),
        label: trimStr(p.label),
      };
    case 'arc':
      return {
        kind: 'arc',
        cx: clampNum(p.cx),
        cy: clampNum(p.cy),
        r: clampNum(p.r, 0, 100),
        startDeg: clampNum(p.startDeg, -360, 360),
        endDeg: clampNum(p.endDeg, -360, 360),
        label: trimStr(p.label),
      };
    case 'label': {
      const text = trimStr(p.text);
      if (!text) return null;
      return {
        kind: 'label',
        x: clampNum(p.x),
        y: clampNum(p.y),
        text,
        annotation: p.annotation === true,
      };
    }
    case 'shape': {
      const shape = p.shape;
      if (shape !== 'rect' && shape !== 'circle' && shape !== 'triangle') return null;
      return {
        kind: 'shape',
        shape,
        x: clampNum(p.x),
        y: clampNum(p.y),
        w: clampNum(p.w, 0, 100),
        h: clampNum(p.h, 0, 100),
        label: trimStr(p.label),
      };
    }
    case 'numberline': {
      const from = clampNum(p.from, -1e6, 1e6);
      const to = clampNum(p.to, -1e6, 1e6);
      const rawPts = Array.isArray(p.points) ? p.points : [];
      const points = rawPts
        .filter((pt): pt is Record<string, unknown> => !!pt && typeof pt === 'object')
        .map((pt) => ({ value: Number(pt.value), label: trimStr(pt.label) }))
        .filter((pt) => Number.isFinite(pt.value))
        .slice(0, 12);
      return { kind: 'numberline', from, to, points };
    }
    case 'graph': {
      const rawPts = Array.isArray(p.points) ? p.points : [];
      const points = rawPts
        .filter((pt): pt is Record<string, unknown> => !!pt && typeof pt === 'object')
        .map((pt) => ({ x: clampNum(pt.x), y: clampNum(pt.y) }))
        .slice(0, 64);
      if (points.length < 2) return null;
      return { kind: 'graph', points, xLabel: trimStr(p.xLabel), yLabel: trimStr(p.yLabel) };
    }
    default:
      return null;
  }
}

/** Sanitise the canvas content union — bounded, with the verify gate on steps. */
function sanitiseCanvasContent(raw: unknown): CanvasContent | null {
  if (!raw || typeof raw !== 'object') return null;
  const c = raw as Record<string, unknown>;
  if (c.type === 'derivation') {
    // Reuse the SAME verify gate as inline steps: drop any unverified step.
    const steps = sanitiseSteps({ steps: c.steps, title: 'derivation' }).steps;
    return { type: 'derivation', steps };
  }
  if (c.type === 'diagram') {
    const rawPrims = Array.isArray(c.primitives) ? c.primitives : [];
    const primitives: CanvasPrimitive[] = [];
    for (const r of rawPrims.slice(0, 48)) {
      const prim = sanitisePrimitive(r);
      if (prim) primitives.push(prim);
    }
    return { type: 'diagram', primitives };
  }
  if (c.type === 'written') {
    const rawLines = Array.isArray(c.lines) ? c.lines : [];
    const lines = rawLines
      .map((l) => (typeof l === 'string' ? l.trim() : ''))
      .filter((l) => l.length > 0)
      .slice(0, 24);
    return { type: 'written', lines };
  }
  return null;
}

/** Sanitise the canvas sources/evidence — bounded, plain text, real routes only. */
function sanitiseCanvasSources(raw: unknown): CanvasSource[] {
  if (!Array.isArray(raw)) return [];
  const out: CanvasSource[] = [];
  for (const r of raw.slice(0, 8)) {
    if (!r || typeof r !== 'object') continue;
    const s = r as Record<string, unknown>;
    const label = trimStr(s.label);
    if (!label) continue;
    out.push({
      label: label.slice(0, 160),
      note: trimStr(s.note)?.slice(0, 240),
      href: isNavTarget(s.href) ? s.href : undefined,
    });
  }
  return out;
}

/** Sanitise a full canvas spec at the trust boundary. */
export function sanitiseCanvas(spec: Record<string, unknown>): CanvasCardSpec {
  const content = sanitiseCanvasContent(spec.content) ?? { type: 'written', lines: [] };
  const sources = sanitiseCanvasSources(spec.sources);
  return {
    kind: 'canvas',
    title: typeof spec.title === 'string' && spec.title.trim() ? spec.title.trim() : 'On the canvas',
    content,
    openHref: isNavTarget(spec.openHref) ? spec.openHref : undefined,
    openLabel: trimStr(spec.openLabel),
    sources: sources.length > 0 ? sources : undefined,
  };
}

/** Whether a sanitised canvas spec has anything real to draw. */
export function canvasHasContent(spec: CanvasCardSpec): boolean {
  const c = spec.content;
  if (c.type === 'derivation') return c.steps.length > 0;
  if (c.type === 'diagram') return c.primitives.length > 0;
  if (c.type === 'written') return c.lines.length > 0;
  return false;
}

// ---------------------------------------------------------------------------
// Deterministic step verification — the generate-and-verify gate for a taught
// step. A pure, safe arithmetic evaluator (no eval): it parses + evaluates a
// rational arithmetic expression (digits, + - * /, parentheses, fractions) and
// confirms lhs == rhs exactly under rational arithmetic. Anything it cannot
// parse is treated as UNVERIFIED (returns false) — never trusted by default.
// ---------------------------------------------------------------------------

type Rational = { n: number; d: number };

const gcd = (a: number, b: number): number => (b === 0 ? Math.abs(a) : gcd(b, a % b));

function norm(r: Rational): Rational {
  if (r.d === 0) return { n: NaN, d: 1 };
  let { n, d } = r;
  if (d < 0) {
    n = -n;
    d = -d;
  }
  const g = gcd(n, d) || 1;
  return { n: n / g, d: d / g };
}

/** Evaluate a rational arithmetic expression. Returns null if it cannot parse
 *  (which the verifier treats as unverified). */
export function evalRational(expr: string): Rational | null {
  const src = expr.replace(/\s+/g, '');
  if (src.length === 0) return null;
  if (!/^[0-9+\-*/().]+$/.test(src)) return null;
  let i = 0;

  function parseExpr(): Rational | null {
    let left = parseTerm();
    if (!left) return null;
    while (i < src.length && (src[i] === '+' || src[i] === '-')) {
      const op = src[i++];
      const right = parseTerm();
      if (!right) return null;
      left =
        op === '+'
          ? norm({ n: left.n * right.d + right.n * left.d, d: left.d * right.d })
          : norm({ n: left.n * right.d - right.n * left.d, d: left.d * right.d });
    }
    return left;
  }

  function parseTerm(): Rational | null {
    let left = parseFactor();
    if (!left) return null;
    while (i < src.length && (src[i] === '*' || src[i] === '/')) {
      const op = src[i++];
      const right = parseFactor();
      if (!right) return null;
      if (op === '*') left = norm({ n: left.n * right.n, d: left.d * right.d });
      else {
        if (right.n === 0) return null; // division by zero -> unverified
        left = norm({ n: left.n * right.d, d: left.d * right.n });
      }
    }
    return left;
  }

  function parseFactor(): Rational | null {
    if (src[i] === '+') {
      i++;
      return parseFactor();
    }
    if (src[i] === '-') {
      i++;
      const f = parseFactor();
      return f ? { n: -f.n, d: f.d } : null;
    }
    if (src[i] === '(') {
      i++;
      const e = parseExpr();
      if (!e || src[i] !== ')') return null;
      i++;
      return e;
    }
    // a number (integer or decimal)
    const start = i;
    while (i < src.length && /[0-9.]/.test(src[i]!)) i++;
    if (i === start) return null;
    const tok = src.slice(start, i);
    if ((tok.match(/\./g)?.length ?? 0) > 1) return null;
    if (tok.includes('.')) {
      const [whole, frac = ''] = tok.split('.');
      const d = Math.pow(10, frac.length);
      return norm({ n: Number(whole + frac), d });
    }
    return { n: Number(tok), d: 1 };
  }

  const result = parseExpr();
  if (!result || i !== src.length || Number.isNaN(result.n)) return null;
  return result;
}

/**
 * The deterministic generate-and-verify gate for one taught step: is lhs == rhs
 * under exact rational arithmetic? Returns false for anything it cannot parse,
 * so an unverifiable claim is never presented as verified.
 */
export function verifyStep(lhs: string, rhs: string): boolean {
  const a = evalRational(lhs);
  const b = evalRational(rhs);
  if (!a || !b) return false;
  return a.n * b.d === b.n * a.d;
}

// ---------------------------------------------------------------------------
// Render spec -> inline card data. The thread renders one generative card per
// vidya turn (the InlineResult SpotlightCard). This maps each typed spec to that
// calm, plain-language shape — a learner never sees a raw number or formula.
// ---------------------------------------------------------------------------

/** The shape the thread's InlineResult renders. Kept structural so this module
 *  stays free of a React/component import. */
export interface InlineCard {
  title: string;
  body: string;
  items?: string[];
  confidence?: RenderConfidence;
  openHref?: string;
  openLabel?: string;
}

const LEVEL_WORD: Record<'strong' | 'growing' | 'early', string> = {
  strong: 'strong',
  growing: 'growing',
  early: 'still early',
};

/** Convert a render spec to the inline card the thread shows. Returns null for a
 *  spec that carries no useful card (kept defensive against a malformed shape). */
export function specToInline(spec: RenderSpec): InlineCard | null {
  switch (spec.kind) {
    case 'mastery':
      return {
        title: `Where you stand — ${spec.topic}`,
        body: spec.plainLanguage,
        items: [
          spec.independent
            ? 'You can do this on your own, consistently.'
            : 'This still leans on a little support.',
          ...(spec.revisionDue ? ['A short revision is due to keep it fresh.'] : []),
          ...spec.dimensions.map((d) => `${d.label} — ${LEVEL_WORD[d.level]}`),
        ],
      };
    case 'gaps':
      return {
        title: `What to look at — ${spec.topic}`,
        body: 'A plain-language read of where the learning still needs a little work, evidence-led.',
        items: spec.gaps.map(
          (g) => `${g.label}${g.confirmed ? '' : ' (worth watching)'} — ${g.rationale}`,
        ),
        confidence: spec.gaps[0]?.confidence,
      };
    case 'draft':
      return {
        title: spec.title,
        body: spec.body,
        items: spec.items,
        confidence: spec.confidence,
        openHref: spec.openHref,
        openLabel: spec.openLabel,
      };
    case 'recommendation':
      return {
        title: spec.title,
        body: spec.why,
        items: [
          ...spec.evidence,
          `If ignored: ${spec.consequence}`,
          `Owner: ${spec.owner} · Due: ${spec.due}`,
        ],
        confidence: spec.confidence,
      };
    case 'explain':
      return {
        title: `A nudge — ${spec.concept}`,
        body: spec.body,
      };
    case 'steps':
      return {
        title: spec.title,
        body: spec.topic
          ? `Step by step, ${spec.topic}. Each step is checked before it is shown.`
          : 'Step by step. Each step is checked before it is shown.',
        items: spec.steps.map((s) => s.text),
        confidence: 'high',
      };
    case 'surface':
      return surfaceToInline(spec.surface);
    default:
      return null;
  }
}

/**
 * Map a composed surface to the calm inline card the thread renders. This is
 * the conservative text projection (the live operable surface is rendered by
 * the dedicated client component); the card always shows the consequential
 * affordance behind the approval control so the permission ladder reads true.
 */
export function surfaceToInline(surface: SurfaceSpec): InlineCard {
  switch (surface.kind) {
    case 'quiz-builder':
      return {
        title: surface.title,
        body: `A working quick check on ${surface.topic}. Edit it here; setting it live needs your approval.`,
        items: surface.items.map((it, i) => `${i + 1}. ${it.prompt}`),
        confidence: 'middle',
        openHref: surface.publish.openHref,
        openLabel: surface.publish.label,
      };
    case 'class-view':
      return {
        title: surface.title,
        body: surface.summary ?? `Where ${surface.section} stands, in plain language.`,
        items: surface.rows.map(
          (r) => `${r.label} — ${r.band}${r.needsAttention ? ' (worth a look)' : ''}`,
        ),
      };
    case 'plan-board':
      return {
        title: surface.title,
        body: `A draft plan for ${surface.topic}. Adopting it needs your approval.`,
        items: surface.columns.map((c) => `${c.heading}: ${c.cards.join(' · ')}`),
        confidence: 'middle',
        openHref: surface.adopt.openHref,
        openLabel: surface.adopt.label,
      };
    case 'report-card':
      return {
        title: surface.title,
        body: `How ${surface.childLabel} is doing, in plain language.`,
        items: [...surface.highlights, ...(surface.nextStep ? [`Next: ${surface.nextStep}`] : [])],
      };
  }
}

// ---------------------------------------------------------------------------
// The TUTOR pure helper — the assistance ladder, as a deterministic state
// machine, so the rule "never reveal before a posed attempt" is testable and
// holds on BOTH the typed and the voice path. Vidya poses a step, waits for the
// learner's attempt, scaffolds on a wrong answer (misconception detonation),
// and only reveals once an attempt has been made (or the learner is clearly
// stuck after enough scaffolding).
// ---------------------------------------------------------------------------

export type TutorPhase = 'pose' | 'scaffold' | 'reveal';

export interface TutorState {
  /** How many attempts the learner has made on the current step. */
  attempts: number;
  /** Whether the latest attempt was correct. */
  lastCorrect: boolean;
  /** Whether the learner explicitly asked to be shown / gave up. */
  gaveUp: boolean;
}

export const TUTOR_START: TutorState = { attempts: 0, lastCorrect: false, gaveUp: false };

/** The maximum scaffolds before a reveal is allowed even without a correct attempt. */
export const TUTOR_MAX_SCAFFOLDS = 2;

/**
 * Decide the next tutoring phase from the state. INVARIANT (generate-and-verify
 * of pedagogy): a reveal is NEVER returned before the learner has made at least
 * one posed attempt — unless they explicitly gave up. With no attempt yet we
 * pose; after a wrong attempt we scaffold (detonate the misconception); once the
 * learner is correct, has tried enough times, or gave up, we may reveal.
 */
export function tutorReveal(state: TutorState): TutorPhase {
  if (state.attempts === 0 && !state.gaveUp) return 'pose';
  if (state.lastCorrect || state.gaveUp || state.attempts > TUTOR_MAX_SCAFFOLDS) return 'reveal';
  return 'scaffold';
}

/**
 * One Vidya text turn. Posts the conversation + role to the orchestrator and
 * returns the final text + client actions. NEVER throws on a provider/transport
 * failure — it resolves to { degraded: true } so the caller can fall back to the
 * offline responder.
 */
export async function vidyaChat(
  req: VidyaChatRequest,
  route: string = VIDYA_CHAT_ROUTE,
  fetchImpl: typeof fetch = fetch,
): Promise<VidyaChatResult> {
  try {
    // The wall authorizes the turn by the opaque caller headers (lib/opGate):
    // the locally-held account uuid + the request's role. Never PII, never a key.
    const headers: Record<string, string> = { 'content-type': 'application/json' };
    try {
      const account = readStore().account;
      if (account?.id) {
        headers['x-caller-uuid'] = account.id;
        headers['x-caller-role'] = req.role;
        headers['x-caller-app'] = 'school';
      }
    } catch {
      /* no account yet — the route degrades to the local responder */
    }
    const res = await fetchImpl(route, {
      method: 'POST',
      headers,
      body: JSON.stringify(req),
    });
    const data = (await res.json().catch(() => ({}))) as Partial<VidyaChatResult>;
    if (!res.ok || data.degraded) {
      return { text: '', actions: [], degraded: true, reason: data.reason ?? `http-${res.status}` };
    }
    return {
      text: typeof data.text === 'string' ? data.text : '',
      actions: parseActions(data.actions),
    };
  } catch {
    return { text: '', actions: [], degraded: true, reason: 'network' };
  }
}
