/**
 * The home loading state — calm, centred, no spinner. A skeleton of the
 * greeting and composer so the canvas never flashes empty.
 */
export default function HomeLoading() {
  return (
    <div className="app-frame">
      <div className="rail" aria-hidden="true" />
      <main className="app-main">
        <div className="home-canvas">
          <div className="home-center" aria-busy="true" aria-label="Loading">
            <div className="home-greeting">
              <div
                className="skeleton skeleton-line"
                style={{ width: 240, height: 28, margin: '0 auto' }}
              />
            </div>
            <div className="skeleton" style={{ height: 56 }} />
            <div className="home-chips">
              <div className="skeleton" style={{ height: 32, width: 140 }} />
              <div className="skeleton" style={{ height: 32, width: 180 }} />
              <div className="skeleton" style={{ height: 32, width: 120 }} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
