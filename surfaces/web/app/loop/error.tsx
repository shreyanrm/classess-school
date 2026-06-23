'use client';

import { SurfaceError } from '../_components/SurfaceError';

export default function LoopError({ reset }: { error: Error; reset: () => void }) {
  return <SurfaceError reset={reset} message="The live loop could not start just now. Your work is safe — try again." />;
}
