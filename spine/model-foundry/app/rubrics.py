"""The gap taxonomy + pedagogy rubrics the Track-2 student distils against.

The closed set of LEARNING-GAP TYPES (mirrored from the event contract
``contracts/src/events/gaps.ts``) and the per-gap pedagogical RESPONSE rubric are
the curriculum the small edge student is taught. They are PII-free, deterministic
constants: the teacher conditions its distillation targets on them, curate uses
them to validate that a gap label is in-taxonomy, and eval scores the student's
gap classification against them.

Keeping the taxonomy here (not re-deriving it) means the foundry, the fabric, and
the contract never disagree about what a gap IS or how a tutor should respond to
it — collapsing ten distinct gaps into one "struggling" signal is exactly what
this taxonomy exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass

# The ten gap types as a closed, ordered tuple — mirrors GAP_TYPES in the
# contract (contracts/src/events/gaps.ts). Order is for display, not severity.
GAP_TYPES: tuple[str, ...] = (
    "prerequisite",
    "conceptual",
    "procedural",
    "application",
    "retention",
    "language",
    "accuracy",
    "speed",
    "confidence",
    "support-dependency",
)


@dataclass(frozen=True)
class GapRubric:
    """The pedagogy rubric for one gap type: what it IS and how to respond.

    ``response`` is the bounded instructional move a tutor (and therefore the
    distilled student) should take for this gap. PII-free, deterministic.
    """

    gap_type: str
    definition: str
    response: str


# Per-gap rubric, mirrored from GAP_TYPE_DOCS in the contract. The response is the
# label the pedagogy gate checks the student against.
GAP_RUBRICS: dict[str, GapRubric] = {
    "prerequisite": GapRubric(
        gap_type="prerequisite",
        definition="A required earlier concept is missing or weak; the current topic cannot stand on it.",
        response="route back to the prerequisite in the graph",
    ),
    "conceptual": GapRubric(
        gap_type="conceptual",
        definition="The underlying idea is misunderstood — the mental model is wrong, not just the execution.",
        response="re-explain and re-anchor the concept",
    ),
    "procedural": GapRubric(
        gap_type="procedural",
        definition="The concept is understood but the method/steps are not reliably executed.",
        response="guided practice on the procedure",
    ),
    "application": GapRubric(
        gap_type="application",
        definition="Knows the concept and procedure in isolation but cannot transfer it to a novel problem.",
        response="varied-context application practice",
    ),
    "retention": GapRubric(
        gap_type="retention",
        definition="Was demonstrated before but has decayed over time.",
        response="spaced retrieval and review",
    ),
    "language": GapRubric(
        gap_type="language",
        definition="The barrier is linguistic — comprehension of the question or terminology, not the concept.",
        response="hyperlocalized language support, not re-teaching the concept",
    ),
    "accuracy": GapRubric(
        gap_type="accuracy",
        definition="Method is right but execution is error-prone (slips, miscalculation).",
        response="precision drills and self-checking habits",
    ),
    "speed": GapRubric(
        gap_type="speed",
        definition="Correct and accurate but too slow for the context (timed work, fluency).",
        response="fluency building, not new instruction",
    ),
    "confidence": GapRubric(
        gap_type="confidence",
        definition="Capable when supported or unobserved but falters under self-reliance or pressure.",
        response="scaffolded autonomy and low-stakes wins",
    ),
    "support-dependency": GapRubric(
        gap_type="support-dependency",
        definition="Performs well only with assistance and cannot yet do it independently.",
        response="deliberate fading of support",
    ),
}


def is_gap_type(value: str) -> bool:
    """True if ``value`` is a known, in-taxonomy gap type."""
    return value in GAP_RUBRICS


def expected_response(gap_type: str) -> str | None:
    """The rubric-correct instructional response for a gap type (or None)."""
    rub = GAP_RUBRICS.get(gap_type)
    return rub.response if rub else None


def taxonomy_prompt_block() -> str:
    """A compact, PII-free description of the taxonomy for a teacher prompt.

    Deterministic — the same block every time so a distillation run is
    reproducible and the teacher is conditioned on the exact taxonomy the
    student is scored against.
    """
    lines = ["The closed gap taxonomy and the correct tutor response for each:"]
    for gt in GAP_TYPES:
        rub = GAP_RUBRICS[gt]
        lines.append(f"- {gt}: {rub.definition} Response: {rub.response}.")
    return "\n".join(lines)
