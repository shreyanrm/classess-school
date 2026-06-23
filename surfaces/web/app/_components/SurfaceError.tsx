'use client';

import Link from 'next/link';
import { Button, Icon } from '@classess/design-system';
import { Rail } from './Rail';

/**
 * A calm, shared error state for destination pages. Errors are first-class
 * states, not failure screens: one clear next action, no raw stack, no alarm.
 * The real, live rail still renders so every other page stays one click away,
 * and a "Back to the conversation" link returns the user to the home.
 */
export function SurfaceError({ reset, message }: { reset: () => void; message?: string }) {
  return (
    <div className="app-frame">
      <Rail />
      <div className="surface">
        <div className="surface-split">
          <div className="surface-body">
            <div className="empty">
              <Icon name="info" size="lg" className="glyph" />
              <h4 className="body-lg">This view could not load just now</h4>
              <p>
                {message ??
                  'Your work is safe. Try again, and if it keeps happening the rail still reaches your other pages.'}
              </p>
              <div className="row" style={{ gap: 'var(--space-3)', justifyContent: 'center' }}>
                <Button variant="primary" size="sm" onClick={reset}>
                  Try again
                </Button>
                <Link href="/" className="btn btn-ghost btn-sm row" style={{ gap: 'var(--space-2)' }}>
                  <Icon name="home" size="sm" />
                  Back to the conversation
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
