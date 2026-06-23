import { describe, it, expect, afterEach, vi, beforeAll } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { VidyaCanvas } from '../VidyaCanvas';
import type { CanvasCardSpec } from '@/lib/vidya';

afterEach(cleanup);

// The canvas honours prefers-reduced-motion (reveals everything at once) so the
// derivation steps are all present synchronously in the test environment.
beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: query.includes('reduce'),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
});

const spec: CanvasCardSpec = {
  kind: 'canvas',
  title: 'Adding fractions',
  content: {
    type: 'derivation',
    steps: [
      { text: 'A half plus a quarter', check: { lhs: '1/2 + 1/4', rhs: '3/4' } },
      { text: 'Find a common denominator' },
    ],
  },
  sources: [
    { label: 'Your last three attempts on fractions', note: 'all unaided', href: '/student/progress' },
    { label: 'The worked example you opened earlier' },
  ],
};

describe('VidyaCanvas — editable derivation + sources', () => {
  it('lets the human annotate a derivation step without overwriting the verified text', () => {
    render(<VidyaCanvas spec={spec} onClose={() => {}} />);

    // Add a note to the first step.
    const annotateButtons = screen.getAllByTestId('vidya-canvas-annotate');
    fireEvent.click(annotateButtons[0]!);
    const input = screen.getByTestId('vidya-canvas-note-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'This is the step I keep missing' } });
    fireEvent.blur(input);

    // The note now shows as a human-style annotation; the verified text remains.
    expect(screen.getByTestId('vidya-canvas-note')).toHaveTextContent('This is the step I keep missing');
    expect(screen.getByText('A half plus a quarter')).toBeInTheDocument();
  });

  it('shows the sources / evidence alongside the answer, with a real route to open', () => {
    const onOpenHref = vi.fn();
    render(<VidyaCanvas spec={spec} onClose={() => {}} onOpenHref={onOpenHref} />);

    expect(screen.getByTestId('vidya-canvas-sources')).toBeInTheDocument();
    const sources = screen.getAllByTestId('vidya-canvas-source');
    expect(sources).toHaveLength(2);
    expect(sources[0]).toHaveTextContent('Your last three attempts on fractions');

    // Only the source with a real route exposes an open control.
    fireEvent.click(screen.getByRole('button', { name: /open/i }));
    expect(onOpenHref).toHaveBeenCalledWith('/student/progress');
  });
});
