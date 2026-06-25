'use client';

/* ============================================================================
   app/_components/VidyaWatch.tsx — the QUIET ambient offer (Pillar 1 surface).

   VidyaWatch watches the in-app state (useVidyaWatch) and, when it detects a
   STUCK / REPEATING / IDLE pattern on a HARD step, surfaces ONE calm, dismissible
   offer just above the orb: a subtle pill that says "want a hand?" — never a nag,
   never a modal, never a blocker. Accepting hands off to the SAME Vidya orb
   (openVidya), which then guides / teaches-by-drawing / explains on screen via
   the existing spotlight + steps + canvas path. Dismissing mutes that signal for
   a cool-off.

   PREMIUM, CALM-FIRST motion: a hairline-framed frosted pill that rises in on
   transform/opacity with var(--ease); a subtle living dot (the same gradient
   family as the orb) marks it as Vidya without shouting. No shadow. Reduced-
   motion shows it placed, no rise, no living dot animation.

   It mounts INSIDE the orb root (VidyaOrb) so there is exactly one ambient layer
   and one Vidya identity — it is not a second presence, it is the orb's quiet
   proactive offer.
   ============================================================================ */

import { Icon } from '@classess/design-system';
import { useVidyaWatch } from '@/lib/useVidyaWatch';

export function VidyaWatch() {
  const { offer, accept, dismiss } = useVidyaWatch();

  if (!offer) return null;

  return (
    <div
      className="vidya-watch"
      role="status"
      aria-live="polite"
      data-testid="vidya-watch"
      data-signal={offer.signal}
    >
      <span className="vidya-watch-dot" aria-hidden="true" />
      <p className="vidya-watch-caption body-sm">{offer.caption}</p>
      <div className="vidya-watch-actions">
        <button
          type="button"
          className="vidya-watch-accept body-sm"
          data-testid="vidya-watch-accept"
          onClick={accept}
        >
          {offer.accept}
        </button>
        <button
          type="button"
          className="vidya-watch-dismiss"
          aria-label="Not now"
          title="Not now"
          data-testid="vidya-watch-dismiss"
          onClick={dismiss}
        >
          <Icon name="close" size="sm" />
        </button>
      </div>
    </div>
  );
}
