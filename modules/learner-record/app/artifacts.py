"""Distinct CERTIFICATE and BADGE issuance artifacts (B8).

The doc (section 14): "certificates, badges, and credentials are issued and
verifiable." A credential (``credentials.py``) is the underlying verifiable
attestation; a CERTIFICATE and a BADGE are distinct, presentable ARTIFACTS built
ON a credential — they are what a learner shows and shares, with their own
identity, plain-language title, and (for a badge) a visual emblem reference.

The distinction (beyond the credential's claim-kind label):

  - A CERTIFICATE attests completion/achievement of something substantial — a
    course, a project, an exam milestone. It is a formal document.
  - A BADGE recognises a discrete skill or independent mastery — a smaller,
    collectible, emblem-bearing recognition.

Both:
  - WRAP A VERIFIABLE CREDENTIAL. The artifact is only as trustworthy as its
    credential: if the credential is unsigned-draft (no key), the artifact is
    issued NOT verifiable — never faked (INVARIANT 4 + 7). Production swaps the
    HMAC placeholder in ``credentials.py`` for asymmetric signing behind the
    same interface; this module needs no change for that.
  - ARE PII-FREE. Subject is the opaque ``canonical_uuid``; title and emblem are
    plain-language / opaque references, never a name or raw score.
  - EXPORT GATED. Sharing an artifact with anyone but the holder passes the
    consent + purpose gate (scope ``credentials``), reusing the credential
    export path so a single audit trail covers it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable

from .access import ConsentGrant, ReadRequest
from .credentials import Credential, export_portable


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class ArtifactType(str, Enum):
    """The two distinct issuance artifacts (beyond the credential claim kind)."""

    CERTIFICATE = "certificate"
    BADGE = "badge"


def _assert_plain_title(title: str) -> None:
    if not title:
        raise ValueError("An issuance artifact needs a plain-language title.")
    if any(ch.isdigit() for ch in title) or "%" in title:
        raise ValueError(
            "An artifact title must be plain language with no raw score "
            "(no digit, no percentage)."
        )


@dataclass(frozen=True)
class Certificate:
    """A formal certificate artifact wrapping a verifiable credential.

    The certificate is verifiable IFF its credential is verifiable — the wrapper
    never adds trust the credential lacks.
    """

    artifact_id: str
    artifact_type: ArtifactType
    subject: str                       # opaque canonical_uuid (the holder)
    title: str                         # plain-language, no number
    credential: Credential
    issued_at: datetime

    def __post_init__(self) -> None:
        _assert_plain_title(self.title)
        if self.subject != self.credential.subject:
            raise ValueError("Certificate subject must match its credential's subject.")
        if self.artifact_type is not ArtifactType.CERTIFICATE:
            raise ValueError("Certificate must carry the CERTIFICATE type.")

    @property
    def is_verifiable(self) -> bool:
        """Only verifiable when the wrapped credential is verifiable — never
        faked (a draft credential yields a non-verifiable certificate)."""
        return self.credential.is_verifiable


@dataclass(frozen=True)
class Badge:
    """A collectible badge artifact wrapping a verifiable credential.

    ``emblem_ref`` is an OPAQUE handle into governed asset storage for the
    badge's visual — never an inline blob, never PII.
    """

    artifact_id: str
    artifact_type: ArtifactType
    subject: str
    title: str                         # plain-language, no number
    credential: Credential
    issued_at: datetime
    emblem_ref: str = ""               # opaque visual asset handle

    def __post_init__(self) -> None:
        _assert_plain_title(self.title)
        if self.subject != self.credential.subject:
            raise ValueError("Badge subject must match its credential's subject.")
        if self.artifact_type is not ArtifactType.BADGE:
            raise ValueError("Badge must carry the BADGE type.")

    @property
    def is_verifiable(self) -> bool:
        return self.credential.is_verifiable


def issue_certificate(
    *,
    credential: Credential,
    title: str,
    issued_at: datetime | None = None,
    artifact_id: str | None = None,
) -> Certificate:
    """Issue a certificate artifact over an existing credential.

    The certificate inherits its verifiability from the credential: pass an
    unsigned-draft credential and you get a non-verifiable certificate — the
    wrapper never fabricates trust.
    """
    return Certificate(
        artifact_id=artifact_id or _new_id(),
        artifact_type=ArtifactType.CERTIFICATE,
        subject=credential.subject,
        title=title,
        credential=credential,
        issued_at=issued_at or _now(),
    )


def issue_badge(
    *,
    credential: Credential,
    title: str,
    emblem_ref: str = "",
    issued_at: datetime | None = None,
    artifact_id: str | None = None,
) -> Badge:
    """Issue a badge artifact over an existing credential (verifiability
    inherited from the credential — never faked)."""
    return Badge(
        artifact_id=artifact_id or _new_id(),
        artifact_type=ArtifactType.BADGE,
        subject=credential.subject,
        title=title,
        credential=credential,
        issued_at=issued_at or _now(),
        emblem_ref=emblem_ref,
    )


def export_artifact(
    artifact: Certificate | Badge,
    *,
    request: ReadRequest,
    grants: Iterable[ConsentGrant],
    asof: datetime | None = None,
) -> dict:
    """Export a self-contained, PII-free, portable artifact document.

    GATED: reuses the credential export gate (scope ``credentials``) so sharing
    an artifact with a third party is denied unless the learner consented; a
    self-export by the holder is in-audience by construction. The embedded
    credential document verifies away from this system; ``verifiable`` reflects
    the credential's real state and is never faked.
    """
    credential_doc = export_portable(
        artifact.credential, request=request, grants=grants, asof=asof
    )
    doc = {
        "format": "classess.artifact.v1",
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type.value,
        "subject": artifact.subject,           # opaque canonical_uuid only
        "title": artifact.title,
        "issued_at": artifact.issued_at.astimezone(timezone.utc).isoformat(),
        "verifiable": artifact.is_verifiable,
        "credential": credential_doc,
    }
    if isinstance(artifact, Badge):
        doc["emblem_ref"] = artifact.emblem_ref
    return doc


__all__ = [
    "ArtifactType",
    "Certificate",
    "Badge",
    "issue_certificate",
    "issue_badge",
    "export_artifact",
]
