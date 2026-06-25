/**
 * @classess/contracts — the single source of truth for Classess School Ring 0.
 *
 * Everything binds to this package: the immutable event/evidence contract, the
 * per-capability OpenAPI specs, the canonical DB schema description, and the v4
 * design tokens. Import the whole surface here, or the subpath exports
 * (`@classess/contracts/events`, `/openapi`, `/tokens`).
 */

export * from "./events/index.js";
export * from "./openapi/index.js";
export * from "./db/index.js";
export * as tokens from "./tokens/index.js";

// Slice 1 — the Student <-> Teacher loop surfaces.
export * from "./ontology/index.js";
export * from "./evaluation/index.js";
export * from "./recommendations/index.js";
export * from "./ai/index.js";

// The named capability registry (spec 11 + 13) — thin typed index over the
// existing surface; binds capability -> ladder level + emitted events + consent.
export * from "./capabilities/index.js";

// The unified evidence record (INVARIANT 2). Exported as a namespace because the
// recommendations layer already exposes an `EvidenceRef`; reach the unified
// record + the independent-vs-supported flag via `evidence.*`.
export * as evidence from "./evidence/index.js";

// The assistance ladder re-exports the rung enum + docs from ./events (the
// single source of truth for the rungs), so it is exported as a namespace to
// avoid duplicating those symbols on the flat surface. Its ladder array and
// helpers are reached via `assistance.*`.
export * as assistance from "./assistance/index.js";
