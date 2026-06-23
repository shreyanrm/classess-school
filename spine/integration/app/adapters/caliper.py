"""IMS Caliper Analytics adapter (spine A6).

Translates Caliper events to/from the bridge's internal
``LearningActivityStatement``. As with xAPI, the Caliper ``actor`` carries a
person id; on the way IN it is reduced to an opaque salted source_key (raw id
dropped). On the way OUT the actor is emitted with an opaque Classess id IRI —
never an email/login.

Round-trip guarantee: ``to_internal(from_internal(stmt))`` preserves verb,
object, result and actor source_key with no PII reintroduced.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..connector import Capability, Connector, Direction
from ..mapping import IdentityResolver, map_identity
from ..models import (
    LearningActivityStatement,
    Standard,
    Verb,
    assert_no_pii,
)

ACTOR_IRI_PREFIX = "https://id.classess.internal/canonical/"

# Caliper action <-> internal verb. Caliper action vocabulary.
_ACTION_TO_INTERNAL: dict[str, Verb] = {
    "Started": Verb.STARTED,
    "Completed": Verb.COMPLETED,
    "Submitted": Verb.SUBMITTED,
    "Graded": Verb.SCORED,
    "Viewed": Verb.VIEWED,
    "Used": Verb.VIEWED,
    "completed": Verb.COMPLETED,
}
_INTERNAL_TO_ACTION: dict[Verb, str] = {
    Verb.STARTED: "Started",
    Verb.COMPLETED: "Completed",
    Verb.SUBMITTED: "Submitted",
    Verb.SCORED: "Graded",
    Verb.VIEWED: "Viewed",
    Verb.ANSWERED: "Completed",
    Verb.PROGRESSED: "Used",
}


class CaliperAdapter(Connector):
    standard = Standard.CALIPER

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "events.ingest", Direction.INBOUND,
                "Ingest Caliper events as PII-free internal activity statements.",
            ),
            Capability(
                "events.export", Direction.OUTBOUND,
                "Export internal activity as Caliper events with opaque actors.",
            ),
            Capability(
                "endpoint.forward", Direction.OUTBOUND,
                "Forward an envelope to a Caliper endpoint via a governed gateway capability.",
                consequential=True,
            ),
        ]

    # -- inbound: Caliper -> internal --------------------------------------
    def to_internal(
        self,
        event: dict[str, Any],
        *,
        identity_resolver: IdentityResolver | None = None,
    ) -> LearningActivityStatement:
        actor = event.get("actor")
        raw_actor_id = _caliper_entity_id(actor)
        ref = map_identity(self.standard, raw_actor_id, resolver=identity_resolver)

        action = event.get("action", "")
        verb = _ACTION_TO_INTERNAL.get(action, Verb.VIEWED)

        object_id = _caliper_entity_id(event.get("object"), required=False) or ""

        generated = event.get("generated") or {}
        score = None
        success = None
        if isinstance(generated, dict):
            max_score = generated.get("maxScore")
            given = generated.get("scoreGiven")
            if given is not None and max_score:
                try:
                    score = float(given) / float(max_score)
                except (TypeError, ZeroDivisionError, ValueError):
                    score = None
            elif given is not None:
                try:
                    score = float(given)
                except (TypeError, ValueError):
                    score = None

        timestamp = _parse_ts(event.get("eventTime"))

        return LearningActivityStatement(
            actor=ref,
            verb=verb,
            object_id=object_id,
            timestamp=timestamp,
            result_success=success,
            result_score_scaled=score,
        )

    # -- outbound: internal -> Caliper -------------------------------------
    def from_internal(self, stmt: LearningActivityStatement) -> dict[str, Any]:
        actor_id = ACTOR_IRI_PREFIX + (stmt.actor.canonical_uuid or stmt.actor.source_key)
        out: dict[str, Any] = {
            "@context": "http://purl.imsglobal.org/ctx/caliper/v1p2",
            "type": "Event",
            "actor": {"id": actor_id, "type": "Person"},
            "action": _INTERNAL_TO_ACTION[stmt.verb],
            "object": {"id": stmt.object_id, "type": "DigitalResource"},
            "eventTime": stmt.timestamp.isoformat(),
        }
        if stmt.result_score_scaled is not None:
            out["generated"] = {
                "type": "Score",
                "scoreGiven": stmt.result_score_scaled,
                "maxScore": 1.0,
            }
        assert_no_pii(out, where="Caliper event (outbound)")
        return out


def _caliper_entity_id(entity: Any, *, required: bool = True) -> str:
    """Extract an entity id from a Caliper actor/object (string IRI or dict)."""

    if isinstance(entity, str):
        return entity
    if isinstance(entity, dict) and entity.get("id"):
        return str(entity["id"])
    if required:
        raise ValueError("Caliper entity has no id.")
    return ""


def _parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)
