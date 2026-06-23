'use client';

import { SurfaceError } from '../_components/SurfaceError';

/** Admin segment error state — first-class, calm, one next action. */
export default function AdminError({ reset }: { error: Error; reset: () => void }) {
  return (
    <SurfaceError
      reset={reset}
      message="The briefing could not load just now. Your school's data is safe. Try again, and the rail still reaches your other admin pages."
    />
  );
}
