"""Tests for the Vidya speech-to-speech capability (Gemini Live native audio).

Verifies, with NO key and NO SDK:
  - the capability degrades to ``provider_available=False`` (no token, no audio,
    no crash) for both the browser handshake and the server-side turn,
  - the RAW KEY is NEVER present in any returned object (defence against leaks)
    and never appears where logged,
  - the capability is registered with ``track=1`` and a LEAST-PRIVILEGE scope.

Plus, with a fake in-process minter/model (no network), it confirms:
  - an ephemeral token is returned distinct from the raw key,
  - a server-side turn passes the confidence gate only when a second model
    agrees, and stays closed (refused) when it abstains.

Import-safe, no network, no DB.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.capability_registry import default_registry
from app.config import Settings, get_settings
from app.verify import ConfidenceGate
from app.voice import (
    GEMINI_KEY_ENV_VAR as VOICE_ENV_VAR,
    GEMINI_KEY_SECRET_NAME,
    VOICE_CAPABILITY_NAME,
    VOICE_PURPOSE,
    AudioCandidate,
    EphemeralSessionResult,
    MintedToken,
    VoiceAdapter,
    register_voice_capability,
    voice_capability,
)

RAW_KEY = "super-secret-raw-gemini-key-DO-NOT-LEAK"


# ---------------------------------------------------------------------------
# Test doubles (in-process, no network)
# ---------------------------------------------------------------------------

@dataclass
class FakeMinter:
    """Mints a token derived from but DISTINCT from the raw key."""

    def mint_ephemeral_token(self, *, raw_key: str, ttl_seconds: int) -> MintedToken:
        assert raw_key == RAW_KEY  # the seam receives the raw key server-side
        return MintedToken(token="ephemeral-" + str(ttl_seconds), expires_in_seconds=ttl_seconds)


@dataclass
class FakeAudioModel:
    confidence: float = 0.97

    def respond(self, *, raw_key: str, audio_in: bytes, model_label: str) -> AudioCandidate:
        assert raw_key == RAW_KEY
        return AudioCandidate(audio_out=b"PCM_AUDIO_BYTES", confidence=self.confidence, transcript="hello there")


class AgreeingSecondModel:
    def cross_check(self, *, task_class: str, content: object) -> tuple[bool, float]:
        return (True, 0.96)


def _settings_with_key() -> Settings:
    return get_settings(env={VOICE_ENV_VAR: RAW_KEY})


def _settings_no_key() -> Settings:
    return get_settings(env={})


# ---------------------------------------------------------------------------
# Env var convention
# ---------------------------------------------------------------------------

def test_env_var_name_and_secret_name():
    assert VOICE_ENV_VAR == "CLSS_AIFABRIC_DEV_GEMINI_API_KEY"
    assert GEMINI_KEY_SECRET_NAME == "clss.aifabric.dev.gemini_api_key"


def test_settings_resolves_field_from_prefixed_env():
    s = get_settings(env={VOICE_ENV_VAR: RAW_KEY})
    assert s.gemini_api_key == RAW_KEY
    # Default is None when unset — never fabricated.
    assert get_settings(env={}).gemini_api_key is None
    # Blank/whitespace is treated as unset.
    assert get_settings(env={VOICE_ENV_VAR: "   "}).gemini_api_key is None


# ---------------------------------------------------------------------------
# Registration: track=1, least-privilege scope
# ---------------------------------------------------------------------------

def test_voice_capability_registered_in_default_registry_track1():
    reg = default_registry()
    cap = reg.require(VOICE_CAPABILITY_NAME)
    assert cap.track == 1
    assert cap.requires_verification is True


def test_voice_capability_least_privilege_scope():
    cap = voice_capability()
    assert cap.least_privilege.purpose == VOICE_PURPOSE
    # Minimal scope: only the opaque conversation handle, nothing wider, no PII.
    assert cap.least_privilege.data_scopes == ("conversation.context",)
    # A single purpose code, and a narrow scope set.
    assert len(cap.least_privilege.data_scopes) == 1


def test_register_voice_capability_on_fresh_registry():
    from app.capability_registry import CapabilityRegistry

    reg = CapabilityRegistry()
    cap = register_voice_capability(reg)
    assert reg.require(VOICE_CAPABILITY_NAME) is cap
    assert cap.track == 1
    # It is in the track-1 set, never track 2.
    assert cap in reg.for_track(1)
    assert cap not in reg.for_track(2)


# ---------------------------------------------------------------------------
# Degrade gracefully: no key / no SDK => provider_available=False, no token
# ---------------------------------------------------------------------------

def test_mint_browser_session_no_key_is_unavailable_no_token():
    # No key AND no minter seam => unavailable, never fabricates a token.
    adapter = VoiceAdapter(settings=_settings_no_key(), token_minter=None, audio_model=None)
    res = adapter.mint_browser_session()
    assert res.provider_available is False
    assert res.token is None
    assert res.expires_in_seconds is None
    assert res.track == 1
    assert VOICE_ENV_VAR in (res.detail or "")


def test_mint_browser_session_key_present_but_no_sdk_is_unavailable():
    # Key set but SDK absent => still unavailable, no token fabricated.
    adapter = VoiceAdapter(settings=_settings_with_key(), token_minter=None, audio_model=None)
    res = adapter.mint_browser_session()
    assert res.provider_available is False
    assert res.token is None


def test_respond_speech_to_speech_no_provider_refuses_no_crash():
    adapter = VoiceAdapter(settings=_settings_no_key(), token_minter=None, audio_model=None)
    res = adapter.respond_speech_to_speech(audio_in=b"learner-audio")
    assert res.provider_available is False
    assert res.refused is True
    assert res.audio_out is None
    assert res.transcript is None
    assert res.track == 1


# ---------------------------------------------------------------------------
# THE RAW KEY IS NEVER PRESENT in any returned object (no-leak invariant)
# ---------------------------------------------------------------------------

def _assert_no_raw_key(obj: object) -> None:
    """The raw key must not appear anywhere in the object's repr/values."""
    text = repr(obj)
    assert RAW_KEY not in text, f"raw key leaked into {type(obj).__name__}"


def test_minted_token_is_not_the_raw_key():
    adapter = VoiceAdapter(
        settings=_settings_with_key(), token_minter=FakeMinter(), audio_model=None,
    )
    res = adapter.mint_browser_session(ttl_seconds=90)
    assert res.provider_available is True
    assert res.token is not None
    assert res.token != RAW_KEY
    assert res.expires_in_seconds == 90
    _assert_no_raw_key(res)


def test_raw_key_never_in_any_returned_object():
    adapter = VoiceAdapter(
        settings=_settings_with_key(),
        token_minter=FakeMinter(),
        audio_model=FakeAudioModel(),
        second_model=AgreeingSecondModel(),
    )
    session = adapter.mint_browser_session()
    turn = adapter.respond_speech_to_speech(audio_in=b"learner-audio")
    for obj in (session, turn, turn.verification):
        _assert_no_raw_key(obj)


def test_provider_rejects_token_equal_to_raw_key():
    # A misbehaving provider that echoes the raw key must NOT leak it.
    class LeakyMinter:
        def mint_ephemeral_token(self, *, raw_key: str, ttl_seconds: int) -> MintedToken:
            return MintedToken(token=raw_key, expires_in_seconds=ttl_seconds)

    adapter = VoiceAdapter(
        settings=_settings_with_key(), token_minter=LeakyMinter(), audio_model=None,
    )
    res = adapter.mint_browser_session()
    assert res.provider_available is False
    assert res.token is None
    _assert_no_raw_key(res)


def test_unavailable_result_cannot_carry_a_token():
    import pytest

    with pytest.raises(ValueError):
        EphemeralSessionResult(
            provider_available=False,
            token="sneaky",
            expires_in_seconds=10,
            model_label="x",
            track=1,
            capability=VOICE_CAPABILITY_NAME,
        )


# ---------------------------------------------------------------------------
# Confidence gate on the server-side turn
# ---------------------------------------------------------------------------

def test_turn_served_when_second_model_agrees():
    adapter = VoiceAdapter(
        settings=_settings_with_key(),
        token_minter=FakeMinter(),
        audio_model=FakeAudioModel(),
        second_model=AgreeingSecondModel(),
        gate=ConfidenceGate(threshold=0.85),
    )
    res = adapter.respond_speech_to_speech(audio_in=b"learner-audio")
    assert res.provider_available is True
    assert res.refused is False
    assert res.audio_out == b"PCM_AUDIO_BYTES"
    assert res.verification is not None and res.verification.served is True


def test_turn_withheld_when_second_model_abstains():
    # Default second model abstains => gate closed even with a live provider.
    adapter = VoiceAdapter(
        settings=_settings_with_key(),
        token_minter=FakeMinter(),
        audio_model=FakeAudioModel(),
    )
    res = adapter.respond_speech_to_speech(audio_in=b"learner-audio")
    assert res.provider_available is True
    assert res.refused is True
    assert res.audio_out is None
    assert res.verification is not None and res.verification.served is False
    assert "second-model" in (res.detail or "").lower()


def test_orchestrator_can_route_voice_capability():
    # The capability is wired end-to-end: registry + router agree on the class.
    from app.orchestrator import Orchestrator, Intent

    orch = Orchestrator()
    intent = Intent(
        request_id="11111111-1111-1111-1111-111111111111",
        capability=VOICE_CAPABILITY_NAME,
        purpose=VOICE_PURPOSE,
        payload={},
    )
    res = orch.handle(intent)
    # No provider adapter + no deterministic handle => well-formed refusal,
    # never a crash, never fabricated audio.
    assert res.refused is True
    assert res.provider_available is False
    assert res.track == 1
