/** Insights loading state — calm skeleton of the matrix and rows. */
export default function InsightsLoading() {
  return (
    <div className="app-frame">
      <div className="rail" aria-hidden="true" />
      <div className="surface">
        <div className="surface-topbar">
          <div className="skeleton skeleton-line" style={{ width: 220, height: 28 }} />
        </div>
        <div className="surface-split">
          <div className="surface-body">
            <div className="surface-body-inner" aria-busy="true" aria-label="Loading insights">
              <div className="skeleton" style={{ height: 120 }} />
              <div className="skeleton" style={{ height: 220 }} />
              <div className="skeleton" style={{ height: 180 }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
