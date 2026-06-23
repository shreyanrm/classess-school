/**
 * The SEED ontology — a rich, board-agnostic curriculum graph.
 *
 * This expands the original narrow proof (one board, Class 10, Mathematics +
 * Physics) into a realistic graph that makes the curriculum and hyperlocalisation
 * surfaces real:
 *
 *   - TWO neutral example boards ("Example National Board" and "Example State
 *     Board"). The board is a FIELD, never a baked-in enum — neither is a real
 *     board, and nothing privileges one over the other.
 *   - Grades 9 and 10 on each board.
 *   - Six subjects per board (Mathematics, Physics, Chemistry, Biology, English,
 *     Social Science), each with units → chapters → topics → outcomes.
 *   - Realistic prerequisite edges, both within a grade and ACROSS grades
 *     (Class 9 secures the ground Class 10 rests on).
 *   - CROSS-BOARD EQUIVALENCES that resolve to real topic ids in the other
 *     board's snapshot, so a learner's evidence can travel across boards without
 *     the platform hard-coding any board.
 *
 * The schema `OntologySnapshot` describes ONE board+grade-range snapshot. We keep
 * `SEED_ONTOLOGY` as the canonical (national) snapshot — still a single valid
 * `OntologySnapshot` — and additionally export the state-board snapshot and a
 * combined view so cross-board equivalence is genuinely exercised.
 *
 * Ids are fixed, deterministic UUIDs so projections and tests can reference nodes
 * by constant. They are opaque tokens; nothing about a person lives here. The seed
 * is structured as composable per-subject builders for readability; the exported
 * `SEED_ONTOLOGY` is assembled into a single valid snapshot.
 */

import {
  OntologySnapshot,
  type Board,
  type Grade,
  type Subject,
  type Unit,
  type Chapter,
  type Topic,
  type Outcome,
  type Competency,
  type Edge,
  type CrossBoardEquivalence,
  type OntologyNodeKind,
} from "./types.js";

// ---------------------------------------------------------------------------
// Deterministic UUID generators.
//
// Every node kind gets its own UUID "family" (a fixed high segment) and a
// monotonic counter for the low segment, so ids are stable across builds and
// unique by construction. The format stays UUID-v4-valid (version nibble 4,
// variant nibble 8) to satisfy z.string().uuid().
// ---------------------------------------------------------------------------

type Family =
  | "board"
  | "grade"
  | "subject"
  | "unit"
  | "chapter"
  | "topic"
  | "outcome"
  | "competency"
  | "edge"
  | "equiv";

const FAMILY_PREFIX: Record<Family, string> = {
  board: "b0a11000",
  grade: "61ade100",
  subject: "5ec70000",
  unit: "00170000",
  chapter: "c0a70000",
  topic: "70910000",
  outcome: "0c700000",
  competency: "c0590000",
  edge: "ed9e0000",
  equiv: "e9010000",
};

const counters: Record<Family, number> = {
  board: 0,
  grade: 0,
  subject: 0,
  unit: 0,
  chapter: 0,
  topic: 0,
  outcome: 0,
  competency: 0,
  edge: 0,
  equiv: 0,
};

/** Mint the next deterministic UUID for a node family. */
function uid(family: Family): string {
  const n = ++counters[family];
  return `${FAMILY_PREFIX[family]}-0000-4000-8000-${String(n).padStart(12, "0")}`;
}

// ---------------------------------------------------------------------------
// Composable builders.
//
// A `BoardBuilder` accumulates flat node tables for a single board, and resolves
// human handles → minted ids so prerequisite edges and cross-board equivalences
// can be written declaratively against readable handles.
// ---------------------------------------------------------------------------

interface TopicSpec {
  handle: string;
  name: string;
  outcome: string; // the can-do statement for this topic's primary outcome
}

interface ChapterSpec {
  name: string;
  topics: TopicSpec[];
}

interface UnitSpec {
  name: string;
  chapters: ChapterSpec[];
}

interface CompetencySpec {
  name: string;
  statement: string;
  /** Topic handles whose outcomes roll up into this competency. */
  topicHandles: string[];
}

interface SubjectSpec {
  name: string;
  units: UnitSpec[];
  competencies?: CompetencySpec[];
}

class BoardBuilder {
  readonly board: Board;
  readonly grades: Grade[] = [];
  readonly subjects: Subject[] = [];
  readonly units: Unit[] = [];
  readonly chapters: Chapter[] = [];
  readonly topics: Topic[] = [];
  readonly outcomes: Outcome[] = [];
  readonly competencies: Competency[] = [];
  readonly edges: Edge[] = [];
  readonly equivalences: CrossBoardEquivalence[] = [];

  /** handle → topic id, scoped per board (handles are prefixed by board code). */
  private readonly topicByHandle = new Map<string, string>();
  /** handle → primary outcome id for that topic. */
  private readonly outcomeByHandle = new Map<string, string>();
  /** "<gradeId>:<subjectName>" → subject id, for resolving subjects by grade + name. */
  private readonly subjectByGradeName = new Map<string, string>();

  constructor(args: { code: string; name: string; region?: string }) {
    this.board = {
      id: uid("board"),
      kind: "board",
      code: args.code,
      name: args.name,
      region: args.region,
    };
  }

  get code(): string {
    return this.board.code;
  }

  /** Add a grade and return its id. */
  addGrade(level: number, name: string): string {
    const id = uid("grade");
    this.grades.push({ id, kind: "grade", board_id: this.board.id, level, name });
    return id;
  }

  /** Add a fully-specified subject under a grade. */
  addSubject(gradeId: string, spec: SubjectSpec): string {
    const subjectId = uid("subject");
    this.subjects.push({ id: subjectId, kind: "subject", grade_id: gradeId, name: spec.name });
    this.subjectByGradeName.set(`${gradeId}:${spec.name}`, subjectId);

    spec.units.forEach((unitSpec, unitSeq) => {
      const unitId = uid("unit");
      this.units.push({ id: unitId, kind: "unit", subject_id: subjectId, name: unitSpec.name, sequence: unitSeq });

      unitSpec.chapters.forEach((chapterSpec, chapterSeq) => {
        const chapterId = uid("chapter");
        this.chapters.push({ id: chapterId, kind: "chapter", unit_id: unitId, name: chapterSpec.name, sequence: chapterSeq });

        chapterSpec.topics.forEach((topicSpec, topicSeq) => {
          const topicId = uid("topic");
          this.topics.push({ id: topicId, kind: "topic", chapter_id: chapterId, name: topicSpec.name, sequence: topicSeq });
          this.topicByHandle.set(topicSpec.handle, topicId);

          const outcomeId = uid("outcome");
          this.outcomes.push({ id: outcomeId, kind: "outcome", topic_id: topicId, statement: topicSpec.outcome });
          this.outcomeByHandle.set(topicSpec.handle, outcomeId);
        });
      });
    });

    for (const compSpec of spec.competencies ?? []) {
      this.competencies.push({
        id: uid("competency"),
        kind: "competency",
        subject_id: subjectId,
        name: compSpec.name,
        statement: compSpec.statement,
        outcome_ids: compSpec.topicHandles.map((h) => this.outcomeId(h)),
      });
    }

    return subjectId;
  }

  /** Resolve a subject id by its grade id and subject name. */
  subjectId(gradeId: string, name: string): string {
    const id = this.subjectByGradeName.get(`${gradeId}:${name}`);
    if (!id) throw new Error(`[${this.code}] unknown subject: ${name} in grade ${gradeId}`);
    return id;
  }

  /** Resolve a grade id by its numeric level. */
  gradeId(level: number): string {
    const g = this.grades.find((x) => x.level === level);
    if (!g) throw new Error(`[${this.code}] unknown grade level: ${level}`);
    return g.id;
  }

  /** Resolve a topic handle to its id (throws on typos — fails the build loudly). */
  topicId(handle: string): string {
    const id = this.topicByHandle.get(handle);
    if (!id) throw new Error(`[${this.code}] unknown topic handle: ${handle}`);
    return id;
  }

  /** Resolve a topic handle to its primary outcome id. */
  outcomeId(handle: string): string {
    const id = this.outcomeByHandle.get(handle);
    if (!id) throw new Error(`[${this.code}] unknown outcome handle: ${handle}`);
    return id;
  }

  /** Add a prerequisite edge between two topic handles. */
  addEdge(args: {
    from: string;
    to: string;
    kind: Edge["kind"];
    confirmed: boolean;
    rationale: string;
  }): void {
    this.edges.push({
      id: uid("edge"),
      from_topic_id: this.topicId(args.from),
      to_topic_id: this.topicId(args.to),
      kind: args.kind,
      confirmed: args.confirmed,
      rationale: args.rationale,
    });
  }

  /** Add a cross-board equivalence from one of THIS board's topics to another board's topic. */
  addEquivalence(args: {
    handle: string;
    nodeKind?: OntologyNodeKind;
    toBoard: BoardBuilder;
    toHandle: string;
    label: string;
    confidence: number;
  }): void {
    this.equivalences.push({
      id: uid("equiv"),
      node_id: this.topicId(args.handle),
      node_kind: args.nodeKind ?? "topic",
      equivalent_board_code: args.toBoard.code,
      equivalent_node_id: args.toBoard.topicId(args.toHandle),
      equivalent_label: args.label,
      confidence: args.confidence,
    });
  }

  /** Assemble the accumulated tables into a single valid snapshot. */
  snapshot(): OntologySnapshot {
    return {
      board: this.board,
      grades: this.grades,
      subjects: this.subjects,
      units: this.units,
      chapters: this.chapters,
      topics: this.topics,
      outcomes: this.outcomes,
      competencies: this.competencies,
      edges: this.edges,
      equivalences: this.equivalences,
    };
  }
}

// ---------------------------------------------------------------------------
// Subject builders — board-agnostic curriculum specs.
//
// Handles are written as `${code}:${grade}:${subject}:${topic}` so they are
// unique per board and grade. Each builder returns a SubjectSpec; the two boards
// reuse the same spec factories (the curriculum content is genuinely shared,
// only the board label and the equivalence wiring differ).
// ---------------------------------------------------------------------------

const h = (code: string, grade: number, subject: string, topic: string) =>
  `${code}:g${grade}:${subject}:${topic}`;

function mathematics(code: string, grade: number): SubjectSpec {
  if (grade === 9) {
    return {
      name: "Mathematics",
      units: [
        {
          name: "Number Systems",
          chapters: [
            {
              name: "Number Systems",
              topics: [
                { handle: h(code, 9, "math", "rational"), name: "Rational Numbers on the Number Line", outcome: "Represents rational numbers on the number line and orders them." },
                { handle: h(code, 9, "math", "irrational9"), name: "Irrational Numbers and Real Numbers", outcome: "Distinguishes rational from irrational numbers and places real numbers on the line." },
                { handle: h(code, 9, "math", "surds"), name: "Operations on Surds and Rationalisation", outcome: "Performs operations on surds and rationalises a denominator." },
              ],
            },
          ],
        },
        {
          name: "Algebra",
          chapters: [
            {
              name: "Polynomials",
              topics: [
                { handle: h(code, 9, "math", "polyintro"), name: "Polynomials in One Variable", outcome: "Identifies polynomials, their degree, and standard terminology." },
                { handle: h(code, 9, "math", "remfactor"), name: "Remainder and Factor Theorems", outcome: "Applies the remainder and factor theorems to factorise polynomials." },
              ],
            },
            {
              name: "Linear Equations in Two Variables",
              topics: [
                { handle: h(code, 9, "math", "lineqtwo"), name: "Linear Equations in Two Variables", outcome: "Writes and graphs linear equations in two variables." },
              ],
            },
          ],
        },
        {
          name: "Coordinate Geometry",
          chapters: [
            {
              name: "Coordinate Geometry",
              topics: [
                { handle: h(code, 9, "math", "cartesian"), name: "The Cartesian Plane", outcome: "Plots points in the Cartesian plane and reads coordinates." },
              ],
            },
          ],
        },
      ],
      competencies: [
        {
          name: "Number sense",
          statement: "Reasons about the structure of the real number system and surd arithmetic.",
          topicHandles: [h(code, 9, "math", "rational"), h(code, 9, "math", "irrational9"), h(code, 9, "math", "surds")],
        },
        {
          name: "Foundational algebra",
          statement: "Manipulates polynomials and linear relationships fluently.",
          topicHandles: [h(code, 9, "math", "polyintro"), h(code, 9, "math", "remfactor"), h(code, 9, "math", "lineqtwo")],
        },
      ],
    };
  }
  // grade 10
  return {
    name: "Mathematics",
    units: [
      {
        name: "Real Numbers",
        chapters: [
          {
            name: "Real Numbers",
            topics: [
              { handle: h(code, 10, "math", "euclid"), name: "Euclid's Division Lemma and HCF", outcome: "Applies Euclid's division lemma to compute the HCF of two positive integers." },
              { handle: h(code, 10, "math", "fundthm"), name: "Fundamental Theorem of Arithmetic", outcome: "Expresses a composite number as a product of primes and uses it to find HCF and LCM." },
              { handle: h(code, 10, "math", "irrational"), name: "Irrational Numbers and Proofs", outcome: "Proves that a given number such as the square root of 2 is irrational by contradiction." },
            ],
          },
        ],
      },
      {
        name: "Polynomials",
        chapters: [
          {
            name: "Polynomials",
            topics: [
              { handle: h(code, 10, "math", "polyzeros"), name: "Degree and Zeros of a Polynomial", outcome: "Identifies the degree of a polynomial and finds its zeros graphically and algebraically." },
              { handle: h(code, 10, "math", "polycoeff"), name: "Relationship Between Zeros and Coefficients", outcome: "Verifies the relationship between the zeros and coefficients of a quadratic polynomial." },
            ],
          },
        ],
      },
      {
        name: "Trigonometry",
        chapters: [
          {
            name: "Introduction to Trigonometry",
            topics: [
              { handle: h(code, 10, "math", "trigratios"), name: "Trigonometric Ratios of an Acute Angle", outcome: "Computes the six trigonometric ratios of an acute angle from a right triangle." },
              { handle: h(code, 10, "math", "trigidentities"), name: "Trigonometric Identities", outcome: "Proves and applies the standard trigonometric identities to simplify expressions." },
            ],
          },
        ],
      },
    ],
    competencies: [
      {
        name: "Number reasoning and divisibility",
        statement: "Reasons about integer structure, factorisation, and number classification.",
        topicHandles: [h(code, 10, "math", "euclid"), h(code, 10, "math", "fundthm"), h(code, 10, "math", "irrational")],
      },
      {
        name: "Algebraic and trigonometric reasoning",
        statement: "Manipulates polynomials and trigonometric relationships to solve problems.",
        topicHandles: [
          h(code, 10, "math", "polyzeros"),
          h(code, 10, "math", "polycoeff"),
          h(code, 10, "math", "trigratios"),
          h(code, 10, "math", "trigidentities"),
        ],
      },
    ],
  };
}

function physics(code: string, grade: number): SubjectSpec {
  if (grade === 9) {
    return {
      name: "Physics",
      units: [
        {
          name: "Motion and Force",
          chapters: [
            {
              name: "Motion",
              topics: [
                { handle: h(code, 9, "phys", "motion"), name: "Describing Motion and Kinematic Equations", outcome: "Describes uniform and non-uniform motion and applies the equations of motion." },
              ],
            },
            {
              name: "Force and Laws of Motion",
              topics: [
                { handle: h(code, 9, "phys", "newton"), name: "Newton's Laws of Motion", outcome: "States Newton's laws and uses them to explain everyday motion." },
              ],
            },
          ],
        },
        {
          name: "Energy",
          chapters: [
            {
              name: "Work and Energy",
              topics: [
                { handle: h(code, 9, "phys", "work"), name: "Work, Power, and Energy", outcome: "Relates work, power, and kinetic and potential energy quantitatively." },
              ],
            },
          ],
        },
      ],
      competencies: [
        {
          name: "Mechanics reasoning",
          statement: "Explains and predicts motion using force and energy principles.",
          topicHandles: [h(code, 9, "phys", "motion"), h(code, 9, "phys", "newton"), h(code, 9, "phys", "work")],
        },
      ],
    };
  }
  return {
    name: "Physics",
    units: [
      {
        name: "Light — Reflection and Refraction",
        chapters: [
          {
            name: "Reflection of Light",
            topics: [
              { handle: h(code, 10, "phys", "reflection"), name: "Laws of Reflection", outcome: "States the laws of reflection and applies them to plane surfaces." },
              { handle: h(code, 10, "phys", "mirrors"), name: "Spherical Mirrors and Image Formation", outcome: "Predicts the nature, position, and size of images formed by concave and convex mirrors." },
            ],
          },
          {
            name: "Refraction of Light",
            topics: [
              { handle: h(code, 10, "phys", "refraction"), name: "Laws of Refraction and Refractive Index", outcome: "States the laws of refraction and calculates refractive index using Snell's law." },
              { handle: h(code, 10, "phys", "lenses"), name: "Lenses and Image Formation", outcome: "Uses the lens formula and ray diagrams to locate images formed by convex and concave lenses." },
            ],
          },
        ],
      },
      {
        name: "Electricity",
        chapters: [
          {
            name: "Electric Current and Circuits",
            topics: [
              { handle: h(code, 10, "phys", "ohm"), name: "Ohm's Law and Resistance", outcome: "Applies Ohm's law to relate potential difference, current, and resistance in a conductor." },
              { handle: h(code, 10, "phys", "resistors"), name: "Resistors in Series and Parallel", outcome: "Computes equivalent resistance for resistors combined in series and in parallel." },
            ],
          },
        ],
      },
    ],
    competencies: [
      {
        name: "Geometric optics",
        statement: "Predicts image formation by mirrors and lenses from reflection and refraction principles.",
        topicHandles: [
          h(code, 10, "phys", "reflection"),
          h(code, 10, "phys", "mirrors"),
          h(code, 10, "phys", "refraction"),
          h(code, 10, "phys", "lenses"),
        ],
      },
      {
        name: "Circuit reasoning",
        statement: "Analyses simple resistive circuits using Ohm's law and combination rules.",
        topicHandles: [h(code, 10, "phys", "ohm"), h(code, 10, "phys", "resistors")],
      },
    ],
  };
}

function chemistry(code: string, grade: number): SubjectSpec {
  if (grade === 9) {
    return {
      name: "Chemistry",
      units: [
        {
          name: "Matter",
          chapters: [
            {
              name: "Matter in Our Surroundings",
              topics: [
                { handle: h(code, 9, "chem", "states"), name: "States of Matter and Change of State", outcome: "Explains the states of matter and changes of state using particle behaviour." },
              ],
            },
            {
              name: "Is Matter Around Us Pure",
              topics: [
                { handle: h(code, 9, "chem", "mixtures"), name: "Mixtures, Solutions, and Separation", outcome: "Classifies matter as mixtures or pure substances and selects separation techniques." },
              ],
            },
          ],
        },
        {
          name: "Atoms and Molecules",
          chapters: [
            {
              name: "Atoms and Molecules",
              topics: [
                { handle: h(code, 9, "chem", "atoms"), name: "Atoms, Molecules, and Mole Concept", outcome: "Uses atomic and molecular masses and the mole concept in basic calculations." },
              ],
            },
          ],
        },
      ],
      competencies: [
        {
          name: "Particulate reasoning",
          statement: "Explains matter and its transformations at the particle level.",
          topicHandles: [h(code, 9, "chem", "states"), h(code, 9, "chem", "mixtures"), h(code, 9, "chem", "atoms")],
        },
      ],
    };
  }
  return {
    name: "Chemistry",
    units: [
      {
        name: "Chemical Reactions",
        chapters: [
          {
            name: "Chemical Reactions and Equations",
            topics: [
              { handle: h(code, 10, "chem", "reactions"), name: "Types of Chemical Reactions and Balancing", outcome: "Classifies and balances chemical equations for common reaction types." },
            ],
          },
        ],
      },
      {
        name: "Acids, Bases and Salts",
        chapters: [
          {
            name: "Acids, Bases and Salts",
            topics: [
              { handle: h(code, 10, "chem", "acidsbases"), name: "Acids, Bases, and the pH Scale", outcome: "Relates acid and base strength to the pH scale and explains neutralisation." },
              { handle: h(code, 10, "chem", "salts"), name: "Salts and Their Properties", outcome: "Explains the formation and properties of common salts." },
            ],
          },
        ],
      },
      {
        name: "Periodic Classification",
        chapters: [
          {
            name: "Periodic Classification of Elements",
            topics: [
              { handle: h(code, 10, "chem", "periodic"), name: "The Modern Periodic Table and Trends", outcome: "Predicts periodic trends in properties using position in the modern periodic table." },
            ],
          },
        ],
      },
    ],
    competencies: [
      {
        name: "Chemical change reasoning",
        statement: "Represents and reasons about chemical change and the behaviour of acids and bases.",
        topicHandles: [
          h(code, 10, "chem", "reactions"),
          h(code, 10, "chem", "acidsbases"),
          h(code, 10, "chem", "salts"),
        ],
      },
      {
        name: "Periodic reasoning",
        statement: "Uses periodic structure to predict elemental properties.",
        topicHandles: [h(code, 10, "chem", "periodic")],
      },
    ],
  };
}

function biology(code: string, grade: number): SubjectSpec {
  if (grade === 9) {
    return {
      name: "Biology",
      units: [
        {
          name: "Cell and Tissues",
          chapters: [
            {
              name: "The Fundamental Unit of Life",
              topics: [
                { handle: h(code, 9, "bio", "cell"), name: "Cell Structure and Organelles", outcome: "Identifies cell organelles and describes their functions." },
              ],
            },
            {
              name: "Tissues",
              topics: [
                { handle: h(code, 9, "bio", "tissues"), name: "Plant and Animal Tissues", outcome: "Distinguishes plant and animal tissues by structure and function." },
              ],
            },
          ],
        },
        {
          name: "Diversity in Living Organisms",
          chapters: [
            {
              name: "Diversity in Living Organisms",
              topics: [
                { handle: h(code, 9, "bio", "diversity"), name: "Classification of Living Organisms", outcome: "Classifies organisms using a hierarchical classification scheme." },
              ],
            },
          ],
        },
      ],
      competencies: [
        {
          name: "Life organisation",
          statement: "Explains how living things are organised from cells to classified diversity.",
          topicHandles: [h(code, 9, "bio", "cell"), h(code, 9, "bio", "tissues"), h(code, 9, "bio", "diversity")],
        },
      ],
    };
  }
  return {
    name: "Biology",
    units: [
      {
        name: "Life Processes",
        chapters: [
          {
            name: "Life Processes",
            topics: [
              { handle: h(code, 10, "bio", "nutrition"), name: "Nutrition and Respiration", outcome: "Explains nutrition and respiration as life processes in plants and animals." },
              { handle: h(code, 10, "bio", "transport"), name: "Transportation and Excretion", outcome: "Describes transport and excretion systems in living organisms." },
            ],
          },
        ],
      },
      {
        name: "Reproduction and Heredity",
        chapters: [
          {
            name: "How Organisms Reproduce",
            topics: [
              { handle: h(code, 10, "bio", "reproduction"), name: "Modes of Reproduction", outcome: "Compares asexual and sexual reproduction across organisms." },
            ],
          },
          {
            name: "Heredity and Evolution",
            topics: [
              { handle: h(code, 10, "bio", "heredity"), name: "Heredity and Inheritance", outcome: "Applies basic rules of inheritance to predict trait transmission." },
            ],
          },
        ],
      },
    ],
    competencies: [
      {
        name: "Physiology reasoning",
        statement: "Explains how organisms sustain life through interacting processes.",
        topicHandles: [h(code, 10, "bio", "nutrition"), h(code, 10, "bio", "transport")],
      },
      {
        name: "Inheritance reasoning",
        statement: "Reasons about reproduction and the transmission of traits.",
        topicHandles: [h(code, 10, "bio", "reproduction"), h(code, 10, "bio", "heredity")],
      },
    ],
  };
}

function english(code: string, grade: number): SubjectSpec {
  if (grade === 9) {
    return {
      name: "English",
      units: [
        {
          name: "Reading and Writing",
          chapters: [
            {
              name: "Reading Comprehension",
              topics: [
                { handle: h(code, 9, "eng", "reading"), name: "Comprehending Unseen Passages", outcome: "Extracts main ideas and inferences from an unseen prose passage." },
              ],
            },
            {
              name: "Writing Skills",
              topics: [
                { handle: h(code, 9, "eng", "paragraph"), name: "Paragraph and Notice Writing", outcome: "Writes a coherent paragraph and a clear notice for a given purpose." },
              ],
            },
          ],
        },
        {
          name: "Grammar",
          chapters: [
            {
              name: "Applied Grammar",
              topics: [
                { handle: h(code, 9, "eng", "grammar"), name: "Tenses and Sentence Structure", outcome: "Uses correct tense and sentence structure in context." },
              ],
            },
          ],
        },
      ],
      competencies: [
        {
          name: "Language foundations",
          statement: "Reads with comprehension and writes accurately for everyday purposes.",
          topicHandles: [h(code, 9, "eng", "reading"), h(code, 9, "eng", "paragraph"), h(code, 9, "eng", "grammar")],
        },
      ],
    };
  }
  return {
    name: "English",
    units: [
      {
        name: "Reading and Literature",
        chapters: [
          {
            name: "Reading Comprehension",
            topics: [
              { handle: h(code, 10, "eng", "reading"), name: "Analytical Reading of Passages", outcome: "Analyses tone, purpose, and argument in an unseen passage." },
            ],
          },
          {
            name: "Literature",
            topics: [
              { handle: h(code, 10, "eng", "literature"), name: "Responding to Prose and Poetry", outcome: "Interprets themes and devices in prescribed prose and poetry." },
            ],
          },
        ],
      },
      {
        name: "Writing and Grammar",
        chapters: [
          {
            name: "Writing Skills",
            topics: [
              { handle: h(code, 10, "eng", "writing"), name: "Letter and Analytical Paragraph Writing", outcome: "Composes formal letters and analytical paragraphs with appropriate register." },
            ],
          },
          {
            name: "Applied Grammar",
            topics: [
              { handle: h(code, 10, "eng", "grammar"), name: "Reported Speech and Editing", outcome: "Transforms sentences into reported speech and edits for grammatical accuracy." },
            ],
          },
        ],
      },
    ],
    competencies: [
      {
        name: "Reading and interpretation",
        statement: "Reads analytically and interprets literary texts.",
        topicHandles: [h(code, 10, "eng", "reading"), h(code, 10, "eng", "literature")],
      },
      {
        name: "Written expression",
        statement: "Writes accurately and appropriately for formal purposes.",
        topicHandles: [h(code, 10, "eng", "writing"), h(code, 10, "eng", "grammar")],
      },
    ],
  };
}

function socialScience(code: string, grade: number): SubjectSpec {
  if (grade === 9) {
    return {
      name: "Social Science",
      units: [
        {
          name: "History",
          chapters: [
            {
              name: "Events That Shaped the Modern World",
              topics: [
                { handle: h(code, 9, "soc", "revolutions"), name: "Revolutions and the Rise of the Modern State", outcome: "Explains causes and consequences of major modern revolutions." },
              ],
            },
          ],
        },
        {
          name: "Geography",
          chapters: [
            {
              name: "Physical Features and Climate",
              topics: [
                { handle: h(code, 9, "soc", "physical"), name: "Physical Features, Drainage, and Climate", outcome: "Relates physical features and drainage to regional climate patterns." },
              ],
            },
          ],
        },
        {
          name: "Civics",
          chapters: [
            {
              name: "Foundations of Democracy",
              topics: [
                { handle: h(code, 9, "soc", "democracy"), name: "Democracy and Constitutional Foundations", outcome: "Explains the basic principles of democracy and constitutional design." },
              ],
            },
          ],
        },
      ],
      competencies: [
        {
          name: "Historical and civic foundations",
          statement: "Connects historical change, geography, and democratic institutions.",
          topicHandles: [h(code, 9, "soc", "revolutions"), h(code, 9, "soc", "physical"), h(code, 9, "soc", "democracy")],
        },
      ],
    };
  }
  return {
    name: "Social Science",
    units: [
      {
        name: "History",
        chapters: [
          {
            name: "Nationalism and Industrial Change",
            topics: [
              { handle: h(code, 10, "soc", "nationalism"), name: "Nationalism and the Making of Nations", outcome: "Analyses how nationalism reshaped societies and borders." },
            ],
          },
        ],
      },
      {
        name: "Geography",
        chapters: [
          {
            name: "Resources and Development",
            topics: [
              { handle: h(code, 10, "soc", "resources"), name: "Resources, Agriculture, and Development", outcome: "Evaluates resource use and its link to sustainable development." },
            ],
          },
        ],
      },
      {
        name: "Civics and Economics",
        chapters: [
          {
            name: "Democratic Politics and the Economy",
            topics: [
              { handle: h(code, 10, "soc", "politics"), name: "Power Sharing and Federalism", outcome: "Explains power sharing and federal arrangements in a democracy." },
              { handle: h(code, 10, "soc", "economics"), name: "Sectors of the Economy", outcome: "Distinguishes economic sectors and interprets development indicators." },
            ],
          },
        ],
      },
    ],
    competencies: [
      {
        name: "Historical and spatial reasoning",
        statement: "Interprets historical change and the geography of development.",
        topicHandles: [h(code, 10, "soc", "nationalism"), h(code, 10, "soc", "resources")],
      },
      {
        name: "Civic and economic reasoning",
        statement: "Analyses democratic institutions and the structure of the economy.",
        topicHandles: [h(code, 10, "soc", "politics"), h(code, 10, "soc", "economics")],
      },
    ],
  };
}

const SUBJECT_BUILDERS = [mathematics, physics, chemistry, biology, english, socialScience] as const;

// ---------------------------------------------------------------------------
// Assemble the two boards.
// ---------------------------------------------------------------------------

function buildBoard(args: { code: string; name: string; region: string }): BoardBuilder {
  const b = new BoardBuilder(args);
  const grade9 = b.addGrade(9, "Class 9");
  const grade10 = b.addGrade(10, "Class 10");

  for (const make of SUBJECT_BUILDERS) {
    b.addSubject(grade9, make(args.code, 9));
    b.addSubject(grade10, make(args.code, 10));
  }
  return b;
}

const nationalCode = "example-national-board";
const stateCode = "example-state-board";

const national = buildBoard({ code: nationalCode, name: "Example National Board", region: "Example Nation" });
const state = buildBoard({ code: stateCode, name: "Example State Board", region: "Example Region" });

// ---------------------------------------------------------------------------
// Prerequisite edges per board — within-grade and cross-grade.
// Written declaratively against topic handles; the same dependency structure is
// applied to both boards.
// ---------------------------------------------------------------------------

function wireEdges(b: BoardBuilder, code: string): void {
  const T = (g: number, s: string, t: string) => h(code, g, s, t);

  // --- Mathematics, within Class 9 ---
  b.addEdge({ from: T(9, "math", "rational"), to: T(9, "math", "irrational9"), kind: "hard", confirmed: true, rationale: "Placing irrationals on the line builds on representing rationals there." });
  b.addEdge({ from: T(9, "math", "irrational9"), to: T(9, "math", "surds"), kind: "hard", confirmed: true, rationale: "Surd arithmetic presupposes recognising irrational numbers." });
  b.addEdge({ from: T(9, "math", "polyintro"), to: T(9, "math", "remfactor"), kind: "hard", confirmed: true, rationale: "The factor theorem is stated in the language of polynomials introduced first." });

  // --- Mathematics, within Class 10 ---
  b.addEdge({ from: T(10, "math", "euclid"), to: T(10, "math", "fundthm"), kind: "soft", confirmed: true, rationale: "Comfort with HCF via division supports prime-factorisation reasoning for HCF and LCM." });
  b.addEdge({ from: T(10, "math", "fundthm"), to: T(10, "math", "irrational"), kind: "hard", confirmed: true, rationale: "Irrationality proofs rely on unique prime factorisation from the fundamental theorem." });
  b.addEdge({ from: T(10, "math", "polyzeros"), to: T(10, "math", "polycoeff"), kind: "hard", confirmed: true, rationale: "The zeros-coefficient relationship presupposes the learner can identify a polynomial's zeros." });
  b.addEdge({ from: T(10, "math", "trigratios"), to: T(10, "math", "trigidentities"), kind: "hard", confirmed: true, rationale: "Identities are stated and proved in terms of the basic ratios, which must be secure first." });
  b.addEdge({ from: T(10, "math", "irrational"), to: T(10, "math", "trigratios"), kind: "soft", confirmed: false, rationale: "Proposed: trig ratios often produce surd values; comfort with irrationals reduces friction. Awaiting steward confirmation." });

  // --- Mathematics, CROSS-GRADE (9 -> 10) ---
  b.addEdge({ from: T(9, "math", "surds"), to: T(10, "math", "irrational"), kind: "hard", confirmed: true, rationale: "Class 10 irrationality proofs rest on Class 9 fluency with surds and rationalisation." });
  b.addEdge({ from: T(9, "math", "remfactor"), to: T(10, "math", "polyzeros"), kind: "hard", confirmed: true, rationale: "Finding zeros in Class 10 builds directly on the factor theorem mastered in Class 9." });

  // --- Physics, within Class 10 ---
  b.addEdge({ from: T(10, "phys", "reflection"), to: T(10, "phys", "mirrors"), kind: "hard", confirmed: true, rationale: "Image formation by mirrors is derived by applying the laws of reflection at the surface." });
  b.addEdge({ from: T(10, "phys", "refraction"), to: T(10, "phys", "lenses"), kind: "hard", confirmed: true, rationale: "Lens behaviour follows from refraction at curved surfaces; Snell's law must be understood first." });
  b.addEdge({ from: T(10, "phys", "mirrors"), to: T(10, "phys", "lenses"), kind: "soft", confirmed: true, rationale: "Ray-diagram and sign-convention skills from mirrors transfer to lens problems." });
  b.addEdge({ from: T(10, "phys", "ohm"), to: T(10, "phys", "resistors"), kind: "hard", confirmed: true, rationale: "Series and parallel equivalents are derived by applying Ohm's law across combinations." });

  // --- Physics, within Class 9 ---
  b.addEdge({ from: T(9, "phys", "motion"), to: T(9, "phys", "newton"), kind: "hard", confirmed: true, rationale: "Newton's laws explain the motion described kinematically first." });
  b.addEdge({ from: T(9, "phys", "newton"), to: T(9, "phys", "work"), kind: "soft", confirmed: true, rationale: "Work and energy are framed in terms of force, which Newton's laws establish." });

  // --- Physics, CROSS-GRADE (9 -> 10) ---
  b.addEdge({ from: T(9, "phys", "work"), to: T(10, "phys", "ohm"), kind: "soft", confirmed: false, rationale: "Proposed: the energy view from Class 9 supports interpreting electrical work and power. Awaiting steward confirmation." });

  // --- Chemistry, CROSS-GRADE (9 -> 10) ---
  b.addEdge({ from: T(9, "chem", "atoms"), to: T(10, "chem", "reactions"), kind: "hard", confirmed: true, rationale: "Balancing equations rests on the atom and mole concepts from Class 9." });
  b.addEdge({ from: T(10, "chem", "reactions"), to: T(10, "chem", "acidsbases"), kind: "soft", confirmed: true, rationale: "Neutralisation is a reaction type best understood after general reaction classification." });
  b.addEdge({ from: T(10, "chem", "acidsbases"), to: T(10, "chem", "salts"), kind: "hard", confirmed: true, rationale: "Salt formation is defined through acid-base neutralisation." });

  // --- Biology, CROSS-GRADE (9 -> 10) ---
  b.addEdge({ from: T(9, "bio", "cell"), to: T(10, "bio", "nutrition"), kind: "hard", confirmed: true, rationale: "Life processes are explained at the cellular level introduced in Class 9." });
  b.addEdge({ from: T(10, "bio", "nutrition"), to: T(10, "bio", "transport"), kind: "soft", confirmed: true, rationale: "Transport carries the products of nutrition and respiration through the organism." });
  b.addEdge({ from: T(10, "bio", "reproduction"), to: T(10, "bio", "heredity"), kind: "hard", confirmed: true, rationale: "Inheritance is studied as a consequence of sexual reproduction." });

  // --- English, CROSS-GRADE (9 -> 10) ---
  b.addEdge({ from: T(9, "eng", "reading"), to: T(10, "eng", "reading"), kind: "soft", confirmed: true, rationale: "Analytical reading in Class 10 extends Class 9 comprehension skills." });
  b.addEdge({ from: T(9, "eng", "grammar"), to: T(10, "eng", "grammar"), kind: "soft", confirmed: true, rationale: "Class 10 grammar transformations build on Class 9 tense and structure control." });

  // --- Social Science, within Class 10 ---
  b.addEdge({ from: T(10, "soc", "politics"), to: T(10, "soc", "economics"), kind: "soft", confirmed: true, rationale: "Economic policy is read against the power-sharing institutions studied first." });
  b.addEdge({ from: T(9, "soc", "democracy"), to: T(10, "soc", "politics"), kind: "hard", confirmed: true, rationale: "Power sharing and federalism extend the constitutional foundations from Class 9." });
}

wireEdges(national, nationalCode);
wireEdges(state, stateCode);

// ---------------------------------------------------------------------------
// Cross-board equivalences — resolve to REAL topic ids in the other board.
// Wired both directions so cross-board equivalence is genuinely exercised.
// ---------------------------------------------------------------------------

interface EquivPair {
  national: string; // topic handle in the national board
  state: string; // topic handle in the state board
  label: string;
  confidence: number;
}

const equivPairs: EquivPair[] = [
  { national: h(nationalCode, 10, "math", "euclid"), state: h(stateCode, 10, "math", "euclid"), label: "Euclidean algorithm for HCF (Class 10)", confidence: 0.96 },
  { national: h(nationalCode, 10, "math", "irrational"), state: h(stateCode, 10, "math", "irrational"), label: "Irrational number proofs (Class 10)", confidence: 0.94 },
  { national: h(nationalCode, 10, "phys", "ohm"), state: h(stateCode, 10, "phys", "ohm"), label: "Ohm's law and resistance (Class 10)", confidence: 0.97 },
  { national: h(nationalCode, 10, "phys", "lenses"), state: h(stateCode, 10, "phys", "lenses"), label: "Lenses and image formation (Class 10)", confidence: 0.9 },
  { national: h(nationalCode, 10, "chem", "acidsbases"), state: h(stateCode, 10, "chem", "acidsbases"), label: "Acids, bases, and the pH scale (Class 10)", confidence: 0.92 },
  { national: h(nationalCode, 10, "bio", "heredity"), state: h(stateCode, 10, "bio", "heredity"), label: "Heredity and inheritance (Class 10)", confidence: 0.88 },
  { national: h(nationalCode, 9, "math", "surds"), state: h(stateCode, 9, "math", "surds"), label: "Operations on surds (Class 9)", confidence: 0.91 },
];

for (const pair of equivPairs) {
  national.addEquivalence({
    handle: pair.national,
    toBoard: state,
    toHandle: pair.state,
    label: `${pair.label} — Example State Board`,
    confidence: pair.confidence,
  });
  state.addEquivalence({
    handle: pair.state,
    toBoard: national,
    toHandle: pair.national,
    label: `${pair.label} — Example National Board`,
    confidence: pair.confidence,
  });
}

// ---------------------------------------------------------------------------
// Exported snapshots.
// ---------------------------------------------------------------------------

/**
 * The canonical seed snapshot (Example National Board). A single valid
 * `OntologySnapshot`: grades 9 and 10, six subjects, a full topic graph,
 * within- and cross-grade prerequisite edges, and cross-board equivalences that
 * resolve to real topics in the state board.
 */
export const SEED_ONTOLOGY: OntologySnapshot = national.snapshot();

/** The second board (Example State Board) — the equivalence target. Also a valid snapshot. */
export const SEED_ONTOLOGY_STATE: OntologySnapshot = state.snapshot();

/** Both board snapshots, for cross-board projections and tests. */
export const SEED_ONTOLOGIES: readonly OntologySnapshot[] = [SEED_ONTOLOGY, SEED_ONTOLOGY_STATE];

/** Validate eagerly at module load so a malformed seed fails loudly, not silently. */
OntologySnapshot.parse(SEED_ONTOLOGY);
OntologySnapshot.parse(SEED_ONTOLOGY_STATE);

/**
 * The stable id map for the seed. Resolves readable handles to minted ids for
 * both boards, plus the board ids, so tests and projections can reference nodes
 * by constant without depending on UUID literals.
 */
export const SEED_ONTOLOGY_IDS = {
  boards: {
    national: SEED_ONTOLOGY.board.id,
    state: SEED_ONTOLOGY_STATE.board.id,
  },
  codes: {
    national: nationalCode,
    state: stateCode,
  },
  /** Resolve a topic handle to its id on the national board. */
  nationalTopic: (handle: string) => national.topicId(handle),
  /** Resolve a topic handle to its id on the state board. */
  stateTopic: (handle: string) => state.topicId(handle),
  /** Build a topic handle the same way the seed does. */
  handle: h,

  // -------------------------------------------------------------------------
  // Backward-compatible flat keys.
  //
  // The original narrow seed exposed flat constants (subjMath, tEuclid, …) that
  // existing web surfaces depend on. They resolve to the SAME conceptual nodes
  // on the canonical (national) board, so downstream code keeps working while
  // the graph is now far richer.
  // -------------------------------------------------------------------------
  subjMath: national.subjectId(national.gradeId(10), "Mathematics"),
  subjPhys: national.subjectId(national.gradeId(10), "Physics"),

  tEuclid: national.topicId(h(nationalCode, 10, "math", "euclid")),
  tFundThm: national.topicId(h(nationalCode, 10, "math", "fundthm")),
  tIrrational: national.topicId(h(nationalCode, 10, "math", "irrational")),
  tPolyDegreeZeros: national.topicId(h(nationalCode, 10, "math", "polyzeros")),
  tPolyCoeffRel: national.topicId(h(nationalCode, 10, "math", "polycoeff")),
  tTrigRatios: national.topicId(h(nationalCode, 10, "math", "trigratios")),
  tTrigIdentities: national.topicId(h(nationalCode, 10, "math", "trigidentities")),

  tReflectionLaws: national.topicId(h(nationalCode, 10, "phys", "reflection")),
  tSphericalMirrors: national.topicId(h(nationalCode, 10, "phys", "mirrors")),
  tRefractionLaws: national.topicId(h(nationalCode, 10, "phys", "refraction")),
  tLensesImages: national.topicId(h(nationalCode, 10, "phys", "lenses")),
  tOhmsLaw: national.topicId(h(nationalCode, 10, "phys", "ohm")),
  tResistorsSeriesParallel: national.topicId(h(nationalCode, 10, "phys", "resistors")),
} as const;
