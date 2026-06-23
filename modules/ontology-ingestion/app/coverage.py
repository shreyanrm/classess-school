"""Learning-outcome coverage tracking + curriculum versioning (A2, Ring 1).

The ontology steward keeps the graph clean and CURRENT; two of its jobs are:

  - LEARNING-OUTCOME COVERAGE. For a curriculum scope, which outcomes are
    backed by assessable content (a question, through a skill) and which are
    uncovered? Coverage is computed structurally from the graph — outcome →
    skill → question — so a gap surfaces the moment an outcome has no question
    that reaches it. Pure read over the snapshot; carries NO PII, no behavioural
    data (this is curriculum structure, never a learner's mastery).
  - CURRICULUM VERSIONING. Curriculum is versioned: a scope (subject/grade) may
    carry several :class:`CurriculumVersion` stamps. This module selects the
    version effective at a date and exposes the supersession chain, so routing
    and coverage can pin to a version. Append-only by convention — a revision is
    a new record, never an edit.

Import-safe: pure logic over the in-memory snapshot. No I/O, no provider, no env
read at import.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ._ontology import CurriculumVersion, NodeKind, OntologySnapshot


@dataclass(frozen=True)
class OutcomeCoverage:
    """Whether one learning outcome is reachable from assessable content.

    ``covered`` is True iff at least one question reaches the outcome (directly
    via the question's ``outcome_id``, or through a skill that lists the
    outcome). ``skill_ids`` / ``question_ids`` are the evidence — explainability.
    """

    outcome_id: str
    covered: bool
    skill_ids: tuple[str, ...] = ()
    question_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompetencyCoverage:
    """How fully one competency is backed by assessable content.

    Rolls the per-outcome coverage up to the competency the outcomes serve.
    ``status`` is ``"full"`` (every listed outcome covered), ``"partial"`` (some),
    or ``"none"`` (no listed outcome reachable from a question). ``covered_ids`` /
    ``uncovered_ids`` are the evidence — explainability for the colour-coded view.
    Pure structure; no behavioural data, no PII.
    """

    competency_id: str
    status: str  # "full" | "partial" | "none"
    covered_ids: tuple[str, ...] = ()
    uncovered_ids: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return len(self.covered_ids) + len(self.uncovered_ids)

    @property
    def coverage_ratio(self) -> float:
        return (len(self.covered_ids) / self.total) if self.total else 0.0


@dataclass
class CoverageReport:
    """Coverage across a set of outcomes — the colour-coded view's data."""

    items: list[OutcomeCoverage] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def covered(self) -> list[OutcomeCoverage]:
        return [i for i in self.items if i.covered]

    @property
    def uncovered(self) -> list[OutcomeCoverage]:
        return [i for i in self.items if not i.covered]

    @property
    def coverage_ratio(self) -> float:
        """Fraction of outcomes covered, in [0, 1]; 0.0 for an empty scope."""
        return (len(self.covered) / self.total) if self.total else 0.0


def _subject_outcome_ids(snapshot: OntologySnapshot, subject_id: str) -> list[str]:
    """All outcome ids under a subject, walking subject → unit → … → outcome.
    Deterministic order (declaration order on the snapshot tables)."""
    unit_ids = {u.id for u in snapshot.units if u.subject_id == subject_id}
    chapter_ids = {c.id for c in snapshot.chapters if c.unit_id in unit_ids}
    topic_ids = {t.id for t in snapshot.topics if t.chapter_id in chapter_ids}
    return [o.id for o in snapshot.outcomes if o.topic_id in topic_ids]


def outcome_coverage(
    snapshot: OntologySnapshot, *, subject_id: str | None = None
) -> CoverageReport:
    """Compute learning-outcome coverage from the graph.

    An outcome is covered when a question reaches it — either a question whose
    ``outcome_id`` is the outcome, or a question on a skill that lists the
    outcome in ``outcome_ids``. Restrict to ``subject_id`` when given; otherwise
    report every outcome. Pure structural read — no behavioural data, no PII.
    """
    if subject_id is not None:
        outcome_ids = _subject_outcome_ids(snapshot, subject_id)
    else:
        outcome_ids = [o.id for o in snapshot.outcomes]

    # Map each outcome -> the skills that list it, and -> direct questions.
    skills_by_outcome: dict[str, list[str]] = {}
    for skill in snapshot.skills:
        for oid in skill.outcome_ids:
            skills_by_outcome.setdefault(oid, []).append(skill.id)

    questions_by_skill: dict[str, list[str]] = {}
    direct_questions_by_outcome: dict[str, list[str]] = {}
    for question in snapshot.questions:
        questions_by_skill.setdefault(question.skill_id, []).append(question.id)
        if question.outcome_id is not None:
            direct_questions_by_outcome.setdefault(question.outcome_id, []).append(question.id)

    items: list[OutcomeCoverage] = []
    for oid in outcome_ids:
        skill_ids = tuple(skills_by_outcome.get(oid, ()))
        q_ids: list[str] = list(direct_questions_by_outcome.get(oid, ()))
        for sid in skill_ids:
            q_ids.extend(questions_by_skill.get(sid, ()))
        # De-dup while preserving order.
        seen: set[str] = set()
        deduped = tuple(q for q in q_ids if not (q in seen or seen.add(q)))
        items.append(
            OutcomeCoverage(
                outcome_id=oid,
                covered=bool(deduped),
                skill_ids=skill_ids,
                question_ids=deduped,
            )
        )
    return CoverageReport(items=items)


def competency_coverage(
    snapshot: OntologySnapshot, *, subject_id: str | None = None
) -> list[CompetencyCoverage]:
    """Roll outcome coverage up to the competency level.

    A competency lists the outcomes it is demonstrated through (``outcome_ids``).
    This reuses :func:`outcome_coverage` and partitions each competency's listed
    outcomes into covered / uncovered, deriving a ``full`` / ``partial`` / ``none``
    status. Restrict to ``subject_id`` when given (the competency's subject).
    Deterministic (declaration order on the competencies table). Pure structural
    read — no behavioural data, no PII.
    """
    covered_outcomes = {i.outcome_id for i in outcome_coverage(snapshot).covered}
    out: list[CompetencyCoverage] = []
    for comp in snapshot.competencies:
        if subject_id is not None and comp.subject_id != subject_id:
            continue
        covered = tuple(o for o in comp.outcome_ids if o in covered_outcomes)
        uncovered = tuple(o for o in comp.outcome_ids if o not in covered_outcomes)
        if not comp.outcome_ids:
            status = "none"
        elif not uncovered:
            status = "full"
        elif covered:
            status = "partial"
        else:
            status = "none"
        out.append(
            CompetencyCoverage(
                competency_id=comp.id,
                status=status,
                covered_ids=covered,
                uncovered_ids=uncovered,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Curriculum versioning
# ---------------------------------------------------------------------------


def versions_for_scope(
    snapshot: OntologySnapshot, scope_id: str
) -> list[CurriculumVersion]:
    """All version stamps for a scope, oldest-first by effective date."""
    scoped = [v for v in snapshot.versions if v.scope_id == scope_id]
    return sorted(scoped, key=lambda v: (v.effective_from, v.version))


def effective_version(
    snapshot: OntologySnapshot, scope_id: str, *, on_date: str
) -> CurriculumVersion | None:
    """The version effective for ``scope_id`` on an ISO ``on_date``.

    The latest version whose ``effective_from`` is on or before ``on_date``.
    Returns ``None`` when no version had taken effect yet. ISO date strings sort
    lexicographically, so plain comparison is correct.
    """
    candidates = [
        v for v in versions_for_scope(snapshot, scope_id) if v.effective_from <= on_date
    ]
    return candidates[-1] if candidates else None


def supersession_chain(
    snapshot: OntologySnapshot, scope_id: str
) -> list[CurriculumVersion]:
    """The supersession chain for a scope, oldest-first.

    Built from ``supersedes_id`` links and verified to be linear (each version
    superseded by at most one). Falls back to date order when no links exist.
    """
    scoped = versions_for_scope(snapshot, scope_id)
    if not scoped:
        return []
    superseded_ids = {v.supersedes_id for v in scoped if v.supersedes_id}
    # The head is the one nobody supersedes.
    heads = [v for v in scoped if v.id not in superseded_ids]
    if len(heads) != 1:
        return scoped  # ambiguous links — return date order rather than guess.
    by_id = {v.id: v for v in scoped}
    # Walk backwards from head via supersedes_id, then reverse to oldest-first.
    chain: list[CurriculumVersion] = []
    cursor: CurriculumVersion | None = heads[0]
    seen: set[str] = set()
    while cursor is not None and cursor.id not in seen:
        seen.add(cursor.id)
        chain.append(cursor)
        cursor = by_id.get(cursor.supersedes_id) if cursor.supersedes_id else None
    chain.reverse()
    return chain
