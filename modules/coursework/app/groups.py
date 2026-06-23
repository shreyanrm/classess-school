"""Balanced group-project composition (B6, domain 9).

Composes learners into project teams of COMPARABLE capability, balancing by a
configurable mastery/skill mix, and explains every placement. The dossier line:
"the platform composes groups of comparable capability from the mastery data,
supports milestones and multiple submission types, and applies project rubrics
covering contribution, collaboration, communication, leadership, quality, and
problem-solving."

This module owns ONLY the composition: turning per-learner mastery/skill signals
into balanced teams. The mastery numbers are CONSUMED from the intelligence
layer's evidence/mastery engine — never computed or owned here (altitude: a
School module never owns a spine concern). The project rubric and grading live in
``rubric``/``evaluation``.

Non-negotiables encoded here:

  - Behavioural data carries ONLY the opaque ``canonical_uuid`` — never PII. A
    learner is a bare uuid plus board-agnostic skill scores; no names anywhere.
  - HUMAN AUTHORITY (permission ladder, RECOMMEND rung): composition is a
    *recommendation*. ``GroupComposition.rung`` is always "recommend"; a teacher
    reviews and accepts. It is never auto-applied to a record.
  - EXPLAINABLE INTELLIGENCE: every group and the composition as a whole carry a
    plain-language rationale, the balance metric used, the evidence (the skill
    averages), and a confidence/quality read on how even the split is.
  - CONFIGURABLE: which skill dimensions to balance on, their weights, target
    group size, and whether to MIX (spread strong learners across teams, the
    default) or CLUSTER (group like with like) are all caller-set.

Pure: no I/O, no provider, no network. Import-safe.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID


# ---------------------------------------------------------------------------
# Inputs — opaque learner + board-agnostic skill signals (no PII).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LearnerSignal:
    """One learner's capability signal for composition.

    ``canonical_uuid`` is the opaque subject ref (never PII). ``skills`` maps a
    skill/competency dimension key -> mastery score in [0,1], drawn from the
    intelligence layer. Dimension keys are caller-supplied (board-agnostic); the
    composer only ever reads the dimensions named in the ``GroupConfig``.
    """

    canonical_uuid: UUID
    skills: dict[str, float] = field(default_factory=dict)

    def weighted_capability(self, weights: dict[str, float]) -> float:
        """The learner's overall capability as a weighted mean over the configured
        dimensions. A dimension absent from this learner's signal contributes 0
        (an unknown is not assumed strong). Returns a value in [0,1]."""
        total_w = sum(weights.values())
        if total_w <= 0:
            return 0.0
        acc = 0.0
        for dim, w in weights.items():
            acc += w * max(0.0, min(1.0, self.skills.get(dim, 0.0)))
        return acc / total_w


class BalanceStrategy(str, Enum):
    """How to balance.

      - MIX     — spread capability so every team is comparable (the default; the
                  dossier's "comparable capability"). Strong learners are
                  distributed, not concentrated.
      - CLUSTER — group like-with-like (near-peer teams), e.g. for tiered or
                  differentiated project tracks.
    """

    MIX = "mix"
    CLUSTER = "cluster"


@dataclass(frozen=True)
class GroupConfig:
    """Configurable composition policy.

    ``dimension_weights`` selects which skill dimensions matter and their relative
    weight; only these dimensions are read. ``target_group_size`` is the desired
    team size (the last team absorbs the remainder). ``strategy`` picks mix vs
    cluster. ``balance_tolerance`` is the max acceptable spread (range of team
    capability means) before the composition is flagged as not-well-balanced.
    """

    dimension_weights: dict[str, float]
    target_group_size: int = 4
    strategy: BalanceStrategy = BalanceStrategy.MIX
    balance_tolerance: float = 0.15

    def __post_init__(self) -> None:
        if not self.dimension_weights:
            raise ValueError("at least one dimension weight is required to balance on.")
        if any(w < 0 for w in self.dimension_weights.values()):
            raise ValueError("dimension weights must be non-negative.")
        if sum(self.dimension_weights.values()) <= 0:
            raise ValueError("dimension weights must sum to a positive value.")
        if self.target_group_size < 1:
            raise ValueError("target_group_size must be >= 1.")
        if not (0.0 <= self.balance_tolerance <= 1.0):
            raise ValueError("balance_tolerance must be in [0,1].")


# ---------------------------------------------------------------------------
# Outputs — groups + an explainable composition.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Group:
    """One composed team. Members are opaque uuids; the rationale and the
    per-dimension averages make the placement explainable."""

    label: str
    members: list[UUID]
    capability_mean: float
    dimension_means: dict[str, float]
    rationale: str

    @property
    def size(self) -> int:
        return len(self.members)


@dataclass(frozen=True)
class GroupComposition:
    """The full composition — the groups plus the balance evidence and a
    plain-language explanation. A RECOMMENDATION to a teacher, never auto-applied.
    """

    groups: list[Group]
    strategy: BalanceStrategy
    balanced: bool
    spread: float  # range of team capability means; lower is more even (MIX)
    balance_tolerance: float
    rationale: str
    unplaced: list[UUID] = field(default_factory=list)

    @property
    def rung(self) -> str:
        """Permission-ladder rung: always RECOMMEND. A teacher accepts the
        composition; the system never auto-assigns groups to a record."""
        return "recommend"

    @property
    def group_count(self) -> int:
        return len(self.groups)


# ---------------------------------------------------------------------------
# The composer.
# ---------------------------------------------------------------------------
def _group_count(n: int, target: int) -> int:
    """Number of teams for ``n`` learners at ``target`` size — at least one team,
    and never more teams than learners."""
    if n <= 0:
        return 0
    return max(1, min(n, round(n / target) or 1))


def _dimension_means(members: list[LearnerSignal], dims: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for dim in dims:
        vals = [max(0.0, min(1.0, m.skills.get(dim, 0.0))) for m in members]
        out[dim] = statistics.fmean(vals) if vals else 0.0
    return out


def compose_groups(
    learners: list[LearnerSignal],
    config: GroupConfig,
) -> GroupComposition:
    """Compose ``learners`` into balanced teams under ``config``.

    MIX (default): learners are ranked by weighted capability and dealt across
    teams in a serpentine (snake) order, which is a deterministic, explainable
    way to keep every team's mean close — the strongest and weakest are spread so
    no team is stacked. CLUSTER: ranked learners are sliced into contiguous
    near-peer teams.

    The result is a RECOMMENDATION (RECOMMEND rung): every group carries its
    capability mean, its per-dimension averages (the evidence), and a rationale;
    the composition reports whether the spread is within tolerance and explains
    why. A teacher reviews and accepts — nothing is auto-applied.
    """
    weights = config.dimension_weights
    dims = list(weights.keys())

    if not learners:
        return GroupComposition(
            groups=[],
            strategy=config.strategy,
            balanced=True,
            spread=0.0,
            balance_tolerance=config.balance_tolerance,
            rationale="No learners supplied — nothing to compose.",
        )

    # Rank by weighted capability (stable; ties keep input order for determinism).
    ranked = sorted(
        learners,
        key=lambda lr: lr.weighted_capability(weights),
        reverse=True,
    )
    k = _group_count(len(ranked), config.target_group_size)
    buckets: list[list[LearnerSignal]] = [[] for _ in range(k)]

    if config.strategy is BalanceStrategy.MIX:
        # Serpentine deal: 0,1,..,k-1, k-1,..,1,0, ... keeps team means close.
        idx = 0
        direction = 1
        for learner in ranked:
            buckets[idx].append(learner)
            nxt = idx + direction
            if nxt < 0 or nxt >= k:
                direction *= -1  # reverse at the ends -> serpentine
                nxt = idx + direction
            idx = nxt
    else:  # CLUSTER — contiguous near-peer slices.
        # Even-ish slice sizes, larger slices first.
        base, extra = divmod(len(ranked), k)
        pos = 0
        for b in range(k):
            take = base + (1 if b < extra else 0)
            buckets[b] = ranked[pos : pos + take]
            pos += take

    groups: list[Group] = []
    for b, members in enumerate(buckets):
        if not members:
            continue
        d_means = _dimension_means(members, dims)
        cap_mean = statistics.fmean([m.weighted_capability(weights) for m in members])
        if config.strategy is BalanceStrategy.MIX:
            rationale = (
                f"Team {b + 1}: {len(members)} members spread across the capability "
                f"range so the team mean ({cap_mean:.2f}) matches the others. "
                f"Balanced on {', '.join(dims)}."
            )
        else:
            rationale = (
                f"Team {b + 1}: {len(members)} near-peer members (mean {cap_mean:.2f}) "
                f"clustered by comparable capability on {', '.join(dims)}."
            )
        groups.append(
            Group(
                label=f"Team {b + 1}",
                members=[m.canonical_uuid for m in members],
                capability_mean=cap_mean,
                dimension_means=d_means,
                rationale=rationale,
            )
        )

    means = [g.capability_mean for g in groups]
    spread = (max(means) - min(means)) if len(means) > 1 else 0.0

    if config.strategy is BalanceStrategy.MIX:
        balanced = spread <= config.balance_tolerance
        if balanced:
            comp_rationale = (
                f"{len(groups)} teams composed by spreading capability evenly. "
                f"Team means range {spread:.2f}, within the {config.balance_tolerance:.2f} "
                "tolerance — the teams are comparable. Recommendation for a teacher to accept."
            )
        else:
            comp_rationale = (
                f"{len(groups)} teams composed, but team means range {spread:.2f}, "
                f"above the {config.balance_tolerance:.2f} tolerance — likely too few "
                "learners or very uneven capability. Flagged for a teacher to adjust."
            )
    else:
        # For CLUSTER an even spread is NOT the goal; tiering is intentional.
        balanced = True
        comp_rationale = (
            f"{len(groups)} near-peer teams composed by clustering comparable "
            f"capability (intended spread {spread:.2f}). Recommendation for a teacher to accept."
        )

    return GroupComposition(
        groups=groups,
        strategy=config.strategy,
        balanced=balanced,
        spread=spread,
        balance_tolerance=config.balance_tolerance,
        rationale=comp_rationale,
    )
