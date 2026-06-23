/**
 * Classess event + evidence contract — v1, immutable.
 *
 * This is the single source of truth for every attributed event in the
 * ecosystem. It is append-only: v1 schemas are frozen once shipped; evolution
 * happens by adding new versioned modules, never by editing these.
 */

export * from "./primitives.js";
export * from "./gaps.js";
export * from "./mastery.js";
export * from "./attempt.js";
export * from "./payloads.js";
export * from "./envelope.js";
