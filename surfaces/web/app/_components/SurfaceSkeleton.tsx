/**
 * A calm, shared loading skeleton for destination pages — the rail, a top bar,
 * and a few body blocks. No spinner. Used by the teacher/student/loop segment
 * loading states so they never flash empty.
 */
export function SurfaceSkeleton({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="app-frame">
      <div className="rail" aria-hidden="true" />
      <div className="surface">
        <div className="surface-topbar">
          <div className="skeleton skeleton-line" style={{ width: 220, height: 28 }} />
        </div>
        <div className="surface-split">
          <div className="surface-body">
            <div className="surface-body-inner" aria-busy="true" aria-label={label}>
              <div className="skeleton" style={{ height: 120 }} />
              <div className="skeleton" style={{ height: 200 }} />
              <div className="skeleton" style={{ height: 160 }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
