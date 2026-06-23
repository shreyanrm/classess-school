"""Verifiable, portable credentials (B8) — under the learner's control.

A credential is a portable attestation that a learner has demonstrated something
(e.g. independent mastery of a topic). The design rules:

  - UNDER THE LEARNER'S CONTROL. The learner holds and shares the credential;
    sharing it with anyone other than the holder passes the consent + purpose
    gate. The learner can revoke a credential they issued control of.
  - VERIFIABLE. A credential carries a signature over its canonical, PII-free
    payload. A holder (or a third party) can VERIFY it offline against the
    issuer's public key. The signing key NAME is environment-only; with no key
    configured a credential is issued in ``draft`` state and is explicitly NOT
    verifiable — we never fake a signature (INVARIANT 4 + generate-and-verify
    spirit, INVARIANT 7: nothing is served as verified that was not verified).
  - PORTABLE. The exported form is a self-contained, PII-free document that
    verifies away from this system.
  - EVIDENCE-LINKED. Every claim carries its source event-ids — a credential is
    backed by evidence, never an assertion.

PII-FREE: the subject is the opaque ``canonical_uuid``; the claim names an
opaque topic id and a plain-language statement, never a name or a raw score.

NOTE on the signature: this module uses a deterministic HMAC over the canonical
JSON of the payload as the verifiable-credential MECHANISM placeholder. The key
is read from the environment by NAME only and never stored in code; production
swaps in the issuer's asymmetric signing behind the same ``sign``/``verify``
interface. The point load-bearing here is: no key -> no signature -> not
verifiable, never faked.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Literal

from .access import ConsentGrant, ReadRequest, require
from .config import LearnerRecordSettings, get_settings

# What kind of demonstration the credential attests to. ``independent-mastery``
# is the flagship — the learner can do it on their own.
ClaimKind = Literal["independent-mastery", "course-completion", "skill-badge"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class CredentialState(str, Enum):
    """A credential's lifecycle. Only ``verified`` is portable-as-trusted."""

    DRAFT = "draft"          # issued without a signing key — NOT verifiable
    VERIFIED = "verified"    # signed; verifiable offline
    REVOKED = "revoked"      # the learner withdrew it


@dataclass(frozen=True)
class CredentialClaim:
    """The evidence-linked claim a credential attests. PII-free.

    ``statement`` is plain language and carries no raw score — a credential says
    "demonstrated independently", not a number.
    """

    kind: ClaimKind
    topic_id: str
    statement: str
    source_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_event_ids:
            raise ValueError(
                "A credential claim must link to its evidence — no claim "
                "without source events."
            )
        if any(ch.isdigit() for ch in self.statement) or "%" in self.statement:
            raise ValueError(
                "A credential statement must be plain language with no raw "
                "score (no digit, no percentage)."
            )


@dataclass(frozen=True)
class Credential:
    """A verifiable, portable credential held by the learner.

    The ``signature`` is present only in the ``verified`` state. The payload that
    is signed (and exported) is PII-free and self-contained.
    """

    credential_id: str
    subject: str                        # opaque canonical_uuid (the holder)
    claim: CredentialClaim
    issued_at: datetime
    state: CredentialState
    issuer: str = "classess-school"
    expires_at: datetime | None = None
    signature: str | None = None

    @property
    def is_verifiable(self) -> bool:
        return self.state is CredentialState.VERIFIED and bool(self.signature)


def _canonical_payload(
    *,
    credential_id: str,
    subject: str,
    claim: CredentialClaim,
    issued_at: datetime,
    issuer: str,
    expires_at: datetime | None,
) -> str:
    """Canonical, deterministic, PII-free JSON of the signed material.

    Sorted keys + no whitespace so the same credential always produces the same
    bytes — that determinism is what makes offline verification possible.
    """
    body = {
        "credential_id": credential_id,
        "subject": subject,
        "issuer": issuer,
        "issued_at": issued_at.astimezone(timezone.utc).isoformat(),
        "expires_at": expires_at.astimezone(timezone.utc).isoformat() if expires_at else None,
        "claim": {
            "kind": claim.kind,
            "topic_id": claim.topic_id,
            "statement": claim.statement,
            "source_event_ids": list(claim.source_event_ids),
        },
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def _sign(payload: str, *, key: str) -> str:
    """Deterministic signature over the canonical payload using the env-supplied
    key. The key VALUE arrives by name from the environment only — never a
    literal. Production replaces this with asymmetric signing behind the same
    interface."""
    return hmac.new(key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue(
    *,
    subject: str,
    claim: CredentialClaim,
    settings: LearnerRecordSettings | None = None,
    expires_at: datetime | None = None,
    issued_at: datetime | None = None,
    credential_id: str | None = None,
) -> Credential:
    """Issue a credential for a learner.

    If a signing key is configured (by env NAME) the credential is signed and
    issued ``verified``; otherwise it is issued ``draft`` and is explicitly NOT
    verifiable — we never fabricate a signature.
    """
    settings = settings or get_settings()
    cid = credential_id or _new_id()
    issued = issued_at or _now()

    if not settings.can_sign_credentials:
        return Credential(
            credential_id=cid,
            subject=subject,
            claim=claim,
            issued_at=issued,
            state=CredentialState.DRAFT,
            expires_at=expires_at,
            signature=None,
        )

    payload = _canonical_payload(
        credential_id=cid,
        subject=subject,
        claim=claim,
        issued_at=issued,
        issuer="classess-school",
        expires_at=expires_at,
    )
    assert settings.credential_signing_key is not None  # guarded by can_sign
    sig = _sign(payload, key=settings.credential_signing_key)
    return Credential(
        credential_id=cid,
        subject=subject,
        claim=claim,
        issued_at=issued,
        state=CredentialState.VERIFIED,
        expires_at=expires_at,
        signature=sig,
    )


def verify(
    credential: Credential,
    *,
    settings: LearnerRecordSettings | None = None,
    asof: datetime | None = None,
) -> bool:
    """Verify a credential's signature against the issuer key (by env name).

    Returns False for draft/revoked credentials, expired credentials, a missing
    signature, a missing key, or a signature that does not match. Constant-time
    comparison on the signature.
    """
    settings = settings or get_settings()
    asof = asof or _now()
    if not credential.is_verifiable:
        return False
    if credential.expires_at is not None and asof >= credential.expires_at:
        return False
    if not settings.can_sign_credentials:
        return False
    payload = _canonical_payload(
        credential_id=credential.credential_id,
        subject=credential.subject,
        claim=credential.claim,
        issued_at=credential.issued_at,
        issuer=credential.issuer,
        expires_at=credential.expires_at,
    )
    assert settings.credential_signing_key is not None
    expected = _sign(payload, key=settings.credential_signing_key)
    return hmac.compare_digest(expected, credential.signature or "")


def revoke(credential: Credential) -> Credential:
    """Return a revoked copy — the learner withdrawing control. Append-only in
    spirit: the original is unchanged; a new revoked state supersedes it."""
    return Credential(
        credential_id=credential.credential_id,
        subject=credential.subject,
        claim=credential.claim,
        issued_at=credential.issued_at,
        state=CredentialState.REVOKED,
        issuer=credential.issuer,
        expires_at=credential.expires_at,
        signature=None,
    )


def export_portable(
    credential: Credential,
    *,
    request: ReadRequest,
    grants: Iterable[ConsentGrant],
    asof: datetime | None = None,
) -> dict:
    """Export a self-contained, PII-free, portable credential document.

    GATED: sharing a credential with anyone other than the holder passes the
    consent + purpose gate (scope ``credentials``). A self-export by the holder
    is in-audience by construction; an export to a third party is denied unless
    the learner consented. The returned document verifies away from this system.
    """
    require(request, grants, asof=asof)
    return {
        "format": "classess.credential.v1",
        "credential_id": credential.credential_id,
        "subject": credential.subject,            # opaque canonical_uuid only
        "issuer": credential.issuer,
        "issued_at": credential.issued_at.astimezone(timezone.utc).isoformat(),
        "expires_at": (
            credential.expires_at.astimezone(timezone.utc).isoformat()
            if credential.expires_at
            else None
        ),
        "state": credential.state.value,
        "verifiable": credential.is_verifiable,
        "claim": {
            "kind": credential.claim.kind,
            "topic_id": credential.claim.topic_id,
            "statement": credential.claim.statement,
            "source_event_ids": list(credential.claim.source_event_ids),
        },
        "signature": credential.signature,
    }


__all__ = [
    "ClaimKind",
    "CredentialState",
    "CredentialClaim",
    "Credential",
    "issue",
    "verify",
    "revoke",
    "export_portable",
]
