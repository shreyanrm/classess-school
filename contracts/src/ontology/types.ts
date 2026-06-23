/**
 * The academic ontology contract — board-agnostic.
 *
 * The spine models curriculum as a graph, never hard-coded to one board:
 *
 *   Board → Grade → Subject → Unit → Chapter → Topic → Outcome → Competency
 *
 * plus a prerequisite Edge (topic → topic) that is an OWNED, expert-validated
 * artifact (A2: proposed by the steward, confirmed before trusted), and a
 * cross-board equivalence reference so the same conceptual node can be mapped
 * across boards without lock-in.
 *
 * Events point at ontology nodes by opaque id (see events/primitives OntologyRef);
 * this module is the shape of the nodes themselves. INVARIANT-adjacent: the board
 * is a FIELD on the tree, never a baked-in assumption.
 */

import { z } from "zod";

/** A UUID for ontology nodes — mirrors the events Uuid primitive. */
export const OntologyId = z.string().uuid();
export type OntologyId = z.infer<typeof OntologyId>;

/**
 * The kinds of node in the ontology graph, finest-to-coarsest aware. Used to tag
 * a node and to validate that edges connect the levels they are allowed to.
 */
export const OntologyNodeKind = z.enum([
  "board",
  "grade",
  "subject",
  "unit",
  "chapter",
  "topic",
  "outcome",
  "competency",
]);
export type OntologyNodeKind = z.infer<typeof OntologyNodeKind>;

/**
 * The board. Board-agnostic by construction: this is a labelled node, not an
 * enum of permitted boards. The seed uses a neutral example label
 * ("Example State Board") precisely to avoid privileging any real board.
 */
export const Board = z.object({
  id: OntologyId,
  kind: z.literal("board"),
  code: z.string().describe("Short stable handle for the board, e.g. 'example-state-board'. Never a real board lock-in."),
  name: z.string().describe("Display name of the board. A field — never hard-coded as the only option."),
  region: z.string().optional().describe("Optional jurisdiction/region the board governs."),
});
export type Board = z.infer<typeof Board>;

/** A grade/standard within a board. */
export const Grade = z.object({
  id: OntologyId,
  kind: z.literal("grade"),
  board_id: OntologyId,
  level: z.number().int().describe("Numeric standard, e.g. 10."),
  name: z.string().describe("Display name, e.g. 'Class 10'."),
});
export type Grade = z.infer<typeof Grade>;

/** A subject within a grade. */
export const Subject = z.object({
  id: OntologyId,
  kind: z.literal("subject"),
  grade_id: OntologyId,
  name: z.string().describe("e.g. 'Mathematics', 'Physics'."),
});
export type Subject = z.infer<typeof Subject>;

/** A unit within a subject. */
export const Unit = z.object({
  id: OntologyId,
  kind: z.literal("unit"),
  subject_id: OntologyId,
  name: z.string(),
  sequence: z.number().int().nonnegative().describe("Ordering within the subject."),
});
export type Unit = z.infer<typeof Unit>;

/** A chapter within a unit. */
export const Chapter = z.object({
  id: OntologyId,
  kind: z.literal("chapter"),
  unit_id: OntologyId,
  name: z.string(),
  sequence: z.number().int().nonnegative().describe("Ordering within the unit."),
});
export type Chapter = z.infer<typeof Chapter>;

/**
 * A topic — the grain attempts and mastery readings are usually keyed to. A
 * topic owns outcomes and participates in prerequisite edges.
 */
export const Topic = z.object({
  id: OntologyId,
  kind: z.literal("topic"),
  chapter_id: OntologyId,
  name: z.string(),
  sequence: z.number().int().nonnegative().describe("Ordering within the chapter."),
});
export type Topic = z.infer<typeof Topic>;

/**
 * A learning outcome — a verifiable can-do statement under a topic. Outcome
 * statements are written as observable learner behaviours, not topic titles.
 */
export const Outcome = z.object({
  id: OntologyId,
  kind: z.literal("outcome"),
  topic_id: OntologyId,
  statement: z.string().describe("Observable can-do statement, e.g. 'States and applies Euclid's division lemma to find an HCF.'"),
});
export type Outcome = z.infer<typeof Outcome>;

/**
 * A competency — a broader capability that several outcomes roll up into. Crosses
 * topics within a subject.
 */
export const Competency = z.object({
  id: OntologyId,
  kind: z.literal("competency"),
  subject_id: OntologyId,
  name: z.string(),
  statement: z.string().describe("What the learner can durably do across topics, e.g. 'Reasons about number properties and divisibility.'"),
  outcome_ids: z.array(OntologyId).describe("Outcomes that contribute evidence to this competency."),
});
export type Competency = z.infer<typeof Competency>;

/**
 * The reason a prerequisite edge exists — drives the gap response (a missing
 * prerequisite routes back to the prior node rather than re-teaching the current
 * one).
 */
export const PrerequisiteKind = z.enum([
  "hard", // the later topic cannot be attempted without the earlier one
  "soft", // the later topic is easier with the earlier one but not blocked
]);
export type PrerequisiteKind = z.infer<typeof PrerequisiteKind>;

/**
 * A prerequisite edge, topic → topic. An OWNED, expert-validated artifact:
 * `confirmed` is false until a steward confirms it (A2). The engine may propose
 * edges; only confirmed edges are trusted for routing.
 */
export const Edge = z.object({
  id: OntologyId,
  from_topic_id: OntologyId.describe("The prerequisite topic — must be secure first."),
  to_topic_id: OntologyId.describe("The dependent topic — rests on the prerequisite."),
  kind: PrerequisiteKind,
  confirmed: z
    .boolean()
    .describe("True only once a human steward has validated the edge. Proposed edges are never trusted for routing."),
  rationale: z.string().describe("Why the dependency holds — plain language, for explainability."),
});
export type Edge = z.infer<typeof Edge>;

/**
 * A cross-board equivalence reference. Maps a node in this ontology to the
 * conceptually equivalent node in another board's ontology, so a learner's
 * evidence travels across boards without the platform hard-coding any board.
 */
export const CrossBoardEquivalence = z.object({
  id: OntologyId,
  node_id: OntologyId.describe("The node in this ontology."),
  node_kind: OntologyNodeKind,
  equivalent_board_code: z.string().describe("Board code of the other board (a label, not an enum)."),
  equivalent_node_id: OntologyId.optional().describe("The matching node id in the other board's ontology, when known."),
  equivalent_label: z.string().describe("Human-readable label of the equivalent node in the other board."),
  confidence: z.number().min(0).max(1).describe("How strong the equivalence is, in [0,1]."),
});
export type CrossBoardEquivalence = z.infer<typeof CrossBoardEquivalence>;

/**
 * The full ontology snapshot for a board+grade. The seed constant conforms to
 * this. A snapshot is a flat set of typed node tables plus the edge and
 * equivalence lists — projections build trees from it as needed.
 */
export const OntologySnapshot = z.object({
  board: Board,
  grades: z.array(Grade),
  subjects: z.array(Subject),
  units: z.array(Unit),
  chapters: z.array(Chapter),
  topics: z.array(Topic),
  outcomes: z.array(Outcome),
  competencies: z.array(Competency),
  edges: z.array(Edge),
  equivalences: z.array(CrossBoardEquivalence),
});
export type OntologySnapshot = z.infer<typeof OntologySnapshot>;
