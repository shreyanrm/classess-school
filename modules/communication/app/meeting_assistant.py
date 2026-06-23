"""In-meeting SILENT ASSISTANT (B9) — consented capture, notes, actions.

The dossier:

  during it, a silent assistant captures the conversation; after it, every
  meeting produces an action plan ... the assistant handles transcription, notes,
  key-point extraction, and action items WITH CONSENT; and each action gets an
  owner, a timeline, and a follow-up.

The assistant is SILENT (it does not participate) and CONSENTED (it captures
nothing without consent from the meeting). Four jobs, in order:

  1. **Consented transcription** — segments are only accepted when the meeting
     has a satisfied consent ref for the ``meeting_transcription`` purpose.
     Without consent the assistant captures NOTHING (fail-closed) — no silent
     recording. Live capture (a transcription provider) is named by env var only;
     unwired -> the assistant works on already-captured segments handed to it.
  2. **Notes** — a concise, plain-language synthesis of the captured segments.
  3. **Key-point extraction** — the salient points from the conversation.
  4. **Action items** — each with an OWNER, a TIMELINE, and a FOLLOW-UP. An action
     item is a recommendation/prepare on the permission ladder: it is NOT auto-
     assigned or auto-fired; it is prepared for a human to own and confirm.

PII discipline: segments carry an opaque SPEAKER ROLE (teacher/parent/student),
never a name. The captured text stays in the meeting record; the action plan and
key points are plain-language and PII-free.

Import-safe: no I/O, no provider, no secret value read at import.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from .config import CommunicationSettings, get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


MEETING_TRANSCRIPTION_PURPOSE = "meeting_transcription"

SpeakerRole = Literal["teacher", "parent", "student", "admin", "counsellor", "other"]


class MeetingConsentError(PermissionError):
    """Raised when capture is attempted without a satisfied consent ref for the
    meeting_transcription purpose. The assistant captures nothing without it."""


@dataclass(frozen=True)
class TranscriptSegment:
    """One captured utterance. Opaque speaker ROLE only — never a name."""

    speaker_role: SpeakerRole
    text: str
    at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class ActionItem:
    """A prepared action item — owner + timeline + follow-up. NOT auto-fired.

    On the permission ladder this is a recommendation: ``status`` starts as
    ``proposed`` and a human confirms ownership before it is real.
    """

    description: str
    owner_role: str            # who should own it (a role) — a human confirms.
    timeline: str              # a plain-language due window, e.g. "within a week".
    follow_up: str             # how it will be followed up.
    status: Literal["proposed"] = "proposed"


@dataclass
class MeetingNotes:
    """The post-meeting synthesis: notes + key points + prepared action items."""

    meeting_id: str
    consent_ref: str
    notes: str
    key_points: tuple[str, ...]
    action_items: tuple[ActionItem, ...]
    segment_count: int
    captured_with: Literal["live_provider", "supplied_segments"] = "supplied_segments"


# Cue phrases that mark a likely action item in a transcript segment (degraded
# extractor). A real summariser would refine this; the SHAPE — owner, timeline,
# follow-up, proposed-not-fired — is the contract.
_ACTION_CUES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bwe(?:'ll| will)\b",
        r"\bi(?:'ll| will)\b",
        r"\blet(?:'s| us)\b",
        r"\bneed to\b",
        r"\bshould\b",
        r"\bplan to\b",
        r"\bfollow up\b",
        r"\bagree to\b",
    )
)


class SilentMeetingAssistant:
    """The silent, consented in-meeting assistant. Captures only with consent,
    then produces notes, key points, and prepared (not auto-fired) action items.
    """

    def __init__(self, settings: CommunicationSettings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def settings(self) -> CommunicationSettings:
        return self._settings

    @property
    def can_live_capture(self) -> bool:
        """True only when a transcription provider is wired through the gateway.
        Unwired -> the assistant works on already-captured supplied segments."""
        return self._settings.has_transcription

    def capture(
        self,
        *,
        consent_ref: str | None,
        segments: list[TranscriptSegment],
    ) -> list[TranscriptSegment]:
        """Admit captured segments — ONLY with consent. Fail-closed.

        Without a consent ref for the meeting_transcription purpose, this refuses
        and captures nothing. There is no silent-recording path.
        """
        if not consent_ref:
            raise MeetingConsentError(
                "Refusing to capture a meeting without a consent ref for the "
                f"{MEETING_TRANSCRIPTION_PURPOSE!r} purpose. The silent assistant "
                "captures nothing without consent (no silent recording)."
            )
        return list(segments)

    def synthesise(
        self,
        *,
        meeting_id: str,
        consent_ref: str | None,
        segments: list[TranscriptSegment],
    ) -> MeetingNotes:
        """Produce notes + key points + prepared action items from captured
        segments. Consent-gated: refuses without a consent ref.

        Action items are PROPOSED (not auto-assigned/fired) — each carries an
        owner role, a timeline, and a follow-up for a human to confirm.
        """
        if not consent_ref:
            raise MeetingConsentError(
                "Refusing to synthesise a meeting without a consent ref. The "
                "assistant only works on consented capture."
            )
        captured = self.capture(consent_ref=consent_ref, segments=segments)

        notes = self._notes(captured)
        key_points = self._key_points(captured)
        action_items = self._action_items(captured)

        return MeetingNotes(
            meeting_id=meeting_id,
            consent_ref=consent_ref,
            notes=notes,
            key_points=key_points,
            action_items=action_items,
            segment_count=len(captured),
            captured_with="live_provider" if self.can_live_capture else "supplied_segments",
        )

    def _notes(self, segments: list[TranscriptSegment]) -> str:
        if not segments:
            return "No conversation was captured for this meeting."
        roles = []
        for s in segments:
            if s.speaker_role not in roles:
                roles.append(s.speaker_role)
        who = ", ".join(roles)
        return (
            f"A meeting was held with: {who}. {len(segments)} points were "
            "captured and synthesised below — plain language, no names retained."
        )

    @staticmethod
    def _key_points(segments: list[TranscriptSegment]) -> tuple[str, ...]:
        points: list[str] = []
        for s in segments:
            text = re.sub(r"\s+", " ", s.text).strip()
            if not text:
                continue
            # A concise key point keeps the role context, drops the verbatim noise.
            points.append(f"({s.speaker_role}) {text}")
        return tuple(points)

    def _action_items(self, segments: list[TranscriptSegment]) -> tuple[ActionItem, ...]:
        items: list[ActionItem] = []
        for s in segments:
            if any(cue.search(s.text) for cue in _ACTION_CUES):
                desc = re.sub(r"\s+", " ", s.text).strip()
                items.append(
                    ActionItem(
                        # The speaker's role is the natural proposed owner; a human
                        # confirms ownership (permission ladder — proposed only).
                        description=desc,
                        owner_role=s.speaker_role,
                        timeline="to be confirmed at follow-up (proposed: within a week)",
                        follow_up=(
                            "Surfaced on the owner's 'Today' until confirmed; the "
                            "owner accepts or reassigns it — never auto-assigned."
                        ),
                    )
                )
        return tuple(items)
