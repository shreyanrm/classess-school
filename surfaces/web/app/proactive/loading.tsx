/** Proactive feed loading state — calm skeleton of the briefing and feed. */
export default function ProactiveLoading() {
  return (
    <div className="app-frame">
      <div className="rail" aria-hidden="true" />
      <div className="surface">
        <div className="surface-topbar">
          <div className="skeleton skeleton-line" style={{ width: 200, height: 28 }} />
        </div>
        <div className="surface-split">
          <div className="surface-body">
            <div className="surface-body-inner" aria-busy="true" aria-label="Loading proactive feed">
              <div className="skeleton" style={{ height: 140 }} />
              <div className="skeleton" style={{ height: 200 }} />
              <div className="skeleton" style={{ height: 200 }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
