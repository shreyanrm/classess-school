/* ============================================================================
   Shared types for the Classess design system.
   ============================================================================ */

/** The active colour theme. Mapped 1:1 to data-theme on <html>. */
export type Theme = 'light' | 'dark';

/**
 * The vivid accent family. Monochrome shell; ONE vivid per surface; colour
 * carries meaning, never decoration. The ultramarine signature is reserved for
 * the brand mark and the mastery ignite — it is intentionally NOT a subject
 * accent, so it is excluded from SubjectAccent below.
 */
export type Accent =
  | 'molten'
  | 'hot-red'
  | 'magenta'
  | 'violet'
  | 'ultramarine'
  | 'tiffany'
  | 'acid'
  | 'amber'
  | 'cobalt'
  | 'cyan'
  | 'emerald'
  | 'tangerine'
  | 'rose'
  | 'grape'
  | 'indigo';

/**
 * Accents usable as a subject identity colour. Ultramarine is deliberately
 * absent: it is the signature, reserved for brand + ignite, never a subject.
 */
export type SubjectAccent = Exclude<Accent, 'ultramarine'>;

/** Functional / semantic state — validation, status. Never decoration. */
export type Status = 'success' | 'danger' | 'warning' | 'info';

/** Plain-language mastery / verification confidence. Never a raw score. */
export type Confidence = 'high' | 'middle' | 'low';

/** Standard control sizing used by Button, Avatar, etc. */
export type Size = 'sm' | 'md' | 'lg';
