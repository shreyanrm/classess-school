"""Standards-neutral domain models for the FLUID bridge (spine A6).

These are the *internal* shapes every adapter maps TO and FROM. They are
deliberately board- and vendor-agnostic. Critically, they carry only the opaque
``canonical_uuid`` and behavioural/structural data — NEVER PII (INVARIANT 1, 2).

A raw external record (a OneRoster user, a Clever student, an Ed-Fi student)
arrives WITH PII (name, email, SIS id). The boundary rule of this package: PII
is consumed only to compute a stable, opaque *source key* and is then dropped at
the seam — it is never placed on any object that crosses a service boundary or
enters the event store. See ``mapping.py`` for the seam enforcement.

Plain stdlib dataclasses (no pydantic dependency) so the package is import-safe
and the suite runs with no third-party installs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Standards catalogue — the connectors this bridge speaks.
# ---------------------------------------------------------------------------
class Standard(str, Enum):
    LTI_1_3 = "lti-1.3"
    ONEROSTER_1_2 = "oneroster-1.2"
    XAPI = "xapi"
    CALIPER = "caliper"
    QTI = "qti"
    SCORM = "scorm"
    CLEVER = "clever"
    CLASSLINK = "classlink"
    EDFI = "ed-fi"
    CASE = "case"
    MCP = "mcp"


# ---------------------------------------------------------------------------
# Roles — the standards-neutral role we map external roles onto.
# ---------------------------------------------------------------------------
class Role(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    GUARDIAN = "guardian"
    ADMINISTRATOR = "administrator"
    STAFF = "staff"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# PII discipline — the field names that must NEVER cross the seam.
# ---------------------------------------------------------------------------
# Detection is separator-insensitive: a key is normalised (lowercased, with all
# non-alphanumerics dropped) before comparison, so ``givenName``, ``given_name``
# and ``given-name`` all collapse to the same token. The canonical set below is
# therefore stored in that normalised form.
def _norm_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


_PII_RAW = {
    "name",
    "firstName",
    "lastName",
    "lastSurname",
    "middleName",
    "givenName",
    "familyName",
    "preferredName",
    "fullName",
    "nameOfInstitution",
    "email",
    "emailAddress",
    "phone",
    "phoneNumber",
    "telephone",
    "sms",
    "address",
    "street",
    "dob",
    "dateOfBirth",
    "birthDate",
    "ssn",
    "nationalId",
    "aadhaar",
    "photo",
    "photoUrl",
    "avatar",
    "username",
    "login",
    "sisId",
    "studentNumber",
    "stateId",
    "guardianEmail",
    "guardianPhone",
    "parentEmail",
}
PII_FIELD_NAMES: frozenset[str] = frozenset(_norm_key(k) for k in _PII_RAW)

# Exemptions: a ``name`` token is benign when its PARENT key is one of these —
# e.g. an xAPI ``account.name`` is the OPAQUE identity id, not a person's name.
_NAME_PARENT_EXEMPTIONS: frozenset[str] = frozenset({"account"})


class PIILeakError(ValueError):
    """Raised when a PII field name is detected on a cross-boundary object.

    A hard backstop for INVARIANT 1/2 — behavioural/structural data carries only
    the opaque canonical_uuid, never PII.
    """


def is_pii_key(key: str, *, parent_key: str | None = None) -> bool:
    """True if ``key`` is a PII field name (separator-insensitive).

    ``name`` is exempt under an exempted parent (e.g. xAPI ``account.name``,
    which holds the opaque id, not a person's name).
    """

    token = _norm_key(key)
    if token not in PII_FIELD_NAMES:
        return False
    if token == "name" and parent_key is not None:
        if _norm_key(parent_key) in _NAME_PARENT_EXEMPTIONS:
            return False
    return True


def assert_no_pii(payload: dict[str, Any], *, where: str = "object") -> None:
    """Hard backstop: reject any dict carrying a known PII field name.

    Recurses into nested dicts/lists so a buried ``email`` cannot slip through.
    Detection is separator-insensitive (``givenName`` == ``given_name``).
    """

    def _walk(obj: Any, parent_key: str | None) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if is_pii_key(key, parent_key=parent_key):
                    raise PIILeakError(
                        f"PII field '{key}' must not cross the seam ({where})."
                    )
                _walk(value, key)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _walk(item, parent_key)

    _walk(payload, None)


# ---------------------------------------------------------------------------
# Canonical identity ref — opaque only.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CanonicalRef:
    """An opaque reference to an identity. Holds NO PII.

    ``canonical_uuid`` is resolved by the identity service from the opaque
    ``source_key`` (a salted hash of the external id). When identity is offline
    (DEGRADED), ``canonical_uuid`` is None and only the unlinkable source_key is
    present — still no PII.
    """

    source_standard: Standard
    source_key: str  # opaque, salted-hash of the external id — never the raw id
    canonical_uuid: str | None = None

    @property
    def resolved(self) -> bool:
        return self.canonical_uuid is not None


# ---------------------------------------------------------------------------
# Roster — the mapped, PII-free structural picture.
# ---------------------------------------------------------------------------
@dataclass
class MappedOrg:
    source_key: str
    kind: str  # "district" | "school" | "department" ...
    parent_source_key: str | None = None


@dataclass
class MappedEnrollment:
    person: CanonicalRef
    class_source_key: str
    role: Role
    primary: bool = False


@dataclass
class MappedClass:
    source_key: str
    org_source_key: str
    subject_code: str | None = None
    grade: str | None = None
    course_source_key: str | None = None


@dataclass
class MappedPerson:
    """A person reduced to opaque, non-identifying fields.

    Carries the CanonicalRef plus a coarse role. No name/email/etc. ever.
    """

    ref: CanonicalRef
    role: Role


@dataclass
class RosterImportResult:
    standard: Standard
    orgs: list[MappedOrg] = field(default_factory=list)
    classes: list[MappedClass] = field(default_factory=list)
    persons: list[MappedPerson] = field(default_factory=list)
    enrollments: list[MappedEnrollment] = field(default_factory=list)
    # Non-identifying counts for connector-health/observability.
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def person_count(self) -> int:
        return len(self.persons)

    def to_safe_dict(self) -> dict[str, Any]:
        """Serialise for crossing the seam. Asserts no PII before returning."""

        out = {
            "standard": self.standard.value,
            "orgs": [
                {"source_key": o.source_key, "kind": o.kind,
                 "parent_source_key": o.parent_source_key}
                for o in self.orgs
            ],
            "classes": [
                {
                    "source_key": c.source_key,
                    "org_source_key": c.org_source_key,
                    "subject_code": c.subject_code,
                    "grade": c.grade,
                    "course_source_key": c.course_source_key,
                }
                for c in self.classes
            ],
            "persons": [
                {
                    "source_key": p.ref.source_key,
                    "canonical_uuid": p.ref.canonical_uuid,
                    "role": p.role.value,
                }
                for p in self.persons
            ],
            "enrollments": [
                {
                    "source_key": e.person.source_key,
                    "canonical_uuid": e.person.canonical_uuid,
                    "class_source_key": e.class_source_key,
                    "role": e.role.value,
                    "primary": e.primary,
                }
                for e in self.enrollments
            ],
            "skipped": self.skipped,
            "warnings": list(self.warnings),
        }
        assert_no_pii(out, where="RosterImportResult")
        return out


# ---------------------------------------------------------------------------
# Outcome / competency mapping (OneRoster outcomes, CASE items).
# ---------------------------------------------------------------------------
@dataclass
class MappedOutcome:
    """An external standard/outcome mapped toward an ontology node.

    ``ontology_*`` are filled when the ontology service resolves the external
    code; otherwise the external code stands alone as an unmapped candidate.
    """

    source_standard: Standard
    external_code: str
    human_label: str  # the standard's own statement text — NOT personal data
    framework: str | None = None
    ontology_outcome_id: str | None = None
    ontology_competency_id: str | None = None
    parent_external_code: str | None = None

    @property
    def mapped(self) -> bool:
        return self.ontology_outcome_id is not None


# ---------------------------------------------------------------------------
# Activity statements — the unified xAPI/Caliper internal shape.
# ---------------------------------------------------------------------------
class Verb(str, Enum):
    """A small, standards-neutral verb set both xAPI and Caliper map onto."""

    STARTED = "started"
    COMPLETED = "completed"
    ANSWERED = "answered"
    SCORED = "scored"
    VIEWED = "viewed"
    SUBMITTED = "submitted"
    PROGRESSED = "progressed"


@dataclass
class LearningActivityStatement:
    """The bridge's internal learning-activity statement.

    The actor is an OPAQUE CanonicalRef — never an mbox/email/account-name. xAPI
    and Caliper both round-trip THROUGH this shape; the adapters translate
    actor identifiers into the opaque source_key on the way in and never emit
    PII on the way out.
    """

    actor: CanonicalRef
    verb: Verb
    object_id: str  # an activity/resource id (a URI or opaque id), not PII
    timestamp: datetime = field(default_factory=utcnow)
    object_type: str = "activity"
    result_success: bool | None = None
    result_score_scaled: float | None = None  # [-1, 1] xAPI scaled, [0,1] typical
    result_completion: bool | None = None
    context_activity_ids: list[str] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.result_score_scaled is not None:
            if not (-1.0 <= self.result_score_scaled <= 1.0):
                raise ValueError("result_score_scaled must be within [-1, 1].")
        # extensions must never smuggle PII across the seam.
        assert_no_pii(self.extensions, where="LearningActivityStatement.extensions")


# ---------------------------------------------------------------------------
# QTI — parsed assessment item.
# ---------------------------------------------------------------------------
class QTIInteraction(str, Enum):
    CHOICE = "choice"
    TEXT_ENTRY = "text-entry"
    EXTENDED_TEXT = "extended-text"
    MATCH = "match"
    UNKNOWN = "unknown"


@dataclass
class QTIChoice:
    identifier: str
    text: str
    correct: bool = False


@dataclass
class QTIItem:
    identifier: str
    title: str
    interaction: QTIInteraction
    prompt: str = ""
    choices: list[QTIChoice] = field(default_factory=list)
    correct_responses: list[str] = field(default_factory=list)
    max_score: float | None = None

    @property
    def has_answer_key(self) -> bool:
        return bool(self.correct_responses) or any(c.correct for c in self.choices)


# ---------------------------------------------------------------------------
# SCORM / xAPI-launchable package manifest.
# ---------------------------------------------------------------------------
@dataclass
class SCORMResource:
    identifier: str
    href: str
    scorm_type: str = "sco"  # "sco" | "asset"


@dataclass
class SCORMManifest:
    identifier: str
    version: str  # "1.2" | "2004" | "cmi5/xapi"
    title: str
    launch_href: str | None = None
    resources: list[SCORMResource] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Source-key derivation — opaque, salted, never reversible to the raw id.
# ---------------------------------------------------------------------------
_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_external_id(raw: str) -> str:
    """Normalise an external id for stable hashing (case/space folded)."""

    return _NON_WORD.sub("-", raw.strip().lower()).strip("-")
