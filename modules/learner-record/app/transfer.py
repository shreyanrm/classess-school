"""Portable record handoff between permitted contexts (B8).

The doc (section 14): "records are portable between permitted contexts under the
learner's control — the foundation for an evidence-backed, independence-aware
record that can become a trusted signal over time."

Single-credential export already exists (``credentials.export_portable``,
``artifacts.export_artifact``). This module composes the next step: a
learner-controlled HANDOFF — a bundle of the learner's own credentials and
issuance artifacts, prepared FOR a named permitted context (e.g. a next school,
an examination body), gated, self-contained, PII-free, and REVOCABLE.

Hard rules honoured here:

  - UNDER THE LEARNER'S CONTROL + PERMISSION LADDER (invariants 5, 6). A handoff
    to a context other than the holder is CONSEQUENTIAL: :func:`prepare_handoff`
    returns a ``requires_approval`` proposal; only :func:`authorize_handoff`
    with an explicit human ref makes it real. A self-handoff (the learner taking
    their own record) is in-audience by construction but still recorded.
  - GATED EXPORT. The portable document is produced only behind the consent +
    purpose gate, reusing each item's own export path (scope ``credentials``) so
    a single audit trail covers the bundle. Denied-by-default.
  - REVOCABLE. The learner can revoke a handoff they authorized; a revoked
    handoff refuses to export (append-only: a new revoked state supersedes it).
  - VERIFIABILITY NEVER FAKED (invariants 4, 7). Each embedded credential/
    artifact reports its real verifiable state; an unsigned-draft item travels
    as NOT verifiable. The bundle's ``fully_verifiable`` is true only when every
    item is verifiable.
  - PII-FREE. Subject and recipient context are opaque ids; nothing carries a
    name, email, or raw score.

B8 does NOT decide a context is "trusted" or transmit anything itself — it MODELS
the learner-controlled bundle, GATES the export, and HOLDS the revocable state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable

from .access import ConsentGrant, ReadRequest
from .artifacts import Badge, Certificate, export_artifact
from .credentials import Credential, export_portable


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# The items a handoff can carry: verifiable credentials and the certificate /
# badge artifacts built on them. All belong to the holder and carry provenance.
HandoffItem = Credential | Certificate | Badge


class HandoffState(str, Enum):
    """Lifecycle of a portable handoff. Only AUTHORIZED can export."""

    PROPOSED = "proposed"       # prepared, awaiting human authorization
    AUTHORIZED = "authorized"   # the learner (human) authorized the handoff
    REVOKED = "revoked"         # the learner withdrew it — export refused


@dataclass(frozen=True)
class HandoffProposal:
    """A prepared, consequential handoff awaiting the learner's authorization.

    Mirrors the ``requires_approval`` contract used across the platform: a
    surface renders "authorize / decline"; only :func:`authorize_handoff` with
    an explicit human ref makes it real.
    """

    handoff_id: str
    subject: str                       # opaque canonical_uuid (the holder)
    recipient_context: str             # opaque id of the permitted context
    item_count: int
    rationale: str                     # plain-language WHY (explainable)
    requires_approval: bool = True


@dataclass(frozen=True)
class RecordHandoff:
    """A learner-controlled, revocable bundle of portable record items.

    The bundle names the recipient context (opaque) and holds the holder's own
    credentials/artifacts. It is exported only via :func:`export_handoff`, behind
    the gate; a revoked handoff refuses to export.
    """

    handoff_id: str
    subject: str                       # opaque canonical_uuid (the holder)
    recipient_context: str             # opaque id of the permitted context
    items: tuple[HandoffItem, ...]
    state: HandoffState
    created_at: datetime
    authorized_by: str | None = None   # opaque ref of the authorizing human
    authorized_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("A record handoff must carry at least one item.")
        for item in self.items:
            if item.subject != self.subject:
                raise ValueError(
                    "A handoff may only carry the holder's own record items."
                )

    @property
    def fully_verifiable(self) -> bool:
        """True only when EVERY item is verifiable — the bundle never claims a
        trust its weakest item lacks (verifiability never faked)."""
        return all(item.is_verifiable for item in self.items)


def prepare_handoff(
    *,
    subject: str,
    recipient_context: str,
    items: Iterable[HandoffItem],
    rationale: str,
    created_at: datetime | None = None,
    handoff_id: str | None = None,
) -> tuple[RecordHandoff, HandoffProposal]:
    """Prepare (do NOT export) a portable record handoff to a permitted context.

    Returns the PROPOSED handoff plus a ``requires_approval`` proposal. Handing a
    record to another context is consequential and learner-controlled — the human
    authorizes it explicitly via :func:`authorize_handoff`. The bundle is built
    here (so the item set is fixed at proposal time) but cannot export until
    authorized.
    """
    hid = handoff_id or _new_id()
    handoff = RecordHandoff(
        handoff_id=hid,
        subject=subject,
        recipient_context=recipient_context,
        items=tuple(items),
        state=HandoffState.PROPOSED,
        created_at=created_at or _now(),
    )
    proposal = HandoffProposal(
        handoff_id=hid,
        subject=subject,
        recipient_context=recipient_context,
        item_count=len(handoff.items),
        rationale=rationale,
    )
    return handoff, proposal


def authorize_handoff(
    handoff: RecordHandoff,
    *,
    authorized_by: str,
    authorized_at: datetime | None = None,
) -> RecordHandoff:
    """Authorize a proposed handoff — the explicit HUMAN step (learner control).

    ``authorized_by`` is the opaque ref of the authorizing human (the learner, or
    a guardian for a child tier); an empty ref is refused so no handoff is ever
    unattributed. Only a proposed handoff can be authorized.
    """
    if not authorized_by:
        raise ValueError("Authorizing a handoff requires the deciding human's opaque ref.")
    if handoff.state is not HandoffState.PROPOSED:
        raise ValueError("Only a proposed handoff can be authorized.")
    return replace(
        handoff,
        state=HandoffState.AUTHORIZED,
        authorized_by=authorized_by,
        authorized_at=authorized_at or _now(),
    )


def revoke_handoff(handoff: RecordHandoff) -> RecordHandoff:
    """Revoke a handoff — the learner withdrawing control of a shared record.

    Append-only in spirit: the original is unchanged; a new revoked state
    supersedes it. A revoked handoff refuses to export.
    """
    return replace(handoff, state=HandoffState.REVOKED)


def export_handoff(
    handoff: RecordHandoff,
    *,
    request: ReadRequest,
    grants: Iterable[ConsentGrant],
    asof: datetime | None = None,
) -> dict:
    """Export the self-contained, PII-free, portable handoff document.

    Refused unless the handoff is AUTHORIZED (a proposed or revoked handoff never
    exports — learner control + revocability). GATED: each item exports through
    its own gate (scope ``credentials``), so the consent + purpose check runs
    per item and a third-party export is denied unless the learner consented; a
    self-export by the holder is in-audience by construction. Each embedded item
    reports its real verifiable state; the bundle never fakes trust.
    """
    grants = list(grants)
    if handoff.state is not HandoffState.AUTHORIZED:
        raise PermissionError(
            "Only an authorized handoff can be exported (it is "
            f"'{handoff.state.value}'). Learner control is required first."
        )

    item_docs: list[dict] = []
    for item in handoff.items:
        if isinstance(item, Credential):
            item_docs.append(
                export_portable(item, request=request, grants=grants, asof=asof)
            )
        else:  # Certificate | Badge
            item_docs.append(
                export_artifact(item, request=request, grants=grants, asof=asof)
            )

    return {
        "format": "classess.record-handoff.v1",
        "handoff_id": handoff.handoff_id,
        "subject": handoff.subject,                # opaque canonical_uuid only
        "recipient_context": handoff.recipient_context,
        "state": handoff.state.value,
        "authorized_at": (
            handoff.authorized_at.astimezone(timezone.utc).isoformat()
            if handoff.authorized_at
            else None
        ),
        "fully_verifiable": handoff.fully_verifiable,
        "items": item_docs,
    }


__all__ = [
    "HandoffItem",
    "HandoffState",
    "HandoffProposal",
    "RecordHandoff",
    "prepare_handoff",
    "authorize_handoff",
    "revoke_handoff",
    "export_handoff",
]
