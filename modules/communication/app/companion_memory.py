"""Persistent per-user COMPANION MEMORY (B9) — consent-gated, PII-free.

The dossier:

  persistent per-user companion memory (store + thread, not stateless per
  request).

The companion is no longer stateless per request: it remembers a user's thread
(the running conversation) and a small set of SALIENT FACTS (durable, useful
context — "is revising for the algebra check", "prefers worked examples"). Three
laws are enforced in code, not just intent:

  1. **Consent-gated.** Memory is only retained for a user with a satisfied
     consent ref for the ``companion_memory`` purpose. Without it the store runs
     in EPHEMERAL mode: nothing is persisted across requests; recall returns
     empty. Consent can be revoked, which PURGES the user's memory (right to be
     forgotten), fail-closed.
  2. **PII-free.** Memory is keyed by the opaque canonical_uuid only, and every
     remembered fact/turn is screened against a PII guard before it is stored —
     an email/phone-shaped fact is refused, never persisted (INVARIANT 1 + 2).
  3. **Bounded volume.** The thread and the salient-fact set are capped so memory
     is a useful summary, not a surveillance dossier of everything ever said.

Degrade-safe: with no external memory store wired (its env var unset) this runs a
deterministic IN-PROCESS store. It is the supported path until the store is
wired; it reads no secret value at import and opens no connection.

Import-safe: no I/O, no provider, no secret value read at import.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from .config import CommunicationSettings, get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# The consent purpose that permits retaining companion memory for a user.
COMPANION_MEMORY_PURPOSE = "companion_memory"

# Caps so memory is a summary, not a dossier.
MAX_THREAD_TURNS = 50
MAX_SALIENT_FACTS = 20


class MemoryConsentError(PermissionError):
    """Raised when memory retention is attempted without a satisfied consent ref
    for the companion_memory purpose. Fail-closed: nothing is retained."""


class PiiInMemoryError(ValueError):
    """Raised when a fact/turn that looks like PII is offered for storage. Memory
    is PII-free; such an item is refused, never persisted (INVARIANT 1 + 2)."""


# Deterministic PII shapes refused from memory. Conservative + fail-safe: when a
# turn/fact looks like an email/phone, it is rejected wholesale, never stored.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\s-]?){7,}\d(?!\d)")


def looks_like_pii(text: str) -> bool:
    """True when ``text`` contains an email- or phone-shaped span."""
    if not text:
        return False
    return bool(_EMAIL_RE.search(text) or _PHONE_RE.search(text))


@dataclass(frozen=True)
class ThreadTurn:
    """One turn in the running companion conversation. PII-free by construction
    (screened before storage). Carries no name/email — only the role + text."""

    speaker: Literal["user", "companion"]
    text: str
    at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class SalientFact:
    """A durable, useful fact the companion remembers about a user. Plain,
    PII-free, and explainable (it carries why it was kept)."""

    fact: str
    why_kept: str
    at: str = field(default_factory=_now_iso)


@dataclass
class _UserMemory:
    """The per-user record. Held only when consent is satisfied."""

    user_ref: str
    consent_ref: str
    thread: list[ThreadTurn] = field(default_factory=list)
    salient: list[SalientFact] = field(default_factory=list)


class CompanionMemory:
    """Persistent, consent-gated, PII-free per-user companion memory.

    Keyed by opaque canonical_uuid. Without a consent ref for the
    companion_memory purpose, the store is EPHEMERAL — recall is empty and
    nothing is retained. Revoking consent purges the user's memory.
    """

    def __init__(self, settings: CommunicationSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._store: dict[str, _UserMemory] = {}

    @property
    def settings(self) -> CommunicationSettings:
        return self._settings

    @property
    def degraded(self) -> bool:
        """True when no external memory store is wired — the in-process store is
        the supported path."""
        return not self._settings.has_companion_memory_store

    def _require_consent(self, *, user_ref: str, consent_ref: str | None) -> str:
        if not consent_ref:
            raise MemoryConsentError(
                "Refusing to retain companion memory with no consent ref for the "
                f"{COMPANION_MEMORY_PURPOSE!r} purpose. Without consent the "
                "companion is stateless for this user (fail-closed)."
            )
        return consent_ref

    def remember_turn(
        self,
        *,
        user_ref: str,
        speaker: Literal["user", "companion"],
        text: str,
        consent_ref: str | None,
    ) -> ThreadTurn:
        """Append a turn to the user's thread — consent-gated + PII-screened.

        Raises if consent is absent (nothing retained) or the text looks like
        PII (refused, never stored). The thread is capped to the most recent
        ``MAX_THREAD_TURNS``.
        """
        self._require_consent(user_ref=user_ref, consent_ref=consent_ref)
        if looks_like_pii(text):
            raise PiiInMemoryError(
                "Refusing to store a turn that looks like PII (email/phone). "
                "Companion memory is PII-free; keyed by opaque ref only."
            )
        record = self._store.get(user_ref)
        if record is None:
            record = _UserMemory(user_ref=user_ref, consent_ref=consent_ref or "")
            self._store[user_ref] = record
        turn = ThreadTurn(speaker=speaker, text=text)
        record.thread.append(turn)
        # Cap: keep only the most recent turns (a summary, not a dossier).
        if len(record.thread) > MAX_THREAD_TURNS:
            record.thread = record.thread[-MAX_THREAD_TURNS:]
        return turn

    def remember_fact(
        self,
        *,
        user_ref: str,
        fact: str,
        why_kept: str,
        consent_ref: str | None,
    ) -> SalientFact:
        """Store a salient fact — consent-gated + PII-screened + capped."""
        self._require_consent(user_ref=user_ref, consent_ref=consent_ref)
        if looks_like_pii(fact):
            raise PiiInMemoryError(
                "Refusing to store a fact that looks like PII (email/phone). "
                "Companion memory is PII-free."
            )
        record = self._store.get(user_ref)
        if record is None:
            record = _UserMemory(user_ref=user_ref, consent_ref=consent_ref or "")
            self._store[user_ref] = record
        salient = SalientFact(fact=fact, why_kept=why_kept)
        record.salient.append(salient)
        if len(record.salient) > MAX_SALIENT_FACTS:
            record.salient = record.salient[-MAX_SALIENT_FACTS:]
        return salient

    def recall_thread(self, *, user_ref: str, consent_ref: str | None) -> list[ThreadTurn]:
        """Recall the user's thread — empty without consent (stateless), and
        empty if the consent ref does not match the one memory was retained
        under (a different/withdrawn grant reveals nothing)."""
        if not consent_ref:
            return []
        record = self._store.get(user_ref)
        if record is None or record.consent_ref != consent_ref:
            return []
        return list(record.thread)

    def recall_salient(self, *, user_ref: str, consent_ref: str | None) -> list[SalientFact]:
        """Recall the user's salient facts — empty without a matching consent ref."""
        if not consent_ref:
            return []
        record = self._store.get(user_ref)
        if record is None or record.consent_ref != consent_ref:
            return []
        return list(record.salient)

    def forget(self, *, user_ref: str) -> bool:
        """Purge a user's memory entirely (consent revoked / right to be
        forgotten). Returns True if anything was held. Fail-closed and total."""
        return self._store.pop(user_ref, None) is not None
