'use client';

import { Button, Icon } from '@classess/design-system';
import { openVidya } from './VidyaOrb';
import type { ReadPhase } from '@/lib/useDeepReads';

/**
 * The four non-ready states for a governed deep read, rendered INSIDE the
 * surface body (the shell, rail and Vidya stay put). Every student loop surface
 * composes this so all five designed states ship from one place:
 *
 *   loading            — a calm skeleton, no spinner
 *   error              — the route failed; one clear retry, work is safe
 *   offline            — the browser is offline; showing the last synced read
 *   permission-denied  — the wall declined this read on RBAC/ABAC/consent
 *
 * The `ready` phase renders nothing here — the surface renders its own content
 * (empty is the surface's own "nothing yet" copy). v4.1 tokens only; no shadow.
 */
export function ReadStates({
  phase,
  onRetry,
}: {
  phase: ReadPhase;
  onRetry?: () => void;
}) {
  if (phase === 'loading') {
    return (
      <section className="stack" aria-busy="true" aria-label="Reading your progress">
        <div className="skeleton" style={{ height: 96 }} />
        <div className="skeleton" style={{ height: 180 }} />
      </section>
    );
  }

  if (phase === 'offline') {
    return (
      <div className="empty">
        <Icon name="info" size="lg" className="glyph" />
        <h4 className="body">You are offline</h4>
        <p>
          This is your last synced read. It will refresh on its own the moment you reconnect — your
          place is kept.
        </p>
      </div>
    );
  }

  if (phase === 'permission-denied') {
    return (
      <div className="empty">
        <Icon name="info" size="lg" className="glyph" />
        <h4 className="body">This reading is not shared with you right now</h4>
        <p>
          A reading like this opens only with the right consent in place. Nothing is wrong — ask if
          you would like it turned on for you.
        </p>
        <Button variant="secondary" size="sm" onClick={() => openVidya('Why can I not see this reading')}>
          <Icon name="spark" size="sm" /> Ask Vidya
        </Button>
      </div>
    );
  }

  // error
  return (
    <div className="empty">
      <Icon name="info" size="lg" className="glyph" />
      <h4 className="body">This view could not load just now</h4>
      <p>Your work is safe. Try again in a moment.</p>
      {onRetry ? (
        <Button variant="primary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
