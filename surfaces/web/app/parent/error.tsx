'use client';

import { SurfaceError } from '../_components/SurfaceError';

/** Parent segment error state — first-class, calm, reassuring, one next action. */
export default function ParentError({ reset }: { error: Error; reset: () => void }) {
  return (
    <SurfaceError
      reset={reset}
      message="This view could not load just now. Your child's information is safe and private. Try again, and the rail still reaches your other pages."
    />
  );
}
