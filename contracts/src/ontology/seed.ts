/**
 * The SEED ontology — Class 10, two subjects (Mathematics, Physics), on a
 * neutral example board.
 *
 * This is real, board-agnostic seed data: a labelled "Example State Board" node
 * (NOT a real board, no board lock-in), Class 10, with units → chapters →
 * topics → outcomes and a prerequisite graph with realistic edges. It is the
 * narrow path Slice 1 proves on — one board, one grade, two subjects — while
 * the contract stays board-agnostic.
 *
 * Ids are fixed, deterministic UUIDs so projections and tests can reference
 * nodes by constant. They are opaque tokens; nothing about a person lives here.
 */

import { OntologySnapshot } from "./types.js";

// ---------------------------------------------------------------------------
// Stable id constants. Format: c1a55e55-…-<readable-suffix> kept UUID-valid.
// ---------------------------------------------------------------------------

const ID = {
  board: "b0a11000-0000-4000-8000-000000000001",
  grade10: "61ade100-0000-4000-8000-000000000010",

  // Mathematics
  subjMath: "5ec70000-0000-4000-8000-0000000000a1",
  unitRealNumbers: "00170000-0000-4000-8000-000000000101",
  unitPolynomials: "00170000-0000-4000-8000-000000000102",
  unitTrig: "00170000-0000-4000-8000-000000000103",

  chRealNumbers: "c0a70000-0000-4000-8000-000000000201",
  chPolynomials: "c0a70000-0000-4000-8000-000000000202",
  chTrig: "c0a70000-0000-4000-8000-000000000203",

  tEuclid: "70910000-0000-4000-8000-000000000301",
  tFundThm: "70910000-0000-4000-8000-000000000302",
  tIrrational: "70910000-0000-4000-8000-000000000303",
  tPolyDegreeZeros: "70910000-0000-4000-8000-000000000304",
  tPolyCoeffRel: "70910000-0000-4000-8000-000000000305",
  tTrigRatios: "70910000-0000-4000-8000-000000000306",
  tTrigIdentities: "70910000-0000-4000-8000-000000000307",

  // Physics
  subjPhys: "5ec70000-0000-4000-8000-0000000000b1",
  unitLight: "00170000-0000-4000-8000-000000000111",
  unitElectricity: "00170000-0000-4000-8000-000000000112",

  chReflection: "c0a70000-0000-4000-8000-000000000211",
  chRefraction: "c0a70000-0000-4000-8000-000000000212",
  chCurrent: "c0a70000-0000-4000-8000-000000000213",

  tReflectionLaws: "70910000-0000-4000-8000-000000000311",
  tSphericalMirrors: "70910000-0000-4000-8000-000000000312",
  tRefractionLaws: "70910000-0000-4000-8000-000000000313",
  tLensesImages: "70910000-0000-4000-8000-000000000314",
  tOhmsLaw: "70910000-0000-4000-8000-000000000315",
  tResistorsSeriesParallel: "70910000-0000-4000-8000-000000000316",

  // Competencies
  compNumberReasoning: "c0590000-0000-4000-8000-000000000401",
  compAlgebraicReasoning: "c0590000-0000-4000-8000-000000000402",
  compGeomOptics: "c0590000-0000-4000-8000-000000000403",
  compCircuitReasoning: "c0590000-0000-4000-8000-000000000404",
} as const;

let outcomeSeq = 0;
const oid = (suffix: number) =>
  `0c700000-0000-4000-8000-${String(suffix).padStart(12, "0")}`;
const nextOutcome = () => oid(++outcomeSeq);

// Capture outcome ids as we build, so competencies can reference them.
const O = {
  euclid: nextOutcome(),
  fundThm: nextOutcome(),
  irrational: nextOutcome(),
  polyZeros: nextOutcome(),
  polyCoeff: nextOutcome(),
  trigRatios: nextOutcome(),
  trigIdentities: nextOutcome(),
  reflectionLaws: nextOutcome(),
  sphericalMirrors: nextOutcome(),
  refractionLaws: nextOutcome(),
  lensesImages: nextOutcome(),
  ohmsLaw: nextOutcome(),
  resistorsSP: nextOutcome(),
} as const;

let edgeSeq = 0;
const eid = () =>
  `ed9e0000-0000-4000-8000-${String(++edgeSeq).padStart(12, "0")}`;

/**
 * The seed snapshot. Conforms to OntologySnapshot. Exported as the canonical
 * narrow-path ontology for Slice 1.
 */
export const SEED_ONTOLOGY: OntologySnapshot = {
  board: {
    id: ID.board,
    kind: "board",
    code: "example-state-board",
    name: "Example State Board",
    region: "Example Region",
  },

  grades: [{ id: ID.grade10, kind: "grade", board_id: ID.board, level: 10, name: "Class 10" }],

  subjects: [
    { id: ID.subjMath, kind: "subject", grade_id: ID.grade10, name: "Mathematics" },
    { id: ID.subjPhys, kind: "subject", grade_id: ID.grade10, name: "Physics" },
  ],

  units: [
    { id: ID.unitRealNumbers, kind: "unit", subject_id: ID.subjMath, name: "Real Numbers", sequence: 0 },
    { id: ID.unitPolynomials, kind: "unit", subject_id: ID.subjMath, name: "Polynomials", sequence: 1 },
    { id: ID.unitTrig, kind: "unit", subject_id: ID.subjMath, name: "Trigonometry", sequence: 2 },
    { id: ID.unitLight, kind: "unit", subject_id: ID.subjPhys, name: "Light — Reflection and Refraction", sequence: 0 },
    { id: ID.unitElectricity, kind: "unit", subject_id: ID.subjPhys, name: "Electricity", sequence: 1 },
  ],

  chapters: [
    { id: ID.chRealNumbers, kind: "chapter", unit_id: ID.unitRealNumbers, name: "Real Numbers", sequence: 0 },
    { id: ID.chPolynomials, kind: "chapter", unit_id: ID.unitPolynomials, name: "Polynomials", sequence: 0 },
    { id: ID.chTrig, kind: "chapter", unit_id: ID.unitTrig, name: "Introduction to Trigonometry", sequence: 0 },
    { id: ID.chReflection, kind: "chapter", unit_id: ID.unitLight, name: "Reflection of Light", sequence: 0 },
    { id: ID.chRefraction, kind: "chapter", unit_id: ID.unitLight, name: "Refraction of Light", sequence: 1 },
    { id: ID.chCurrent, kind: "chapter", unit_id: ID.unitElectricity, name: "Electric Current and Circuits", sequence: 0 },
  ],

  topics: [
    // Mathematics — Real Numbers
    { id: ID.tEuclid, kind: "topic", chapter_id: ID.chRealNumbers, name: "Euclid's Division Lemma and HCF", sequence: 0 },
    { id: ID.tFundThm, kind: "topic", chapter_id: ID.chRealNumbers, name: "Fundamental Theorem of Arithmetic", sequence: 1 },
    { id: ID.tIrrational, kind: "topic", chapter_id: ID.chRealNumbers, name: "Irrational Numbers and Proofs", sequence: 2 },
    // Mathematics — Polynomials
    { id: ID.tPolyDegreeZeros, kind: "topic", chapter_id: ID.chPolynomials, name: "Degree and Zeros of a Polynomial", sequence: 0 },
    { id: ID.tPolyCoeffRel, kind: "topic", chapter_id: ID.chPolynomials, name: "Relationship Between Zeros and Coefficients", sequence: 1 },
    // Mathematics — Trigonometry
    { id: ID.tTrigRatios, kind: "topic", chapter_id: ID.chTrig, name: "Trigonometric Ratios of an Acute Angle", sequence: 0 },
    { id: ID.tTrigIdentities, kind: "topic", chapter_id: ID.chTrig, name: "Trigonometric Identities", sequence: 1 },
    // Physics — Light
    { id: ID.tReflectionLaws, kind: "topic", chapter_id: ID.chReflection, name: "Laws of Reflection", sequence: 0 },
    { id: ID.tSphericalMirrors, kind: "topic", chapter_id: ID.chReflection, name: "Spherical Mirrors and Image Formation", sequence: 1 },
    { id: ID.tRefractionLaws, kind: "topic", chapter_id: ID.chRefraction, name: "Laws of Refraction and Refractive Index", sequence: 0 },
    { id: ID.tLensesImages, kind: "topic", chapter_id: ID.chRefraction, name: "Lenses and Image Formation", sequence: 1 },
    // Physics — Electricity
    { id: ID.tOhmsLaw, kind: "topic", chapter_id: ID.chCurrent, name: "Ohm's Law and Resistance", sequence: 0 },
    { id: ID.tResistorsSeriesParallel, kind: "topic", chapter_id: ID.chCurrent, name: "Resistors in Series and Parallel", sequence: 1 },
  ],

  outcomes: [
    { id: O.euclid, kind: "outcome", topic_id: ID.tEuclid, statement: "Applies Euclid's division lemma to compute the HCF of two positive integers." },
    { id: O.fundThm, kind: "outcome", topic_id: ID.tFundThm, statement: "Expresses a composite number as a product of primes and uses it to find HCF and LCM." },
    { id: O.irrational, kind: "outcome", topic_id: ID.tIrrational, statement: "Proves that a given number such as the square root of 2 is irrational by contradiction." },
    { id: O.polyZeros, kind: "outcome", topic_id: ID.tPolyDegreeZeros, statement: "Identifies the degree of a polynomial and finds its zeros graphically and algebraically." },
    { id: O.polyCoeff, kind: "outcome", topic_id: ID.tPolyCoeffRel, statement: "Verifies the relationship between the zeros and coefficients of a quadratic polynomial." },
    { id: O.trigRatios, kind: "outcome", topic_id: ID.tTrigRatios, statement: "Computes the six trigonometric ratios of an acute angle from a right triangle." },
    { id: O.trigIdentities, kind: "outcome", topic_id: ID.tTrigIdentities, statement: "Proves and applies the standard trigonometric identities to simplify expressions." },
    { id: O.reflectionLaws, kind: "outcome", topic_id: ID.tReflectionLaws, statement: "States the laws of reflection and applies them to plane surfaces." },
    { id: O.sphericalMirrors, kind: "outcome", topic_id: ID.tSphericalMirrors, statement: "Predicts the nature, position, and size of images formed by concave and convex mirrors." },
    { id: O.refractionLaws, kind: "outcome", topic_id: ID.tRefractionLaws, statement: "States the laws of refraction and calculates refractive index using Snell's law." },
    { id: O.lensesImages, kind: "outcome", topic_id: ID.tLensesImages, statement: "Uses the lens formula and ray diagrams to locate images formed by convex and concave lenses." },
    { id: O.ohmsLaw, kind: "outcome", topic_id: ID.tOhmsLaw, statement: "Applies Ohm's law to relate potential difference, current, and resistance in a conductor." },
    { id: O.resistorsSP, kind: "outcome", topic_id: ID.tResistorsSeriesParallel, statement: "Computes equivalent resistance for resistors combined in series and in parallel." },
  ],

  competencies: [
    {
      id: ID.compNumberReasoning,
      kind: "competency",
      subject_id: ID.subjMath,
      name: "Number reasoning and divisibility",
      statement: "Reasons about integer structure, factorisation, and number classification.",
      outcome_ids: [O.euclid, O.fundThm, O.irrational],
    },
    {
      id: ID.compAlgebraicReasoning,
      kind: "competency",
      subject_id: ID.subjMath,
      name: "Algebraic and trigonometric reasoning",
      statement: "Manipulates polynomials and trigonometric relationships to solve problems.",
      outcome_ids: [O.polyZeros, O.polyCoeff, O.trigRatios, O.trigIdentities],
    },
    {
      id: ID.compGeomOptics,
      kind: "competency",
      subject_id: ID.subjPhys,
      name: "Geometric optics",
      statement: "Predicts image formation by mirrors and lenses from reflection and refraction principles.",
      outcome_ids: [O.reflectionLaws, O.sphericalMirrors, O.refractionLaws, O.lensesImages],
    },
    {
      id: ID.compCircuitReasoning,
      kind: "competency",
      subject_id: ID.subjPhys,
      name: "Circuit reasoning",
      statement: "Analyses simple resistive circuits using Ohm's law and combination rules.",
      outcome_ids: [O.ohmsLaw, O.resistorsSP],
    },
  ],

  edges: [
    // Mathematics — Real Numbers internal chain
    { id: eid(), from_topic_id: ID.tEuclid, to_topic_id: ID.tFundThm, kind: "soft", confirmed: true, rationale: "Comfort with HCF via division supports prime-factorisation reasoning for HCF and LCM." },
    { id: eid(), from_topic_id: ID.tFundThm, to_topic_id: ID.tIrrational, kind: "hard", confirmed: true, rationale: "Irrationality proofs rely on unique prime factorisation from the fundamental theorem." },
    // Mathematics — Polynomials
    { id: eid(), from_topic_id: ID.tPolyDegreeZeros, to_topic_id: ID.tPolyCoeffRel, kind: "hard", confirmed: true, rationale: "The zeros-coefficient relationship presupposes the learner can identify a polynomial's zeros." },
    // Mathematics — Trigonometry
    { id: eid(), from_topic_id: ID.tTrigRatios, to_topic_id: ID.tTrigIdentities, kind: "hard", confirmed: true, rationale: "Identities are stated and proved in terms of the basic ratios, which must be secure first." },
    // Cross-chapter math prerequisite: ratios need fluency with surds from real numbers
    { id: eid(), from_topic_id: ID.tIrrational, to_topic_id: ID.tTrigRatios, kind: "soft", confirmed: false, rationale: "Proposed: trig ratios often produce surd values; comfort with irrationals reduces friction. Awaiting steward confirmation." },
    // Physics — Light reflection chain
    { id: eid(), from_topic_id: ID.tReflectionLaws, to_topic_id: ID.tSphericalMirrors, kind: "hard", confirmed: true, rationale: "Image formation by mirrors is derived by applying the laws of reflection at the surface." },
    // Physics — refraction chain
    { id: eid(), from_topic_id: ID.tRefractionLaws, to_topic_id: ID.tLensesImages, kind: "hard", confirmed: true, rationale: "Lens behaviour follows from refraction at curved surfaces; Snell's law must be understood first." },
    // Physics — reflection geometry transfers to refraction ray diagrams
    { id: eid(), from_topic_id: ID.tSphericalMirrors, to_topic_id: ID.tLensesImages, kind: "soft", confirmed: true, rationale: "Ray-diagram and sign-convention skills from mirrors transfer to lens problems." },
    // Physics — Electricity chain
    { id: eid(), from_topic_id: ID.tOhmsLaw, to_topic_id: ID.tResistorsSeriesParallel, kind: "hard", confirmed: true, rationale: "Series and parallel equivalents are derived by applying Ohm's law across combinations." },
  ],

  equivalences: [
    {
      id: "e9010000-0000-4000-8000-000000000001",
      node_id: ID.tEuclid,
      node_kind: "topic",
      equivalent_board_code: "another-example-board",
      equivalent_label: "Euclidean algorithm for HCF (Class 10, Number Systems)",
      confidence: 0.95,
    },
    {
      id: "e9010000-0000-4000-8000-000000000002",
      node_id: ID.tOhmsLaw,
      node_kind: "topic",
      equivalent_board_code: "another-example-board",
      equivalent_label: "Ohm's law and resistance (Class 10, Current Electricity)",
      confidence: 0.97,
    },
  ],
};

/** The stable id map for the seed, for tests and projections to reference nodes by constant. */
export const SEED_ONTOLOGY_IDS = { ...ID, outcomes: O };
