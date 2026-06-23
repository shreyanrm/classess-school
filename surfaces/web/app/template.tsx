'use client';

/* ============================================================================
   app/template.tsx — calm route transitions.

   A template (unlike a layout) re-mounts on every navigation, so each route
   enters with a calm fade + a small rise. Quick and certain, never bouncy:
   var(--dur-slow) var(--ease). Under prefers-reduced-motion the animation
   collapses to an instant opacity swap (handled in globals.css via the
   .route-enter rule). The orb and rail live in the layout, so they persist —
   only the routed surface re-enters.
   ============================================================================ */

import { type ReactNode } from 'react';

export default function Template({ children }: { children: ReactNode }) {
  return <div className="route-enter">{children}</div>;
}
