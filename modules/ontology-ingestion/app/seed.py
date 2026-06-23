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
    CompetitiveExamMapping,
    CrossBoardEquivalence,
    CurriculumVersion,
    Edge,
    Grade,
    LocalOverlay,
    NodeKind,
    OntologySnapshot,
    Outcome,
    PrerequisiteKind,
    Question,
    Resource,
    Skill,
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


# ---------------------------------------------------------------------------
# Richer OFFLINE seed expansion (no provider, no network)
# ---------------------------------------------------------------------------
#
# The canonical seed above mirrors the contract EXACTLY (count-locked by tests).
# This expansion is a SEPARATE, additive offline path: it grows the same neutral
# example board with a second grade (Class 9 Mathematics) and a third Class 10
# subject (Chemistry), each with units → chapters → topics → outcomes,
# competencies, and prerequisite edges — some CONFIRMED (curriculum-fact, e.g.
# nomenclature before equations) and some PROPOSED (unconfirmed, awaiting a
# steward). It is the deterministic stand-in the pipeline uses to demonstrate a
# substantially larger ontology with NO board lock-in (the board stays a label).

# Stable ids for the expansion nodes (distinct id bands from the base seed).
XID = {
    # Class 9 (Mathematics) — a second grade on the SAME board.
    "grade9": "61ade100-0000-4000-8000-000000000009",
    "subjMath9": "5ec70000-0000-4000-8000-0000000000c1",
    "unitNumber9": "00170000-0000-4000-8000-000000000121",
    "unitAlgebra9": "00170000-0000-4000-8000-000000000122",
    "chNumber9": "c0a70000-0000-4000-8000-000000000221",
    "chPolynomials9": "c0a70000-0000-4000-8000-000000000222",
    "tRealLine9": "70910000-0000-4000-8000-000000000321",
    "tSurds9": "70910000-0000-4000-8000-000000000322",
    "tPolyIntro9": "70910000-0000-4000-8000-000000000323",
    "tFactorThm9": "70910000-0000-4000-8000-000000000324",
    "compNumber9": "c0590000-0000-4000-8000-000000000421",
    "compAlgebra9": "c0590000-0000-4000-8000-000000000422",
    # Class 10 Chemistry — a third subject under the EXISTING grade 10.
    "subjChem": "5ec70000-0000-4000-8000-0000000000d1",
    "unitReactions": "00170000-0000-4000-8000-000000000131",
    "unitAcidsBases": "00170000-0000-4000-8000-000000000132",
    "chReactions": "c0a70000-0000-4000-8000-000000000231",
    "chAcidsBases": "c0a70000-0000-4000-8000-000000000232",
    "tTypesReactions": "70910000-0000-4000-8000-000000000331",
    "tBalancing": "70910000-0000-4000-8000-000000000332",
    "tAcidsBasesProps": "70910000-0000-4000-8000-000000000333",
    "tpHScale": "70910000-0000-4000-8000-000000000334",
    "compReactions": "c0590000-0000-4000-8000-000000000431",
    "compAcidsBases": "c0590000-0000-4000-8000-000000000432",
}


def _xoid(suffix: int) -> str:
    return f"0c700000-0000-4000-8000-{(900000 + suffix):012d}"


XO = {
    "realLine9": _xoid(1),
    "surds9": _xoid(2),
    "polyIntro9": _xoid(3),
    "factorThm9": _xoid(4),
    "typesReactions": _xoid(5),
    "balancing": _xoid(6),
    "acidsBasesProps": _xoid(7),
    "pHScale": _xoid(8),
}


def _xeid(n: int) -> str:
    return f"ed9e0000-0000-4000-8000-{(900000 + n):012d}"


# Stable ids for the DEEP nodes below competency (skill → question → resource)
# and for the competitive-exam mappings, local overlays, and version stamps.
# Distinct id bands so nothing collides with the base or expansion nodes.
def _skid(n: int) -> str:
    return f"5c111000-0000-4000-8000-{n:012d}"


def _quid(n: int) -> str:
    return f"90e51000-0000-4000-8000-{n:012d}"


def _reid(n: int) -> str:
    return f"4e500000-0000-4000-8000-{n:012d}"


def _xmid(n: int) -> str:
    return f"ea11000a-0000-4000-8000-{n:012d}"


def _xovid(n: int) -> str:
    return f"01e41000-0000-4000-8000-{n:012d}"


def _xverid(n: int) -> str:
    return f"7e151000-0000-4000-8000-{n:012d}"


DEEP_ID = {
    # Skills hang off Class 10 Maths competencies from the base seed.
    "skHcf": _skid(1),
    "skPrimeFact": _skid(2),
    "skFactorQuadratic": _skid(3),
    # Questions assess skills.
    "qHcf": _quid(1),
    "qPrimeFact": _quid(2),
    "qFactorQuadratic": _quid(3),
    # Resources tag onto topics / skills / questions.
    "resEuclidNote": _reid(1),
    "resPolyVideo": _reid(2),
    "resHcfWorksheet": _reid(3),
}


def build_expanded_seed_snapshot() -> OntologySnapshot:
    """Build a substantially larger OFFLINE seed on the same neutral board.

    Additive over :func:`build_seed_snapshot`: keeps every base node and edge and
    appends a second grade and a third subject with their topics, outcomes,
    competencies, and edges. Deterministic, offline, board-agnostic. Proposed
    edges ship UNCONFIRMED; curriculum-fact edges ship confirmed.
    """
    snap = build_seed_snapshot()

    snap.grades.append(Grade(id=XID["grade9"], board_id=ID["board"], level=9, name="Class 9"))

    snap.subjects.extend([
        Subject(id=XID["subjMath9"], grade_id=XID["grade9"], name="Mathematics"),
        Subject(id=XID["subjChem"], grade_id=ID["grade10"], name="Chemistry"),
    ])

    snap.units.extend([
        Unit(id=XID["unitNumber9"], subject_id=XID["subjMath9"], name="Number Systems", sequence=0),
        Unit(id=XID["unitAlgebra9"], subject_id=XID["subjMath9"], name="Polynomials", sequence=1),
        Unit(id=XID["unitReactions"], subject_id=XID["subjChem"], name="Chemical Reactions and Equations", sequence=0),
        Unit(id=XID["unitAcidsBases"], subject_id=XID["subjChem"], name="Acids, Bases and Salts", sequence=1),
    ])

    snap.chapters.extend([
        Chapter(id=XID["chNumber9"], unit_id=XID["unitNumber9"], name="Number Systems", sequence=0),
        Chapter(id=XID["chPolynomials9"], unit_id=XID["unitAlgebra9"], name="Polynomials", sequence=0),
        Chapter(id=XID["chReactions"], unit_id=XID["unitReactions"], name="Chemical Reactions and Equations", sequence=0),
        Chapter(id=XID["chAcidsBases"], unit_id=XID["unitAcidsBases"], name="Acids, Bases and Salts", sequence=0),
    ])

    snap.topics.extend([
        Topic(id=XID["tRealLine9"], chapter_id=XID["chNumber9"], name="Representing Real Numbers on the Number Line", sequence=0),
        Topic(id=XID["tSurds9"], chapter_id=XID["chNumber9"], name="Operations on Surds and Rationalisation", sequence=1),
        Topic(id=XID["tPolyIntro9"], chapter_id=XID["chPolynomials9"], name="Polynomials in One Variable", sequence=0),
        Topic(id=XID["tFactorThm9"], chapter_id=XID["chPolynomials9"], name="Remainder and Factor Theorems", sequence=1),
        Topic(id=XID["tTypesReactions"], chapter_id=XID["chReactions"], name="Types of Chemical Reactions", sequence=0),
        Topic(id=XID["tBalancing"], chapter_id=XID["chReactions"], name="Writing and Balancing Chemical Equations", sequence=1),
        Topic(id=XID["tAcidsBasesProps"], chapter_id=XID["chAcidsBases"], name="Properties of Acids and Bases", sequence=0),
        Topic(id=XID["tpHScale"], chapter_id=XID["chAcidsBases"], name="The pH Scale and Its Importance", sequence=1),
    ])

    snap.outcomes.extend([
        Outcome(id=XO["realLine9"], topic_id=XID["tRealLine9"], statement="Represents rational and irrational numbers on the number line by successive magnification."),
        Outcome(id=XO["surds9"], topic_id=XID["tSurds9"], statement="Performs operations on surds and rationalises the denominator of an expression."),
        Outcome(id=XO["polyIntro9"], topic_id=XID["tPolyIntro9"], statement="Identifies polynomials in one variable and classifies them by degree."),
        Outcome(id=XO["factorThm9"], topic_id=XID["tFactorThm9"], statement="Applies the remainder and factor theorems to factorise polynomials."),
        Outcome(id=XO["typesReactions"], topic_id=XID["tTypesReactions"], statement="Classifies a reaction as combination, decomposition, displacement, or double displacement."),
        Outcome(id=XO["balancing"], topic_id=XID["tBalancing"], statement="Writes a balanced chemical equation for a described reaction, conserving mass."),
        Outcome(id=XO["acidsBasesProps"], topic_id=XID["tAcidsBasesProps"], statement="Distinguishes acids and bases by their chemical properties and indicator response."),
        Outcome(id=XO["pHScale"], topic_id=XID["tpHScale"], statement="Relates pH to acidic, neutral, and basic solutions and explains its everyday importance."),
    ])

    snap.competencies.extend([
        Competency(id=XID["compNumber9"], subject_id=XID["subjMath9"], name="Real-number fluency",
                   statement="Reasons about the real number line and manipulates surds.",
                   outcome_ids=(XO["realLine9"], XO["surds9"])),
        Competency(id=XID["compAlgebra9"], subject_id=XID["subjMath9"], name="Polynomial foundations",
                   statement="Classifies polynomials and factorises them using core theorems.",
                   outcome_ids=(XO["polyIntro9"], XO["factorThm9"])),
        Competency(id=XID["compReactions"], subject_id=XID["subjChem"], name="Reaction reasoning",
                   statement="Classifies and balances chemical reactions conserving mass.",
                   outcome_ids=(XO["typesReactions"], XO["balancing"])),
        Competency(id=XID["compAcidsBases"], subject_id=XID["subjChem"], name="Acid-base reasoning",
                   statement="Characterises acids and bases and interprets the pH scale.",
                   outcome_ids=(XO["acidsBasesProps"], XO["pHScale"])),
    ])

    snap.edges.extend([
        # Curriculum-fact (confirmed) edges within the expansion.
        Edge(id=_xeid(1), from_topic_id=XID["tRealLine9"], to_topic_id=XID["tSurds9"], kind=PrerequisiteKind.SOFT, confirmed=True,
             rationale="Locating reals precedes manipulating surd expressions over them."),
        Edge(id=_xeid(2), from_topic_id=XID["tPolyIntro9"], to_topic_id=XID["tFactorThm9"], kind=PrerequisiteKind.HARD, confirmed=True,
             rationale="The factor theorem is stated for polynomials introduced and classified first."),
        Edge(id=_xeid(3), from_topic_id=XID["tTypesReactions"], to_topic_id=XID["tBalancing"], kind=PrerequisiteKind.SOFT, confirmed=True,
             rationale="Recognising reaction types supports writing the correct equation to balance."),
        Edge(id=_xeid(4), from_topic_id=XID["tAcidsBasesProps"], to_topic_id=XID["tpHScale"], kind=PrerequisiteKind.HARD, confirmed=True,
             rationale="The pH scale quantifies the acidic/basic character established by properties first."),
        # PROPOSED, unconfirmed cross-grade edge — awaiting a steward.
        Edge(id=_xeid(5), from_topic_id=XID["tFactorThm9"], to_topic_id=ID["tPolyDegreeZeros"], kind=PrerequisiteKind.SOFT, confirmed=False,
             rationale="Proposed: Class 9 factorisation likely eases Class 10 work on zeros of polynomials. Awaiting steward confirmation."),
    ])

    # -- DEEP nodes below competency: skill → question → resource ----------
    # The doc's full chain ends below competency. Skills operationalise a
    # competency; questions assess a skill (and an outcome); resources tag onto
    # the graph. All neutral, offline, board-agnostic, PII-free.
    snap.skills.extend([
        Skill(id=DEEP_ID["skHcf"], competency_id=ID["compNumberReasoning"],
              name="Compute HCF by Euclid's lemma",
              statement="Carries out Euclid's division algorithm to find the HCF of two integers.",
              outcome_ids=(O["euclid"],)),
        Skill(id=DEEP_ID["skPrimeFact"], competency_id=ID["compNumberReasoning"],
              name="Prime-factorise a composite number",
              statement="Expresses a composite number as a product of primes and uses it for HCF/LCM.",
              outcome_ids=(O["fundThm"],)),
        Skill(id=DEEP_ID["skFactorQuadratic"], competency_id=ID["compAlgebraicReasoning"],
              name="Factorise a quadratic polynomial",
              statement="Factorises a quadratic and reads off its zeros.",
              outcome_ids=(O["polyZeros"], O["polyCoeff"])),
    ])

    snap.questions.extend([
        Question(id=DEEP_ID["qHcf"], skill_id=DEEP_ID["skHcf"], outcome_id=O["euclid"],
                 stem="Find the HCF of 1296 and 2520 using Euclid's division lemma.",
                 difficulty="easy"),
        Question(id=DEEP_ID["qPrimeFact"], skill_id=DEEP_ID["skPrimeFact"], outcome_id=O["fundThm"],
                 stem="Express 5005 as a product of its prime factors.",
                 difficulty="medium"),
        Question(id=DEEP_ID["qFactorQuadratic"], skill_id=DEEP_ID["skFactorQuadratic"], outcome_id=O["polyZeros"],
                 stem="Factorise x^2 - 7x + 12 and state its zeros.",
                 difficulty="medium"),
    ])

    snap.resources.extend([
        Resource(id=DEEP_ID["resEuclidNote"], target_id=ID["tEuclid"], target_kind=NodeKind.TOPIC,
                 title="Euclid's division lemma — worked notes",
                 resource_ref="content-store://example/euclid-notes", media_type="note"),
        Resource(id=DEEP_ID["resPolyVideo"], target_id=ID["tPolyDegreeZeros"], target_kind=NodeKind.TOPIC,
                 title="Zeros of a polynomial — explainer video",
                 resource_ref="content-store://example/poly-zeros-video", media_type="video"),
        Resource(id=DEEP_ID["resHcfWorksheet"], target_id=DEEP_ID["skHcf"], target_kind=NodeKind.SKILL,
                 title="HCF practice worksheet",
                 resource_ref="content-store://example/hcf-worksheet", media_type="worksheet"),
    ])

    # -- competitive-exam mappings (a second frame over the same graph) -----
    # The exam is a CODE label; one confirmed (curriculum-fact) and one proposed.
    snap.exam_mappings.extend([
        CompetitiveExamMapping(
            id=_xmid(1), node_id=O["euclid"], node_kind=NodeKind.OUTCOME,
            exam_code="example-entrance-exam",
            syllabus_ref="number-systems/divisibility", weight=0.8,
            confidence=0.92, confirmed=True),
        CompetitiveExamMapping(
            id=_xmid(2), node_id=O["polyZeros"], node_kind=NodeKind.OUTCOME,
            exam_code="example-scholarship-exam",
            syllabus_ref="algebra/polynomials", weight=0.6,
            confidence=0.55, confirmed=False),  # below gate, awaiting steward.
    ])

    # -- school-defined local overlays (projection, never base mutation) ----
    snap.overlays.extend([
        LocalOverlay(
            id=_xovid(1), scope_ref="tenant-ref-0001", node_id=ID["tEuclid"],
            node_kind=NodeKind.TOPIC, overlay_kind="alias",
            value="HCF using Euclid's method"),
        LocalOverlay(
            id=_xovid(2), scope_ref="tenant-ref-0001", node_id=ID["tTrigIdentities"],
            node_kind=NodeKind.TOPIC, overlay_kind="emphasis",
            value="high"),
    ])

    # -- curriculum versioning (append-only revision stamps) ---------------
    snap.versions.extend([
        CurriculumVersion(
            id=_xverid(1), scope_id=ID["subjMath"], scope_kind=NodeKind.SUBJECT,
            version="2023.1", effective_from="2023-04-01",
            note="Initial mapped revision of Class 10 Mathematics."),
        CurriculumVersion(
            id=_xverid(2), scope_id=ID["subjMath"], scope_kind=NodeKind.SUBJECT,
            version="2024.1", effective_from="2024-04-01",
            note="Sequencing refresh; supersedes 2023.1.",
            supersedes_id=_xverid(1)),
    ])

    return snap


EXPANDED_SEED_IDS = {**XID, **DEEP_ID, "outcomes": XO}
