import { defineWorkspace } from 'vitest/config';
import react from '@vitejs/plugin-react';

const setup = new URL('./vitest.setup.ts', import.meta.url).pathname;
// The web surface imports modules through the `@/*` path alias (tsconfig). The
// test runner needs the same alias to resolve component imports under test.
const webAlias = { '@': new URL('./surfaces/web', import.meta.url).pathname };

export default defineWorkspace([
  // Contracts — pure Zod/TS, node environment.
  {
    test: {
      name: 'contracts',
      root: './contracts',
      environment: 'node',
      include: ['src/**/*.test.ts'],
    },
  },
  // Design system — React components, jsdom + testing-library.
  {
    plugins: [react()],
    test: {
      name: 'design-system',
      root: './packages/design-system',
      environment: 'jsdom',
      include: ['src/**/*.test.{ts,tsx}'],
      setupFiles: [setup],
    },
  },
  // Web — the in-browser engine port + components.
  {
    plugins: [react()],
    resolve: { alias: webAlias },
    // The web tsconfig sets jsx: "preserve" (Next compiles it); for the test
    // runner, compile JSX with the automatic runtime so component test files do
    // not need an explicit React import.
    esbuild: { jsx: 'automatic' },
    test: {
      name: 'web',
      root: './surfaces/web',
      environment: 'jsdom',
      include: ['lib/**/*.test.ts', 'app/**/*.test.{ts,tsx}'],
      setupFiles: [setup],
    },
  },
]);
