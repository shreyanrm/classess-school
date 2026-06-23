"""The LIVE child-safety classifier (Gemini, Track 1) bound to the subsystem.

Verifies, with NO live call (a fake in-process provider, or no key at all):

  * with NO key the subsystem runs on the deterministic floor: a crisis still
    ESCALATES to a qualified human, harassment still FLAGS — the live model can
    never silence the on-device screen,
  * the live provider IS invoked (by name) when a key is present, and can only
    ADD signals (a model that says "safe" cannot suppress a deterministic crisis),
  * a provider error / malformed response never silences a crisis,
  * escalation + route shapes are correct (PENDING escalation, privileged audit),
  * the RAW KEY and the screened TEXT never appear in any result (no PII / no leak),
  * the env-var convention matches the Gemini Track 1 secret name.

Import-safe, offline, no DB, no network.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from app.audit import InMemoryAuditLog
from app.child_safety import ChildSafetySubsystem, UnmonitoredChannelError
from app.models import AuditQuery, EscalationStatus, SafetyVerdict, new_id
from app.safety_classifier import (
    GEMINI_KEY_ENV_VAR,
    GEMINI_KEY_SECRET_NAME,
    TRACK_ID,
    ClassifierVerdict,
    GeminiModerationProvider,
    LiveSafetyClassifier,
    _parse_gemini_response,
    make_safety_classifier,
)

RAW_KEY = "super-secret-raw-gemini-key-DO-NOT-LEAK"
CRISIS_TEXT = "sometimes i want to kill myself"
HARASSMENT_TEXT = "you are such an idiot"


# ---------------------------------------------------------------------------
# Test doubles (in-process, no network)
# ---------------------------------------------------------------------------


@dataclass
class RecordingProvider:
    """A fake provider that records it was called and returns a fixed verdict.

    Asserts it receives the raw key server-side (the seam contract) and never
    leaks it onward.
    """

    verdict: ClassifierVerdict
    calls: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.calls = []

    def classify(self, *, raw_key: str, model_label: str, text: str) -> ClassifierVerdict:
        assert raw_key == RAW_KEY  # the seam receives the raw key server-side
        self.calls.append(text)
        return self.verdict


class ExplodingProvider:
    """A provider that errors — must never silence the deterministic floor."""

    def __init__(self) -> None:
        self.calls = 0

    def classify(self, *, raw_key: str, model_label: str, text: str) -> ClassifierVerdict:
        self.calls += 1
        raise RuntimeError("provider unavailable")


def _sub_with(classifier) -> tuple[ChildSafetySubsystem, InMemoryAuditLog]:
    audit = InMemoryAuditLog()
    sub = ChildSafetySubsystem(audit, classifier=classifier)
    return sub, audit


# ---------------------------------------------------------------------------
# Env-var convention (Track 1 Gemini secret, read by NAME)
# ---------------------------------------------------------------------------


def test_env_var_and_secret_name_and_track():
    assert GEMINI_KEY_ENV_VAR == "CLSS_AIFABRIC_DEV_GEMINI_API_KEY"
    assert GEMINI_KEY_SECRET_NAME == "clss.aifabric.dev.gemini_api_key"
    assert TRACK_ID == 1


def test_classifier_reports_unavailable_with_no_key():
    clf = LiveSafetyClassifier(provider=RecordingProvider(
        verdict=ClassifierVerdict((), False, 0.0)), env={})
    assert clf.live_available() is False
    assert "UNAVAILABLE" in clf.name
    assert GEMINI_KEY_ENV_VAR in clf.name


def test_classifier_reports_available_with_key_and_provider():
    clf = LiveSafetyClassifier(
        provider=RecordingProvider(verdict=ClassifierVerdict((), False, 0.0)),
        env={GEMINI_KEY_ENV_VAR: RAW_KEY},
    )
    assert clf.live_available() is True
    assert "gemini-live-classifier" in clf.name


# ---------------------------------------------------------------------------
# NO KEY: the deterministic floor still escalates a crisis and flags harassment
# ---------------------------------------------------------------------------


def test_no_key_crisis_still_escalates_to_a_human():
    clf = make_safety_classifier(env={})  # no key -> deterministic floor alone
    sub, audit = _sub_with(clf)
    sub.register_surface("companion.chat")
    tenant = new_id()
    a = asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                               text=CRISIS_TEXT, tenant_id=tenant))
    assert a.crisis is True
    assert a.verdict is SafetyVerdict.CRISIS
    pending = sub.pending_escalations()
    assert len(pending) == 1 and pending[0].status is EscalationStatus.PENDING
    esc_audit = asyncio.run(audit.query(AuditQuery(action="child_safety.escalate")))
    assert len(esc_audit) == 1 and esc_audit[0].privileged is True


def test_no_key_harassment_still_flags():
    clf = make_safety_classifier(env={})
    sub, _ = _sub_with(clf)
    sub.register_surface("class.discussion")
    a = asyncio.run(sub.assess(surface="class.discussion", canonical_uuid=new_id(),
                               text=HARASSMENT_TEXT, tenant_id=new_id()))
    assert a.verdict in (SafetyVerdict.FLAG, SafetyVerdict.BLOCK)
    assert "harassment" in a.categories


def test_no_key_does_not_invoke_a_provider():
    # No key => the live provider is never called (no network attempt).
    prov = RecordingProvider(verdict=ClassifierVerdict((), False, 0.0))
    clf = LiveSafetyClassifier(provider=prov, env={})
    clf.classify(CRISIS_TEXT)
    assert prov.calls == []  # never reached the provider


# ---------------------------------------------------------------------------
# KEY PRESENT: the live classifier is invoked, and can only ADD signals
# ---------------------------------------------------------------------------


def test_live_classifier_is_invoked_when_key_present():
    prov = RecordingProvider(verdict=ClassifierVerdict(("hate",), False, 0.9))
    clf = LiveSafetyClassifier(provider=prov, env={GEMINI_KEY_ENV_VAR: RAW_KEY})
    cats, crisis, conf = clf.classify("benign text here")
    assert prov.calls == ["benign text here"]  # the provider WAS invoked
    assert "hate" in cats  # the live signal was added


def test_live_model_cannot_silence_a_deterministic_crisis():
    # Provider claims "safe", but the deterministic floor catches the crisis:
    # crisis MUST survive (never silenced).
    prov = RecordingProvider(verdict=ClassifierVerdict((), False, 0.1))
    clf = LiveSafetyClassifier(provider=prov, env={GEMINI_KEY_ENV_VAR: RAW_KEY})
    sub, _ = _sub_with(clf)
    sub.register_surface("companion.chat")
    a = asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                               text=CRISIS_TEXT, tenant_id=new_id()))
    assert prov.calls == [CRISIS_TEXT]
    assert a.crisis is True
    assert a.verdict is SafetyVerdict.CRISIS


def test_live_model_can_escalate_text_the_floor_missed():
    # Subtle crisis the lexicon misses, but the model catches: it ESCALATES.
    subtle = "i don't want to be here anymore and nobody would notice"
    prov = RecordingProvider(verdict=ClassifierVerdict(("self-harm",), True, 0.92))
    clf = LiveSafetyClassifier(provider=prov, env={GEMINI_KEY_ENV_VAR: RAW_KEY})
    sub, audit = _sub_with(clf)
    sub.register_surface("companion.chat")
    a = asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                               text=subtle, tenant_id=new_id()))
    assert a.crisis is True and a.verdict is SafetyVerdict.CRISIS
    assert "self-harm" in a.categories
    assert len(sub.pending_escalations()) == 1


def test_provider_error_never_silences_a_crisis():
    prov = ExplodingProvider()
    clf = LiveSafetyClassifier(provider=prov, env={GEMINI_KEY_ENV_VAR: RAW_KEY})
    sub, _ = _sub_with(clf)
    sub.register_surface("companion.chat")
    a = asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                               text=CRISIS_TEXT, tenant_id=new_id()))
    assert prov.calls == 1  # the provider WAS tried
    # ...but its failure fell back to the deterministic floor — crisis stands.
    assert a.crisis is True and a.verdict is SafetyVerdict.CRISIS


# ---------------------------------------------------------------------------
# No unmonitored channel still holds with the live classifier wired
# ---------------------------------------------------------------------------


def test_unmonitored_surface_still_refused_with_live_classifier():
    clf = make_safety_classifier(env={GEMINI_KEY_ENV_VAR: RAW_KEY},
                                 provider=RecordingProvider(
                                     verdict=ClassifierVerdict((), False, 0.0)))
    sub, _ = _sub_with(clf)
    with pytest.raises(UnmonitoredChannelError):
        asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                               text="hello", tenant_id=new_id()))


# ---------------------------------------------------------------------------
# NO PII / NO KEY LEAK in any result
# ---------------------------------------------------------------------------


def _assert_clean(obj: object, *, text: str) -> None:
    rep = repr(obj)
    assert RAW_KEY not in rep, f"raw key leaked into {type(obj).__name__}"
    assert text not in rep, f"screened text leaked into {type(obj).__name__}"


def test_raw_key_and_text_never_in_result_or_audit():
    prov = RecordingProvider(verdict=ClassifierVerdict(("self-harm",), True, 0.95))
    clf = LiveSafetyClassifier(provider=prov, env={GEMINI_KEY_ENV_VAR: RAW_KEY})
    sub, audit = _sub_with(clf)
    sub.register_surface("companion.chat")
    tenant = new_id()
    a = asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                               text=CRISIS_TEXT, tenant_id=tenant))
    esc = sub.pending_escalations()[0]
    records = asyncio.run(audit.query(AuditQuery(tenant_id=tenant)))
    for obj in (a, esc, *records):
        _assert_clean(obj, text=CRISIS_TEXT)
    # The classifier name carries no key either.
    assert RAW_KEY not in clf.name


# ---------------------------------------------------------------------------
# Gemini response parsing (no network — pure parse of a sample body)
# ---------------------------------------------------------------------------


def test_parse_gemini_response_maps_closed_set():
    body = {
        "candidates": [
            {"content": {"parts": [
                {"text": '{"categories": ["harassment", "made-up", "self-harm"],'
                         ' "crisis": true, "confidence": 0.88}'}
            ]}}
        ]
    }
    v = _parse_gemini_response(body)
    assert v.crisis is True
    assert "harassment" in v.categories and "self-harm" in v.categories
    assert "made-up" not in v.categories  # clamped to the known set
    assert v.confidence == 0.88


def test_parse_gemini_response_clamps_confidence_and_rejects_empty():
    body = {"candidates": [{"content": {"parts": [
        {"text": '{"categories": [], "crisis": false, "confidence": 9.0}'}]}}]}
    assert _parse_gemini_response(body).confidence == 1.0
    with pytest.raises((ValueError, Exception)):
        _parse_gemini_response({"candidates": []})


def test_gemini_provider_is_constructible_without_network():
    # Constructing the real provider must not require httpx or a network.
    prov = GeminiModerationProvider(timeout_seconds=3.0)
    assert prov is not None
