import '@testing-library/jest-dom/vitest';

// jsdom has no matchMedia; the design system's useReducedMotion depends on it.
if (typeof window !== 'undefined' && !window.matchMedia) {
  // @ts-expect-error - minimal polyfill for tests
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  });
}
