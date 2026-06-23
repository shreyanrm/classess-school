/**
 * Machine-readable design tokens, typed for programmatic consumers (React
 * Native, tooling, codegen). The JSON is the single source of truth — never
 * hardcode hex in app code; read these.
 *
 * Imported via resolveJsonModule (`with { type: "json" }` import attribute) so
 * the literal token tree is available at type level and at runtime.
 */

import tokensJson from "./tokens.json" with { type: "json" };

/** The full token tree, typed as a literal-preserving const. */
export const tokens = tokensJson as typeof tokensJson;
export type Tokens = typeof tokens;

/** Convenience accessors over the typed tree. */
export const color = tokens.color;
export const typography = tokens.typography;
export const space = tokens.space;
export const radius = tokens.radius;
export const motion = tokens.motion;
export const layout = tokens.layout;
export const subjectMap = tokens.subjectMap;

export type ColorTokens = typeof color;
export type TypographyTokens = typeof typography;

export default tokens;
