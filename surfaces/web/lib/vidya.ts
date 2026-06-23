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

export type RenderSpec =
  | MasteryCardSpec
  | GapsCardSpec
  | DraftCardSpec
  | RecommendationCardSpec
  | ExplainCardSpec;

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

export type VidyaAction = NavigateAction | RenderAction;

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

const RENDER_KINDS = new Set(['mastery', 'gaps', 'draft', 'recommendation', 'explain']);

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
        out.push({ type: 'render', spec: spec as unknown as RenderSpec });
      }
    }
  }
  return out;
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
    default:
      return null;
  }
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
