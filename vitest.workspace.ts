import { defineWorkspace } from 'vitest/config';
import react from '@vitejs/plugin-react';

const setup = new URL('./vitest.setup.ts', import.meta.url).pathname;

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
    test: {
      name: 'web',
      root: './surfaces/web',
      environment: 'jsdom',
      include: ['lib/**/*.test.ts', 'app/**/*.test.{ts,tsx}'],
      setupFiles: [setup],
    },
  },
]);
