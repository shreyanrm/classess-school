"""Device-free card-scan check (d7).

A device-free check lets a teacher confirm presence and readiness without
turning the lesson into surveillance. The teacher displays (or each learner
holds) a printed card with an opaque scan code; a quick scan records that the
learner is present and device-free for this checkpoint.

Safeguards:

- The scan code maps to an opaque ``canonical_uuid`` only. The code itself
  carries no PII and no face data. We verify the code shape and never accept a
  raw image or a face descriptor.
- The result is assistive presence evidence, NOT a punishment and NOT a grade.
- Each (session, checkpoint, subject) check is idempotent: re-scanning the same
  card updates the same record rather than stacking duplicates.
- Emitting the check is a gateway-routed event; nothing is written here.

No live keys or DB are required: results accumulate in memory and degrade to a
plain in-process tally.
"""

from __future__ import annotations

import enum
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .events import Event, EventKind, is_opaque_uuid

#: Env var (server-side only) for the HMAC key used to verify scan codes.
ENV_CARD_SCAN_KEY = "clss.classroom.prod.card_scan_hmac_key"

#: A scan code is an opaque, hyphen-grouped token. It is NOT a name or email.
_SCAN_CODE_RE = re.compile(r"^CLSS-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}$")


class CheckOutcome(str, enum.Enum):
    PRESENT_DEVICE_FREE = "present_device_free"
    CODE_INVALID = "code_invalid"


def is_valid_scan_code(code: str) -> bool:
    """Return True only for a well-formed opaque scan code."""
    return bool(isinstance(code, str) and _SCAN_CODE_RE.match(code))


@dataclass(frozen=True)
class ScanCard:
    """A printed card that resolves to one opaque subject.

    The card pairs a scan code with the subject's canonical_uuid. The pairing is
    established out of band (enrollment); this object never holds PII.
    """

    code: str
    subject_uuid: str

    def __post_init__(self) -> None:
        if not is_valid_scan_code(self.code):
            raise ValueError("scan code is malformed")
        if not is_opaque_uuid(self.subject_uuid):
            raise ValueError("subject_uuid must be an opaque canonical_uuid")


@dataclass(frozen=True)
class CheckResult:
    """The outcome of one device-free scan at a checkpoint."""

    checkpoint_id: str
    subject_uuid: Optional[str]
    outcome: CheckOutcome
    scanned_at: float = field(default_factory=time.time)

    @property
    def is_present(self) -> bool:
        return self.outcome is CheckOutcome.PRESENT_DEVICE_FREE


class DeviceFreeCheck:
    """A single device-free checkpoint within a session.

    Holds the registered cards and the set of subjects confirmed present and
    device-free. Idempotent per subject. Purely in-memory.
    """

    def __init__(self, session_id: str, checkpoint_id: Optional[str] = None):
        if not session_id:
            raise ValueError("session_id is required")
        self.session_id = session_id
        self.checkpoint_id = checkpoint_id or str(uuid.uuid4())
        self._cards: dict[str, ScanCard] = {}
        self._present: dict[str, CheckResult] = {}

    def register_card(self, card: ScanCard) -> None:
        """Pre-register a card so a scan can resolve to its subject."""
        self._cards[card.code] = card

    def scan(self, code: str) -> CheckResult:
        """Process a scan. Unknown / malformed codes are invalid, never thrown.

        The result is assistive: an invalid scan is simply not counted as
        present; it never penalizes a learner.
        """
        card = self._cards.get(code)
        if card is None or not is_valid_scan_code(code):
            return CheckResult(
                checkpoint_id=self.checkpoint_id,
                subject_uuid=None,
                outcome=CheckOutcome.CODE_INVALID,
            )
        result = CheckResult(
            checkpoint_id=self.checkpoint_id,
            subject_uuid=card.subject_uuid,
            outcome=CheckOutcome.PRESENT_DEVICE_FREE,
        )
        # Idempotent: keep the first confirmed presence for this subject.
        self._present.setdefault(card.subject_uuid, result)
        return self._present[card.subject_uuid]

    @property
    def present_uuids(self) -> frozenset[str]:
        return frozenset(self._present)

    def present_count(self) -> int:
        return len(self._present)

    def to_event(self, result: CheckResult) -> Optional[Event]:
        """Build an append-only event for a successful presence confirmation.

        Returns None for an invalid scan (nothing to record about a person).
        """
        if not result.is_present or result.subject_uuid is None:
            return None
        return Event(
            kind=EventKind.DEVICE_FREE_CHECK,
            session_id=self.session_id,
            subject_uuid=result.subject_uuid,
            payload={
                "checkpoint_id": self.checkpoint_id,
                "outcome": result.outcome.value,
                "assistive": True,
                "punitive": False,
            },
        )
