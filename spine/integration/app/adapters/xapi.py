"""xAPI (Experience API / Tin Can) adapter (spine A6).

Translates xAPI statements to/from the bridge's internal
``LearningActivityStatement``. The keystone: the xAPI ``actor`` carries an
identifier (mbox / mbox_sha1sum / account name / openid) that IS PII or
PII-adjacent. On the way IN, the actor is reduced to an opaque, salted source_key
and the raw identifier is dropped. On the way OUT, the actor is emitted as an
``account`` whose ``name`` is the OPAQUE source_key (or canonical_uuid) and whose
``homePage`` is the Classess identity namespace — never an mbox/email.

Round-trip guarantee: ``to_internal(from_internal(stmt))`` preserves verb,
object, result and actor source_key with no PII reintroduced.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..connector import Capability, Connector, Direction
from ..mapping import IdentityResolver, derive_source_key, map_identity
from ..models import (
    CanonicalRef,
    LearningActivityStatement,
    Standard,
    Verb,
    assert_no_pii,
)

# The opaque identity namespace emitted as the xAPI account homePage. Not a
# secret and not PII — a stable namespace URI for Classess canonical refs.
ACCOUNT_HOMEPAGE = "https://id.classess.internal/canonical"

# xAPI verb URI <-> internal verb. ADL/standard verb vocabulary.
_VERB_URI_TO_INTERNAL: dict[str, Verb] = {
    "http://adlnet.gov/expapi/verbs/initialized": Verb.STARTED,
    "http://adlnet.gov/expapi/verbs/launched": Verb.STARTED,
    "http://adlnet.gov/expapi/verbs/completed": Verb.COMPLETED,
    "http://adlnet.gov/expapi/verbs/answered": Verb.ANSWERED,
    "http://adlnet.gov/expapi/verbs/scored": Verb.SCORED,
    "http://adlnet.gov/expapi/verbs/experienced": Verb.VIEWED,
    "http://adlnet.gov/expapi/verbs/progressed": Verb.PROGRESSED,
    "https://w3id.org/xapi/dod-isd/verbs/submitted": Verb.SUBMITTED,
}
_INTERNAL_TO_VERB_URI: dict[Verb, str] = {
    Verb.STARTED: "http://adlnet.gov/expapi/verbs/initialized",
    Verb.COMPLETED: "http://adlnet.gov/expapi/verbs/completed",
    Verb.ANSWERED: "http://adlnet.gov/expapi/verbs/answered",
    Verb.SCORED: "http://adlnet.gov/expapi/verbs/scored",
    Verb.VIEWED: "http://adlnet.gov/expapi/verbs/experienced",
    Verb.PROGRESSED: "http://adlnet.gov/expapi/verbs/progressed",
    Verb.SUBMITTED: "https://w3id.org/xapi/dod-isd/verbs/submitted",
}


class XAPIAdapter(Connector):
    standard = Standard.XAPI

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "statements.ingest", Direction.INBOUND,
                "Ingest xAPI statements as PII-free internal activity statements.",
            ),
            Capability(
                "statements.export", Direction.OUTBOUND,
                "Export internal activity as xAPI statements with opaque actors.",
            ),
            Capability(
                "lrs.forward", Direction.OUTBOUND,
                "Forward statements to an external LRS via a governed gateway capability.",
                consequential=True,
            ),
        ]

    # -- inbound: xAPI -> internal -----------------------------------------
    def to_internal(
        self,
        statement: dict[str, Any],
        *,
        identity_resolver: IdentityResolver | None = None,
    ) -> LearningActivityStatement:
        actor = statement.get("actor") or {}
        raw_actor_id = _xapi_actor_id(actor)
        ref = map_identity(self.standard, raw_actor_id, resolver=identity_resolver)

        verb_uri = (statement.get("verb") or {}).get("id", "")
        verb = _VERB_URI_TO_INTERNAL.get(verb_uri, Verb.VIEWED)

        obj = statement.get("object") or {}
        object_id = obj.get("id", "")
        object_type = (obj.get("objectType") or "Activity").lower()

        result = statement.get("result") or {}
        score = result.get("score") or {}

        ts_raw = statement.get("timestamp")
        timestamp = _parse_ts(ts_raw)

        ctx = statement.get("context") or {}
        ctx_activities = ctx.get("contextActivities") or {}
        parents = ctx_activities.get("parent") or []
        context_ids = [p.get("id") for p in parents if isinstance(p, dict) and p.get("id")]

        return LearningActivityStatement(
            actor=ref,
            verb=verb,
            object_id=object_id,
            object_type="activity" if object_type == "activity" else object_type,
            timestamp=timestamp,
            result_success=result.get("success"),
            result_score_scaled=score.get("scaled"),
            result_completion=result.get("completion"),
            context_activity_ids=context_ids,
        )

    # -- outbound: internal -> xAPI ----------------------------------------
    def from_internal(self, stmt: LearningActivityStatement) -> dict[str, Any]:
        # Actor is an OPAQUE account — the name is the canonical_uuid if resolved,
        # else the unlinkable source_key. NEVER an mbox/email.
        account_name = stmt.actor.canonical_uuid or stmt.actor.source_key
        out: dict[str, Any] = {
            "actor": {
                "objectType": "Agent",
                "account": {"homePage": ACCOUNT_HOMEPAGE, "name": account_name},
            },
            "verb": {"id": _INTERNAL_TO_VERB_URI[stmt.verb]},
            "object": {"objectType": "Activity", "id": stmt.object_id},
            "timestamp": stmt.timestamp.isoformat(),
        }
        result: dict[str, Any] = {}
        if stmt.result_success is not None:
            result["success"] = stmt.result_success
        if stmt.result_completion is not None:
            result["completion"] = stmt.result_completion
        if stmt.result_score_scaled is not None:
            result["score"] = {"scaled": stmt.result_score_scaled}
        if result:
            out["result"] = result
        if stmt.context_activity_ids:
            out["context"] = {
                "contextActivities": {
                    "parent": [{"id": cid} for cid in stmt.context_activity_ids]
                }
            }
        assert_no_pii(out, where="xAPI statement (outbound)")
        return out


def _xapi_actor_id(actor: dict[str, Any]) -> str:
    """Extract a stable external actor id from an xAPI actor (consumed, dropped).

    Order: account.name, mbox, mbox_sha1sum, openid. The raw value never leaves
    this function — it is hashed into the salted source_key by the caller.
    """

    account = actor.get("account") or {}
    if isinstance(account, dict) and account.get("name"):
        home = account.get("homePage", "")
        return f"{home}|{account['name']}"
    if actor.get("mbox"):
        return str(actor["mbox"])
    if actor.get("mbox_sha1sum"):
        return f"sha1:{actor['mbox_sha1sum']}"
    if actor.get("openid"):
        return str(actor["openid"])
    raise ValueError("xAPI actor has no usable identifier.")


def _parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)
