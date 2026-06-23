import { SurfaceSkeleton } from '../_components/SurfaceSkeleton';

/** Admin segment loading state — calm skeleton, no spinner. */
export default function AdminLoading() {
  return <SurfaceSkeleton label="Loading the briefing" />;
}
