'use client';

import { SurfaceError } from '../_components/SurfaceError';

export default function StudentError({ reset }: { error: Error; reset: () => void }) {
  return <SurfaceError reset={reset} />;
}
