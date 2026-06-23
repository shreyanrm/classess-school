"""The identity + ontology mapping seam (spine A6).

This is where raw external records (which DO carry PII) are translated into the
PII-free internal shapes. Two responsibilities:

1. IDENTITY — turn an external person id into an opaque, salted ``source_key``
   and (when identity is online) resolve the random ``canonical_uuid``. The raw
   id and any name/email are consumed here and DROPPED — they never appear on a
   returned object (INVARIANT 1, 2).

2. ONTOLOGY — map external outcome/standard codes (OneRoster outcomes, CASE
   items) toward ontology nodes. The mapping is *proposed*; trust is conferred
   by the ontology steward downstream (curriculum is mapped, never assumed).

The seam NEVER calls a provider directly — any identity/ontology resolution goes
THROUGH THE GATEWAY via an injected resolver. With no resolver (DEGRADED), the
opaque source_key still flows and stays unlinkable to a person.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any, Callable, Protocol

from .config import ENV_PREFIX
from .models import (
    CanonicalRef,
    MappedOutcome,
    Role,
    Standard,
    assert_no_pii,
    normalize_external_id,
)

# Env var NAME holding the per-deployment hashing salt (INVARIANT 4). The VALUE
# is read by name and never logged. clss.integration.dev.source_key_salt
SOURCE_KEY_SALT_ENV = ENV_PREFIX + "SOURCE_KEY_SALT"

# A clearly-labelled, NON-SECRET dev salt used only in DEGRADED mode so the
# pipeline is exercisable offline. It is NOT a credential and protects nothing
# in production — production MUST set the salt env var.
_DEV_SALT = "clss-integration-dev-salt-not-a-secret"


def _salt() -> bytes:
    return (os.environ.get(SOURCE_KEY_SALT_ENV) or _DEV_SALT).encode("utf-8")


def derive_source_key(standard: Standard, raw_external_id: str) -> str:
    """Derive an opaque, stable, salted source key from an external id.

    HMAC-SHA256 over (standard, normalized id). One-way: the raw id cannot be
    recovered from the key, and the key is unlinkable to a person without the
    identity vault. The same external id always yields the same key (stable
    re-import), but two deployments with different salts never collide.
    """

    if not raw_external_id or not raw_external_id.strip():
        raise ValueError("external id must be non-empty to derive a source key.")
    norm = normalize_external_id(raw_external_id)
    msg = f"{standard.value}:{norm}".encode("utf-8")
    digest = hmac.new(_salt(), msg, hashlib.sha256).hexdigest()
    return f"{standard.value}:{digest[:32]}"


# ---------------------------------------------------------------------------
# Resolver protocols — injected, always THROUGH THE GATEWAY in production.
# ---------------------------------------------------------------------------
class IdentityResolver(Protocol):
    """Resolves an opaque source_key to a random canonical_uuid.

    The real implementation calls the identity service through the gateway. It
    receives ONLY the opaque source_key — never PII. Returns None if no identity
    is linked yet (or in DEGRADED mode).
    """

    def resolve(self, source_key: str) -> str | None: ...


class OntologyResolver(Protocol):
    """Maps an external outcome/standard code toward ontology node ids.

    Returns a dict with optional keys ``outcome_id`` / ``competency_id``. The
    real implementation calls the ontology service through the gateway. None of
    the inputs are PII.
    """

    def resolve_outcome(self, framework: str | None, code: str) -> dict[str, str] | None: ...


# ---------------------------------------------------------------------------
# Identity mapping
# ---------------------------------------------------------------------------
def map_identity(
    standard: Standard,
    raw_external_id: str,
    *,
    resolver: IdentityResolver | None = None,
) -> CanonicalRef:
    """Produce an opaque CanonicalRef from an external person id.

    The raw id is consumed only to derive the source_key; it is not stored on
    the returned ref. With a resolver online, ``canonical_uuid`` is filled;
    otherwise it stays None and only the unlinkable source_key flows.
    """

    source_key = derive_source_key(standard, raw_external_id)
    canonical_uuid = resolver.resolve(source_key) if resolver is not None else None
    return CanonicalRef(
        source_standard=standard,
        source_key=source_key,
        canonical_uuid=canonical_uuid,
    )


# Standards-neutral role normalisation. External role strings are folded onto the
# internal Role enum; anything unrecognised becomes UNKNOWN (never dropped).
_ROLE_ALIASES: dict[str, Role] = {
    "student": Role.STUDENT,
    "learner": Role.STUDENT,
    "teacher": Role.TEACHER,
    "instructor": Role.TEACHER,
    "faculty": Role.TEACHER,
    "guardian": Role.GUARDIAN,
    "parent": Role.GUARDIAN,
    "relative": Role.GUARDIAN,
    "administrator": Role.ADMINISTRATOR,
    "admin": Role.ADMINISTRATOR,
    "principal": Role.ADMINISTRATOR,
    "districtadministrator": Role.ADMINISTRATOR,
    "siteadministrator": Role.ADMINISTRATOR,
    "staff": Role.STAFF,
    "aide": Role.STAFF,
    "proctor": Role.STAFF,
}


def normalize_role(raw_role: str | None) -> Role:
    if not raw_role:
        return Role.UNKNOWN
    key = raw_role.strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    return _ROLE_ALIASES.get(key, Role.UNKNOWN)


def strip_pii(record: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of an external record with PII keys removed.

    Used by adapters to log/inspect a raw record without leaking PII. Recurses
    one level into nested dicts.
    """

    from .models import is_pii_key

    def _clean(obj: Any, parent_key: str | None) -> Any:
        if isinstance(obj, dict):
            return {
                k: _clean(v, k)
                for k, v in obj.items()
                if not is_pii_key(k, parent_key=parent_key)
            }
        if isinstance(obj, list):
            return [_clean(i, parent_key) for i in obj]
        return obj

    return _clean(record, None)


# ---------------------------------------------------------------------------
# Ontology mapping
# ---------------------------------------------------------------------------
def map_outcome(
    standard: Standard,
    external_code: str,
    human_label: str,
    *,
    framework: str | None = None,
    parent_external_code: str | None = None,
    resolver: OntologyResolver | None = None,
) -> MappedOutcome:
    """Map an external outcome/standard code toward ontology node ids.

    With a resolver online the ontology ids are proposed; otherwise the external
    code stands as an unmapped candidate awaiting the steward's confirmation.
    """

    outcome_id = competency_id = None
    if resolver is not None:
        hit = resolver.resolve_outcome(framework, external_code)
        if hit:
            outcome_id = hit.get("outcome_id")
            competency_id = hit.get("competency_id")
    return MappedOutcome(
        source_standard=standard,
        external_code=external_code,
        human_label=human_label,
        framework=framework,
        parent_external_code=parent_external_code,
        ontology_outcome_id=outcome_id,
        ontology_competency_id=competency_id,
    )


__all__ = [
    "SOURCE_KEY_SALT_ENV",
    "IdentityResolver",
    "OntologyResolver",
    "derive_source_key",
    "map_identity",
    "normalize_role",
    "strip_pii",
    "map_outcome",
]
