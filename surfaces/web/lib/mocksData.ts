/* ============================================================================
   lib/mocksData.ts — the single source for the student mock-test blueprints.

   These are genuinely-static demo blueprints (the shape of a board paper), kept
   here in lib/ so every surface and Vidya read ONE coherent layer rather than a
   per-page inline const. The spaced-revision plan, by contrast, is NOT static —
   it is derived live from the engine (lib/loopData.studentRevisionPlan), so a
   topic surfaces only when the same engine says revision is genuinely due.

   Plain language only: a mock shows where the weight sits as coverage, never a
   marks formula and never a raw score.
   ============================================================================ */

/** A blueprint-aligned mock that mirrors the real paper. */
export interface MockBlueprint {
  id: string;
  subject: string;
  format: string;
  /** Section weights as plain coverage, not a marks formula. */
  coverage: { unit: string; weight: 'light' | 'core' | 'heavy' }[];
  state: 'ready' | 'taken';
}

export const MOCK_BLUEPRINTS: MockBlueprint[] = [
  {
    id: 'm1',
    subject: 'Mathematics',
    format: 'Three sections, mirrors the board paper',
    coverage: [
      { unit: 'Real Numbers', weight: 'light' },
      { unit: 'Polynomials', weight: 'core' },
      { unit: 'Trigonometry', weight: 'heavy' },
    ],
    state: 'ready',
  },
  {
    id: 'm2',
    subject: 'Physics',
    format: 'Two sections, same difficulty curve as the real exam',
    coverage: [
      { unit: 'Light', weight: 'heavy' },
      { unit: 'Electricity', weight: 'core' },
    ],
    state: 'taken',
  },
];
