import { describe, it, expect, afterEach } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { VidyaSpotlight } from '../VidyaSpotlight';

afterEach(cleanup);

/**
 * Item 5 — the Vidya highlight layer is SVG, not a CSS div box. This proves the
 * spotlight ring renders as a real <svg><rect> vector that can draw itself in.
 */
describe('VidyaSpotlight — the highlight ring is an SVG vector', () => {
  it('renders an svg ring around a registered region (not a div box)', async () => {
    // Mount a target the resolver can find by its data-vidya-region.
    render(
      <div>
        <div data-vidya-region="mastery-band" style={{ width: 200, height: 100 }}>
          Mastery
        </div>
        <VidyaSpotlight region="mastery-band" label="Look here" note="Trigonometry" dismissAfterMs={0} />
      </div>,
    );

    const layer = await screen.findByTestId('vidya-spotlight');
    expect(layer).toBeInTheDocument();

    await waitFor(() => {
      const svg = layer.querySelector('svg.vidya-spotlight-svg');
      expect(svg).toBeTruthy();
      // The ring is a vector <rect>, the SVG conversion (not a CSS box div).
      const ring = layer.querySelector('rect.vidya-spotlight-ring');
      expect(ring).toBeTruthy();
    });

    // The annotation (the calm margin note) still renders alongside the vector.
    expect(screen.getByTestId('vidya-annotation')).toHaveTextContent('Trigonometry');
  });
});
