import { SurfaceSkeleton } from '../_components/SurfaceSkeleton';

/** Parent segment loading state — calm skeleton, no spinner. */
export default function ParentLoading() {
  return <SurfaceSkeleton label="Loading a calm look at this week" />;
}
