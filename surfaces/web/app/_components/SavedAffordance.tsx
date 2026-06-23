'use client';

import { Icon } from '@classess/design-system';
import type { SaveState } from '@/lib/useEmit';

/**
 * A quiet, calm affordance shown after a real action emits through the live
 * event seam. It never shouts: a saved write reads "Saved to your record"; the
 * no-database path reads "Kept on this device" (the designed local fallback);
 * a failed/transport path stays on the local line too. Plain language, no
 * emoji, no exclamation.
 *
 * Uses the per-surface accent only for the saved tick (a small affirmation),
 * never the brand signature.
 */
export function SavedAffordance({ state, note }: { state: SaveState; note: string | null }) {
  if (state === 'idle' || !note) return null;
  const persisted = state === 'saved';
  return (
    <span
      className="row caption"
      role="status"
      aria-live="polite"
      style={{
        gap: 'var(--space-2)',
        color: persisted ? 'var(--accent)' : 'var(--text-muted)',
      }}
    >
      {state === 'saving' ? (
        <Icon name="clock" size="sm" aria-hidden="true" />
      ) : (
        <Icon name={persisted ? 'check' : 'info'} size="sm" aria-hidden="true" />
      )}
      {note}
    </span>
  );
}
