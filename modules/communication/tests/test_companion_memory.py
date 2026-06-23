"""Companion memory: consent-gated, PII-free, capped, and purged on revocation.
A companion wired to memory remembers a thread across requests with consent."""

from __future__ import annotations

import pytest

from app.companion import Companion, CompanionRole
from app.companion_memory import (
    CompanionMemory,
    MAX_THREAD_TURNS,
    MemoryConsentError,
    PiiInMemoryError,
    looks_like_pii,
)
from app.config import CommunicationSettings


USER = "9999aaaa-0000-4000-8000-000000000020"
CONSENT = "cccccccc-0000-4000-8000-000000000020"


def _memory() -> CompanionMemory:
    return CompanionMemory(CommunicationSettings())


def test_memory_without_consent_is_stateless():
    mem = _memory()
    with pytest.raises(MemoryConsentError):
        mem.remember_turn(user_ref=USER, speaker="user", text="hello", consent_ref=None)
    # Recall without consent is empty (stateless), never raises.
    assert mem.recall_thread(user_ref=USER, consent_ref=None) == []


def test_consented_memory_persists_thread_across_requests():
    mem = _memory()
    mem.remember_turn(user_ref=USER, speaker="user", text="first", consent_ref=CONSENT)
    mem.remember_turn(user_ref=USER, speaker="companion", text="reply", consent_ref=CONSENT)
    thread = mem.recall_thread(user_ref=USER, consent_ref=CONSENT)
    assert [t.text for t in thread] == ["first", "reply"]


def test_pii_shaped_memory_is_refused():
    mem = _memory()
    assert looks_like_pii("reach me at a@b.com")
    assert looks_like_pii("call 555-123-4567 please")
    with pytest.raises(PiiInMemoryError):
        mem.remember_turn(
            user_ref=USER, speaker="user", text="email me a@b.com", consent_ref=CONSENT
        )
    with pytest.raises(PiiInMemoryError):
        mem.remember_fact(
            user_ref=USER, fact="phone 555-123-4567", why_kept="x", consent_ref=CONSENT
        )


def test_salient_facts_are_recalled_with_matching_consent_only():
    mem = _memory()
    mem.remember_fact(
        user_ref=USER, fact="revising for the algebra check",
        why_kept="recurring topic", consent_ref=CONSENT,
    )
    assert len(mem.recall_salient(user_ref=USER, consent_ref=CONSENT)) == 1
    # A different consent ref reveals nothing.
    assert mem.recall_salient(user_ref=USER, consent_ref="other") == []


def test_revoking_consent_purges_memory():
    mem = _memory()
    mem.remember_turn(user_ref=USER, speaker="user", text="x", consent_ref=CONSENT)
    assert mem.forget(user_ref=USER) is True
    assert mem.recall_thread(user_ref=USER, consent_ref=CONSENT) == []


def test_thread_is_capped_to_a_summary_not_a_dossier():
    mem = _memory()
    for i in range(MAX_THREAD_TURNS + 10):
        mem.remember_turn(user_ref=USER, speaker="user", text=f"t{i}", consent_ref=CONSENT)
    thread = mem.recall_thread(user_ref=USER, consent_ref=CONSENT)
    assert len(thread) == MAX_THREAD_TURNS


def test_companion_with_memory_remembers_only_with_consent():
    mem = _memory()
    companion = Companion(
        role=CompanionRole.STUDENT, settings=CommunicationSettings(), memory=mem
    )
    # No consent ref -> stateless.
    companion.respond("I am stuck", writer_ref=USER)
    assert mem.recall_thread(user_ref=USER, consent_ref=CONSENT) == []
    # With consent -> the turn pair is remembered.
    companion.respond("I am stuck on fractions", writer_ref=USER, consent_ref=CONSENT)
    thread = mem.recall_thread(user_ref=USER, consent_ref=CONSENT)
    assert any(t.speaker == "user" for t in thread)
    assert any(t.speaker == "companion" for t in thread)


def test_companion_does_not_remember_a_flagged_crisis_turn():
    mem = _memory()
    companion = Companion(settings=CommunicationSettings(), memory=mem)
    reply = companion.respond("i want to die", writer_ref=USER, consent_ref=CONSENT)
    assert reply.handed_off is True
    # A crisis turn is a safeguarding matter for a human, not companion memory.
    assert mem.recall_thread(user_ref=USER, consent_ref=CONSENT) == []
