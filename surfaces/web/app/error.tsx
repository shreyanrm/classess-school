'use client';

import Link from 'next/link';
import { Button, Icon } from '@classess/design-system';
import { Rail } from './_components/Rail';

/**
 * The home error state — designed, calm, with one clear next action. No raw
 * stack, no alarm. Errors are first-class states, not failure screens.
 *
 * The live Rail still renders (as every segment error does), so even if reset()
 * keeps re-throwing on a persistent home error the user is never stranded: the
 * rail reaches every other page, and a "Back to home" link returns here. The
 * copy's promise — "the rail still reaches your pages" — is now literally true.
 */
export default function HomeError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="app-frame">
      <Rail />
      <main className="app-main">
        <div className="home-canvas">
          <div className="empty">
            <Icon name="info" size="lg" className="glyph" />
            <h4 className="body-lg">Something interrupted the conversation</h4>
            <p>
              The home could not load just now. Your work is safe. Try again, and if it keeps
              happening, the rail still reaches your pages.
            </p>
            <div className="row" style={{ gap: 'var(--space-3)', justifyContent: 'center' }}>
              <Button variant="primary" size="sm" onClick={reset}>
                Try again
              </Button>
              <Link href="/" className="btn btn-ghost btn-sm row" style={{ gap: 'var(--space-2)' }}>
                <Icon name="home" size="sm" />
                Back to home
              </Link>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
