/* ============================================================================
   lib/parentReads.ts — the governed PARENT VIEW read seam (gateway-first,
   mock fallback). SERVER-ONLY.

   The Parent surface reads a child's GOVERNED, CONSENT-SCOPED view: the calm
   weekly briefing, the timeline, strengths/support, the reports, the
   learn-alongside + PTM prep, and the proof artifact. Those views are owned by
   the ONE source of truth — the Python intelligence spine — and are reached
   THROUGH the live gateway (the wall). The typed mock bundle in lib/parentData
   (selectChildData) is the DEGRADE FALLBACK ONLY: it answers when, and only
   when, the wall is unreachable / times out / denies / returns a non-contract
   body. The user-visible result is identical either way.

   Consent is the heart of this surface — a parent sees only what consent
   permits. An unconsented child returns NO data (the surface renders the
   consent-gated / permission state), exactly as selectChildData enforces; and
   the gateway read asserts the consent purpose so the wall's consent gate runs.

   The web PREPARES and READS; it never bypasses the wall. Confidentiality:
   every id is an opaque canonical ref. No PII, no secret, no raw score.
   ============================================================================ */

import { callerIdentity, type DeepRead } from './deepReads';
import { readCapability, type CallerIdentity, type GatewayResult } from './gateway';
import { findChild, selectChildData, type ParentChildData } from './parentData';

/** Re-export so the API route can build the opaque caller identity. */
export { callerIdentity };

/** The plain-language view names a parent's governed read can carry. */
const PARENT_VIEW = 'parent-child' as const;

/**
 * The shape guard: a gateway body is trusted only when it looks like the
 * ParentChildData contract (the rich, plain-language bundle the surface
 * renders). Anything else (e.g. a generic `{ status: "admitted" }` ack) falls
 * back to the mock bundle so the surface never renders a half-shape.
 */
function isParentChildData(v: unknown): v is ParentChildData {
  if (typeof v !== 'object' || v === null) return false;
  const d = v as Partial<ParentChildData>;
  return (
    Array.isArray(d.briefings) &&
    Array.isArray(d.timeline) &&
    Array.isArray(d.strengths) &&
    Array.isArray(d.supportAreas) &&
    Array.isArray(d.reports) &&
    Array.isArray(d.learnAlongside) &&
    Array.isArray(d.proof) &&
    typeof d.ptm === 'object' &&
    d.ptm !== null
  );
}

/** The result of a governed parent read. `data` is null when consent is absent. */
export interface ParentReadResult {
  data: ParentChildData | null;
  source: DeepRead<unknown>['source'];
  /** True when the wall actively denied (RBAC/ABAC/consent) — the permission state. */
  denied: boolean;
  /** True when the child's view has not been consented (the consent-gated state). */
  consentGated: boolean;
  /** Why the gateway declined, when it was tried (logs only). */
  fallbackReason?: string;
}

/**
 * Read one child's governed parent view, gateway-first. Consent is honoured at
 * the seam: an unknown or unconsented child returns `{ data: null, consentGated:
 * true }` and the gateway is never asked (nothing to read). For a consented
 * child the gateway's `intelligence-views.read` (the parent-child view) is
 * tried; on any degrade the mock bundle answers, identical in shape.
 */
export async function readParentChild(
  childId: string,
  identity: CallerIdentity,
  opts: { fetchImpl?: typeof fetch } = {},
): Promise<ParentReadResult> {
  const child = findChild(childId);

  // Consent first — a parent sees only what consent permits. No read is made
  // for a child whose view has not been consented; the surface gates it.
  if (!child || !child.consentGranted) {
    return { data: null, source: 'fallback', denied: false, consentGated: true };
  }

  const result: GatewayResult<ParentChildData> = await readCapability<ParentChildData>(
    'intelligence-views',
    childId,
    {
      identity,
      view: `${PARENT_VIEW}:${childId}`,
      // A parent reading their child's view is a cross-context, consent-scoped
      // intelligence read -> assert the purpose so the wall's consent gate runs.
      consentPurpose: 'intelligence.parent-child',
      fetchImpl: opts.fetchImpl,
    },
  );

  if (result.ok && isParentChildData(result.data)) {
    return { data: result.data, source: 'gateway', denied: false, consentGated: false };
  }

  // A wall deny on RBAC/ABAC/consent is the permission state, not a silent
  // degrade. Any other decline (unreachable/timeout/non-contract) falls back to
  // the consented child's mock bundle so the live surface never breaks.
  const denied = !result.ok && result.reason === 'unauthorized';
  return {
    data: selectChildData(childId),
    source: 'fallback',
    denied,
    consentGated: false,
    fallbackReason: !result.ok ? result.reason : undefined,
  };
}
