"""A Python view of the Slice 1 seed ontology, mirroring the contract.

The canonical seed is ``contracts/src/ontology/seed.ts`` — Class 10, two
subjects (Mathematics, Physics), on a NEUTRAL example board ("Example State
Board", NOT a real board: no board lock-in). The behavioural pipeline is Python,
so this builds the same flat snapshot with the SAME stable, deterministic ids,
letting tests and projections reference nodes by constant exactly as the TS side
does.

This is seed DATA, not a board assumption: the board is a labelled node. The
ingest / steward / equivalence code never imports a board literal from here for
behaviour — they operate on whatever snapshot they are given.

Import-safe: pure construction, no I/O, no env read.
"""

from __future__ import annotations

from ._ontology import (
    Board,
    Chapter,
    Competency,
    CrossBoardEquivalence,
    Edge,
    Grade,
    NodeKind,
    OntologySnapshot,
    Outcome,
    PrerequisiteKind,
    Subject,
    Topic,
    Unit,
)

# Stable ids mirroring contracts/src/ontology/seed.ts (same constants).
ID = {
    "board": "b0a11000-0000-4000-8000-000000000001",
    "grade10": "61ade100-0000-4000-8000-000000000010",
    "subjMath": "5ec70000-0000-4000-8000-0000000000a1",
    "unitRealNumbers": "00170000-0000-4000-8000-000000000101",
    "unitPolynomials": "00170000-0000-4000-8000-000000000102",
    "unitTrig": "00170000-0000-4000-8000-000000000103",
    "chRealNumbers": "c0a70000-0000-4000-8000-000000000201",
    "chPolynomials": "c0a70000-0000-4000-8000-000000000202",
    "chTrig": "c0a70000-0000-4000-8000-000000000203",
    "tEuclid": "70910000-0000-4000-8000-000000000301",
    "tFundThm": "70910000-0000-4000-8000-000000000302",
    "tIrrational": "70910000-0000-4000-8000-000000000303",
    "tPolyDegreeZeros": "70910000-0000-4000-8000-000000000304",
    "tPolyCoeffRel": "70910000-0000-4000-8000-000000000305",
    "tTrigRatios": "70910000-0000-4000-8000-000000000306",
    "tTrigIdentities": "70910000-0000-4000-8000-000000000307",
    "subjPhys": "5ec70000-0000-4000-8000-0000000000b1",
    "unitLight": "00170000-0000-4000-8000-000000000111",
    "unitElectricity": "00170000-0000-4000-8000-000000000112",
    "chReflection": "c0a70000-0000-4000-8000-000000000211",
    "chRefraction": "c0a70000-0000-4000-8000-000000000212",
    "chCurrent": "c0a70000-0000-4000-8000-000000000213",
    "tReflectionLaws": "70910000-0000-4000-8000-000000000311",
    "tSphericalMirrors": "70910000-0000-4000-8000-000000000312",
    "tRefractionLaws": "70910000-0000-4000-8000-000000000313",
    "tLensesImages": "70910000-0000-4000-8000-000000000314",
    "tOhmsLaw": "70910000-0000-4000-8000-000000000315",
    "tResistorsSeriesParallel": "70910000-0000-4000-8000-000000000316",
    "compNumberReasoning": "c0590000-0000-4000-8000-000000000401",
    "compAlgebraicReasoning": "c0590000-0000-4000-8000-000000000402",
    "compGeomOptics": "c0590000-0000-4000-8000-000000000403",
    "compCircuitReasoning": "c0590000-0000-4000-8000-000000000404",
}


def _oid(suffix: int) -> str:
    return f"0c700000-0000-4000-8000-{suffix:012d}"


# Outcome ids in declaration order, matching the TS nextOutcome() sequence.
O = {
    "euclid": _oid(1),
    "fundThm": _oid(2),
    "irrational": _oid(3),
    "polyZeros": _oid(4),
    "polyCoeff": _oid(5),
    "trigRatios": _oid(6),
    "trigIdentities": _oid(7),
    "reflectionLaws": _oid(8),
    "sphericalMirrors": _oid(9),
    "refractionLaws": _oid(10),
    "lensesImages": _oid(11),
    "ohmsLaw": _oid(12),
    "resistorsSP": _oid(13),
}


def _eid(n: int) -> str:
    return f"ed9e0000-0000-4000-8000-{n:012d}"


def build_seed_snapshot() -> OntologySnapshot:
    """Build the Slice 1 seed snapshot (board-agnostic example board)."""
    return OntologySnapshot(
        board=Board(
            id=ID["board"],
            code="example-state-board",
            name="Example State Board",
            region="Example Region",
        ),
        grades=[Grade(id=ID["grade10"], board_id=ID["board"], level=10, name="Class 10")],
        subjects=[
            Subject(id=ID["subjMath"], grade_id=ID["grade10"], name="Mathematics"),
            Subject(id=ID["subjPhys"], grade_id=ID["grade10"], name="Physics"),
        ],
        units=[
            Unit(id=ID["unitRealNumbers"], subject_id=ID["subjMath"], name="Real Numbers", sequence=0),
            Unit(id=ID["unitPolynomials"], subject_id=ID["subjMath"], name="Polynomials", sequence=1),
            Unit(id=ID["unitTrig"], subject_id=ID["subjMath"], name="Trigonometry", sequence=2),
            Unit(id=ID["unitLight"], subject_id=ID["subjPhys"], name="Light — Reflection and Refraction", sequence=0),
            Unit(id=ID["unitElectricity"], subject_id=ID["subjPhys"], name="Electricity", sequence=1),
        ],
        chapters=[
            Chapter(id=ID["chRealNumbers"], unit_id=ID["unitRealNumbers"], name="Real Numbers", sequence=0),
            Chapter(id=ID["chPolynomials"], unit_id=ID["unitPolynomials"], name="Polynomials", sequence=0),
            Chapter(id=ID["chTrig"], unit_id=ID["unitTrig"], name="Introduction to Trigonometry", sequence=0),
            Chapter(id=ID["chReflection"], unit_id=ID["unitLight"], name="Reflection of Light", sequence=0),
            Chapter(id=ID["chRefraction"], unit_id=ID["unitLight"], name="Refraction of Light", sequence=1),
            Chapter(id=ID["chCurrent"], unit_id=ID["unitElectricity"], name="Electric Current and Circuits", sequence=0),
        ],
        topics=[
            Topic(id=ID["tEuclid"], chapter_id=ID["chRealNumbers"], name="Euclid's Division Lemma and HCF", sequence=0),
            Topic(id=ID["tFundThm"], chapter_id=ID["chRealNumbers"], name="Fundamental Theorem of Arithmetic", sequence=1),
            Topic(id=ID["tIrrational"], chapter_id=ID["chRealNumbers"], name="Irrational Numbers and Proofs", sequence=2),
            Topic(id=ID["tPolyDegreeZeros"], chapter_id=ID["chPolynomials"], name="Degree and Zeros of a Polynomial", sequence=0),
            Topic(id=ID["tPolyCoeffRel"], chapter_id=ID["chPolynomials"], name="Relationship Between Zeros and Coefficients", sequence=1),
            Topic(id=ID["tTrigRatios"], chapter_id=ID["chTrig"], name="Trigonometric Ratios of an Acute Angle", sequence=0),
            Topic(id=ID["tTrigIdentities"], chapter_id=ID["chTrig"], name="Trigonometric Identities", sequence=1),
            Topic(id=ID["tReflectionLaws"], chapter_id=ID["chReflection"], name="Laws of Reflection", sequence=0),
            Topic(id=ID["tSphericalMirrors"], chapter_id=ID["chReflection"], name="Spherical Mirrors and Image Formation", sequence=1),
            Topic(id=ID["tRefractionLaws"], chapter_id=ID["chRefraction"], name="Laws of Refraction and Refractive Index", sequence=0),
            Topic(id=ID["tLensesImages"], chapter_id=ID["chRefraction"], name="Lenses and Image Formation", sequence=1),
            Topic(id=ID["tOhmsLaw"], chapter_id=ID["chCurrent"], name="Ohm's Law and Resistance", sequence=0),
            Topic(id=ID["tResistorsSeriesParallel"], chapter_id=ID["chCurrent"], name="Resistors in Series and Parallel", sequence=1),
        ],
        outcomes=[
            Outcome(id=O["euclid"], topic_id=ID["tEuclid"], statement="Applies Euclid's division lemma to compute the HCF of two positive integers."),
            Outcome(id=O["fundThm"], topic_id=ID["tFundThm"], statement="Expresses a composite number as a product of primes and uses it to find HCF and LCM."),
            Outcome(id=O["irrational"], topic_id=ID["tIrrational"], statement="Proves that a given number such as the square root of 2 is irrational by contradiction."),
            Outcome(id=O["polyZeros"], topic_id=ID["tPolyDegreeZeros"], statement="Identifies the degree of a polynomial and finds its zeros graphically and algebraically."),
            Outcome(id=O["polyCoeff"], topic_id=ID["tPolyCoeffRel"], statement="Verifies the relationship between the zeros and coefficients of a quadratic polynomial."),
            Outcome(id=O["trigRatios"], topic_id=ID["tTrigRatios"], statement="Computes the six trigonometric ratios of an acute angle from a right triangle."),
            Outcome(id=O["trigIdentities"], topic_id=ID["tTrigIdentities"], statement="Proves and applies the standard trigonometric identities to simplify expressions."),
            Outcome(id=O["reflectionLaws"], topic_id=ID["tReflectionLaws"], statement="States the laws of reflection and applies them to plane surfaces."),
            Outcome(id=O["sphericalMirrors"], topic_id=ID["tSphericalMirrors"], statement="Predicts the nature, position, and size of images formed by concave and convex mirrors."),
            Outcome(id=O["refractionLaws"], topic_id=ID["tRefractionLaws"], statement="States the laws of refraction and calculates refractive index using Snell's law."),
            Outcome(id=O["lensesImages"], topic_id=ID["tLensesImages"], statement="Uses the lens formula and ray diagrams to locate images formed by convex and concave lenses."),
            Outcome(id=O["ohmsLaw"], topic_id=ID["tOhmsLaw"], statement="Applies Ohm's law to relate potential difference, current, and resistance in a conductor."),
            Outcome(id=O["resistorsSP"], topic_id=ID["tResistorsSeriesParallel"], statement="Computes equivalent resistance for resistors combined in series and in parallel."),
        ],
        competencies=[
            Competency(id=ID["compNumberReasoning"], subject_id=ID["subjMath"], name="Number reasoning and divisibility",
                       statement="Reasons about integer structure, factorisation, and number classification.",
                       outcome_ids=(O["euclid"], O["fundThm"], O["irrational"])),
            Competency(id=ID["compAlgebraicReasoning"], subject_id=ID["subjMath"], name="Algebraic and trigonometric reasoning",
                       statement="Manipulates polynomials and trigonometric relationships to solve problems.",
                       outcome_ids=(O["polyZeros"], O["polyCoeff"], O["trigRatios"], O["trigIdentities"])),
            Competency(id=ID["compGeomOptics"], subject_id=ID["subjPhys"], name="Geometric optics",
                       statement="Predicts image formation by mirrors and lenses from reflection and refraction principles.",
                       outcome_ids=(O["reflectionLaws"], O["sphericalMirrors"], O["refractionLaws"], O["lensesImages"])),
            Competency(id=ID["compCircuitReasoning"], subject_id=ID["subjPhys"], name="Circuit reasoning",
                       statement="Analyses simple resistive circuits using Ohm's law and combination rules.",
                       outcome_ids=(O["ohmsLaw"], O["resistorsSP"])),
        ],
        edges=[
            Edge(id=_eid(1), from_topic_id=ID["tEuclid"], to_topic_id=ID["tFundThm"], kind=PrerequisiteKind.SOFT, confirmed=True,
                 rationale="Comfort with HCF via division supports prime-factorisation reasoning for HCF and LCM."),
            Edge(id=_eid(2), from_topic_id=ID["tFundThm"], to_topic_id=ID["tIrrational"], kind=PrerequisiteKind.HARD, confirmed=True,
                 rationale="Irrationality proofs rely on unique prime factorisation from the fundamental theorem."),
            Edge(id=_eid(3), from_topic_id=ID["tPolyDegreeZeros"], to_topic_id=ID["tPolyCoeffRel"], kind=PrerequisiteKind.HARD, confirmed=True,
                 rationale="The zeros-coefficient relationship presupposes the learner can identify a polynomial's zeros."),
            Edge(id=_eid(4), from_topic_id=ID["tTrigRatios"], to_topic_id=ID["tTrigIdentities"], kind=PrerequisiteKind.HARD, confirmed=True,
                 rationale="Identities are stated and proved in terms of the basic ratios, which must be secure first."),
            # The one PROPOSED, unconfirmed edge in the seed — awaiting steward.
            Edge(id=_eid(5), from_topic_id=ID["tIrrational"], to_topic_id=ID["tTrigRatios"], kind=PrerequisiteKind.SOFT, confirmed=False,
                 rationale="Proposed: trig ratios often produce surd values; comfort with irrationals reduces friction. Awaiting steward confirmation."),
            Edge(id=_eid(6), from_topic_id=ID["tReflectionLaws"], to_topic_id=ID["tSphericalMirrors"], kind=PrerequisiteKind.HARD, confirmed=True,
                 rationale="Image formation by mirrors is derived by applying the laws of reflection at the surface."),
            Edge(id=_eid(7), from_topic_id=ID["tRefractionLaws"], to_topic_id=ID["tLensesImages"], kind=PrerequisiteKind.HARD, confirmed=True,
                 rationale="Lens behaviour follows from refraction at curved surfaces; Snell's law must be understood first."),
            Edge(id=_eid(8), from_topic_id=ID["tSphericalMirrors"], to_topic_id=ID["tLensesImages"], kind=PrerequisiteKind.SOFT, confirmed=True,
                 rationale="Ray-diagram and sign-convention skills from mirrors transfer to lens problems."),
            Edge(id=_eid(9), from_topic_id=ID["tOhmsLaw"], to_topic_id=ID["tResistorsSeriesParallel"], kind=PrerequisiteKind.HARD, confirmed=True,
                 rationale="Series and parallel equivalents are derived by applying Ohm's law across combinations."),
        ],
        equivalences=[
            CrossBoardEquivalence(
                id="e9010000-0000-4000-8000-000000000001",
                node_id=ID["tEuclid"], node_kind=NodeKind.TOPIC,
                equivalent_board_code="another-example-board",
                equivalent_label="Euclidean algorithm for HCF (Class 10, Number Systems)",
                confidence=0.95,
            ),
            CrossBoardEquivalence(
                id="e9010000-0000-4000-8000-000000000002",
                node_id=ID["tOhmsLaw"], node_kind=NodeKind.TOPIC,
                equivalent_board_code="another-example-board",
                equivalent_label="Ohm's law and resistance (Class 10, Current Electricity)",
                confidence=0.97,
            ),
        ],
    )


SEED_ONTOLOGY_IDS = {**ID, "outcomes": O}
