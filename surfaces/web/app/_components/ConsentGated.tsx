import { Icon } from '@classess/design-system';

/**
 * The consent-gated state — plain, calm, never an error. A parent sees only what
 * consent permits; this is what stands in until the school turns on sharing.
 *
 * Lives in _components (not a route file) so it can be shared across the parent
 * pages — Next App Router only permits a default export from a page file.
 */
export function ConsentGated({ label }: { label?: string }) {
  return (
    <section className="stack">
      <div className="empty">
        <Icon name="info" size="lg" className="glyph" />
        <h4 className="body">{label ? `${label}'s view is not shared yet` : 'This view is not shared yet'}</h4>
        <p>
          A parent sees only what consent permits. When {label ?? 'this child'}&apos;s school turns
          on sharing, their progress will appear here. You can ask the school to enable it whenever
          you are ready.
        </p>
      </div>
    </section>
  );
}
