'use client';

import { Button, Icon } from '@classess/design-system';

/**
 * The home error state — designed, calm, with one clear next action. No raw
 * stack, no alarm. Errors are first-class states, not failure screens.
 */
export default function HomeError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="app-frame">
      <main className="app-main">
        <div className="home-canvas">
          <div className="empty">
            <Icon name="info" size="lg" className="glyph" />
            <h4 className="body-lg">Something interrupted the conversation</h4>
            <p>
              The home could not load just now. Your work is safe. Try again, and if it keeps
              happening, the rail still reaches your pages.
            </p>
            <Button variant="primary" size="sm" onClick={reset}>
              Try again
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
