/** Live loop loading — calm skeleton of the stepper and the two columns. */
export default function LoopLoading() {
  return (
    <div className="app-frame">
      <div className="rail" aria-hidden="true" />
      <div className="surface">
        <div className="surface-topbar">
          <div className="skeleton skeleton-line" style={{ width: 200, height: 28 }} />
        </div>
        <div className="surface-split">
          <div className="surface-body">
            <div className="surface-body-inner" aria-busy="true" aria-label="Loading the live loop">
              <div className="skeleton" style={{ height: 48 }} />
              <div className="cols-2">
                <div className="skeleton" style={{ height: 320 }} />
                <div className="skeleton" style={{ height: 320 }} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
