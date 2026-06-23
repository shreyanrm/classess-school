import Link from 'next/link';
import { Icon } from '@classess/design-system';

/** A calm not-found state — never a dead end; the conversation is one step away. */
export default function NotFound() {
  return (
    <div className="app-frame">
      <main className="app-main">
        <div className="home-canvas">
          <div className="empty">
            <Icon name="search" size="lg" className="glyph" />
            <h4 className="body-lg">That page is not here</h4>
            <p>The link may have moved. The conversation is the front door over every page.</p>
            <Link href="/" className="btn btn-primary btn-sm">
              Back to the conversation
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
