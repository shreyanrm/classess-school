"""Reconcile attendance against EXTERNAL signal sources (d8).

Beyond the in-classroom capture methods (see ``reconciliation.py``), a school
emits other presence signals from systems the attendance domain does not own:

  - a TRANSPORT feed: a learner boarded the school bus this morning;
  - a school-ARRIVAL signal: the learner was marked present in class;
  - a GATE-ENTRY feed: the learner badged through the school gate;
  - a CLASSROOM signal: the learner appears in the confirmed classroom roll.

These pairs should normally AGREE. When they disagree — boarded the bus but
never reached class, or badged in at the gate but is absent from the classroom
roll — that is a SAFEGUARDING-RELEVANT conflict (a learner may be on-site but
unaccounted for) and it is surfaced for HUMAN review, never auto-resolved and
never treated as misconduct (d8: "flags conflicts for human review rather than
treating them as misconduct").

INGEST MODEL: external signals arrive as plain :class:`ExternalSignal` records
keyed by an opaque ``canonical_uuid`` and a ``source``. No PII, no raw device
identifiers, no network — the device/integration layer normalises to this shape
upstream; here we only reconcile already-opaque signals offline.

Output is a list of :class:`SignalConflict` plus a review payload, mirroring the
in-classroom reconciler. Conflicts carry ``needs_human_review`` and a plain-
language rationale (explainability).

Import-safe: pure functions over plain data; no I/O, no provider, no secret.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Sequence


class SignalSource(str, Enum):
    """An external presence source. Each is a SIGNAL, never proof."""

    TRANSPORT = "transport"      # boarded the school bus
    ARRIVAL = "arrival"          # reached / marked present at school
    GATE = "gate"                # badged through the school gate
    CLASSROOM = "classroom"      # appears in the confirmed classroom roll


class Presence(str, Enum):
    """What a source observed for a learner."""

    OBSERVED = "observed"        # signal positively saw the learner
    NOT_OBSERVED = "not_observed"  # source ran but did not see the learner
    NO_DATA = "no_data"          # source had nothing to say (do not infer)


@dataclass(frozen=True)
class ExternalSignal:
    """One external source's observation of one learner on one day.

    PII-free: ``canonical_uuid`` only. The ``confidence`` rides from the
    upstream integration; a weak signal is still surfaced rather than trusted.
    """

    canonical_uuid: str
    source: SignalSource
    presence: Presence
    date: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.canonical_uuid:
            raise ValueError("ExternalSignal requires an opaque canonical_uuid.")
        if "@" in self.canonical_uuid:
            raise ValueError("canonical_uuid must be opaque, not PII.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0,1].")


# The pairs we expect to corroborate each other. The first source implies the
# learner should also show on the second; a positive-then-missing is the
# safeguarding-relevant conflict ("on the bus / on-site but not in class").
_CORROBORATING_PAIRS = (
    (SignalSource.TRANSPORT, SignalSource.ARRIVAL),
    (SignalSource.GATE, SignalSource.CLASSROOM),
)


@dataclass(frozen=True)
class SignalConflict:
    """A reconciled cross-source conflict for one learner. Surfaced, not solved."""

    canonical_uuid: str
    date: str
    upstream_source: str        # the source that observed the learner
    downstream_source: str      # the source that should have, but did not
    rationale: str              # plain-language why (explainability)
    needs_human_review: bool = True
    safeguarding_relevant: bool = True


def _index(signals: Sequence[ExternalSignal]) -> Dict[str, Dict[SignalSource, ExternalSignal]]:
    by_student: Dict[str, Dict[SignalSource, ExternalSignal]] = {}
    for s in signals:
        by_student.setdefault(s.canonical_uuid, {})[s.source] = s
    return by_student


def reconcile_external(signals: Sequence[ExternalSignal]) -> List[SignalConflict]:
    """Reconcile external signals across the corroborating source pairs.

    A conflict is raised only when an UPSTREAM source positively OBSERVED the
    learner but the DOWNSTREAM source that should corroborate it explicitly did
    NOT observe them. ``NO_DATA`` never raises a conflict — a silent source is
    never read as evidence of absence (fail-closed against false accusation).
    """

    conflicts: List[SignalConflict] = []
    by_student = _index(signals)
    for cuid, by_source in by_student.items():
        for upstream, downstream in _CORROBORATING_PAIRS:
            up = by_source.get(upstream)
            down = by_source.get(downstream)
            if up is None or down is None:
                continue
            if up.presence is Presence.OBSERVED and down.presence is Presence.NOT_OBSERVED:
                conflicts.append(
                    SignalConflict(
                        canonical_uuid=cuid,
                        date=up.date,
                        upstream_source=upstream.value,
                        downstream_source=downstream.value,
                        rationale=(
                            f"Seen by {upstream.value} but not by {downstream.value} "
                            f"on {up.date}. The learner may be on-site yet "
                            "unaccounted for — a human should check, not a "
                            "misconduct flag."
                        ),
                    )
                )
    return conflicts


def to_review_payload(conflicts: Sequence[SignalConflict]) -> List[Dict[str, object]]:
    """Plain-language conflict list for an explainable review surface. PII-free."""

    return [
        {
            "canonical_uuid": c.canonical_uuid,
            "date": c.date,
            "upstream_source": c.upstream_source,
            "downstream_source": c.downstream_source,
            "rationale": c.rationale,
            "needs_human_review": True,
            "safeguarding_relevant": c.safeguarding_relevant,
        }
        for c in conflicts
    ]
