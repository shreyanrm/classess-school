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

export type RenderSpec =
  | MasteryCardSpec
  | GapsCardSpec
  | DraftCardSpec
  | RecommendationCardSpec
  | ExplainCardSpec
  | StepsCardSpec;

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

export interface VidyaChatRequest {
  messages: VidyaTurn[];
  role: Role;
}

// ---------------------------------------------------------------------------
// Action parsing — the route returns JSON, but a defensive parser keeps the
// client crash-proof against a malformed action (drops unknown targets/specs).
// ---------------------------------------------------------------------------

const RENDER_KINDS = new Set(['mastery', 'gaps', 'draft', 'recommendation', 'explain', 'steps']);

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

/** Sanitise a full canvas spec at the trust boundary. */
export function sanitiseCanvas(spec: Record<string, unknown>): CanvasCardSpec {
  const content = sanitiseCanvasContent(spec.content) ?? { type: 'written', lines: [] };
  return {
    kind: 'canvas',
    title: typeof spec.title === 'string' && spec.title.trim() ? spec.title.trim() : 'On the canvas',
    content,
    openHref: isNavTarget(spec.openHref) ? spec.openHref : undefined,
    openLabel: trimStr(spec.openLabel),
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
    default:
      return null;
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
    const res = await fetchImpl(route, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
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
