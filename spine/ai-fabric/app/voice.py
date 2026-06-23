"""Vidya speech-to-speech capability (A4) — Gemini Live native audio.

A Track 1 (external LLM routing) voice capability: audio in -> audio out, plus a
browser handshake that mints an EPHEMERAL, short-lived session token so the raw
provider key NEVER leaves the server.

INVARIANT 4 — SECRETS ARE ENV-ONLY, READ BY NAME, NEVER HARDCODED, NEVER
EXPOSED TO THE BROWSER. The raw provider key is read by NAME from the
environment (secret ``clss.aifabric.dev.gemini_api_key`` -> OS env
``CLSS_AIFABRIC_DEV_GEMINI_API_KEY``) via :mod:`app.config`. It is used ONLY to
ask the provider to MINT an ephemeral token; the raw key is never placed in any
returned object, never logged, and never sent to a client. A browser opens a
Live session with the ephemeral token alone.

INVARIANT 7 — THE CONFIDENCE GATE. The server-side speech-to-speech invocation
runs behind the same generate-and-verify gate as every other served capability:
an audio response is SERVED only when deterministic checks pass, an independent
second model agrees, and confidence clears the threshold. With no live provider
the gate stays closed (degrades safely, never fabricates audio).

INVARIANT 8 — THE PERMISSION LADDER. Speaking back to a learner publishes
audio, so the capability sits on the ``RECOMMEND`` rung for drafting a reply but
the orchestrator-level ladder still applies: nothing is emitted to a human until
the gate serves it, and consequential follow-ons require explicit approval. This
adapter never self-approves and never holds credentials beyond the named env.

DEGRADES GRACEFULLY — when the provider SDK is absent OR the key is unset, every
entrypoint returns a clearly-marked ``provider_available=False`` result with no
token and no audio. No network is required to import or test this module.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Protocol

from .capability_registry import (
    Capability,
    CapabilityRegistry,
    CapabilityScope,
    Consequence,
)
from .config import ENV_PREFIX, Settings, get_settings
from .verify import (
    AbstainingSecondModel,
    ConfidenceGate,
    DeterministicCheck,
    GenerateVerification,
    SecondModelChecker,
)

# ---------------------------------------------------------------------------
# Capability identity (Track 1, least-privilege)
# ---------------------------------------------------------------------------

VOICE_CAPABILITY_NAME = "conversation.voice-speech-to-speech"
VOICE_TASK_CLASS = "conversation.voice-speech-to-speech"
VOICE_PURPOSE = "voice_companion_dialogue"

# The named secret (NAME ONLY — never a value). Mapped OS env key below.
GEMINI_KEY_SECRET_NAME = "clss.aifabric.dev.gemini_api_key"
GEMINI_KEY_ENV_VAR = ENV_PREFIX + "GEMINI_API_KEY"  # CLSS_AIFABRIC_DEV_GEMINI_API_KEY

# A short fuse for browser session tokens. The provider enforces the real TTL;
# we request a small one so a leaked token expires quickly.
DEFAULT_TOKEN_TTL_SECONDS = 120

# The native-audio model label routed on Track 1. A label only; the call is made
# by the provider SDK when present.
GEMINI_LIVE_MODEL_LABEL = "gemini-live-native-audio"


def voice_capability() -> Capability:
    """The governed descriptor for the speech-to-speech capability.

    Track 1, requires verification (its audio passes the confidence gate), and a
    LEAST-PRIVILEGE scope: one purpose code and the minimal conversation context
    — no PII, only the opaque conversation handle (INVARIANT — behavioural data
    carries the canonical_uuid only).
    """
    return Capability(
        name=VOICE_CAPABILITY_NAME,
        description=(
            "Vidya speech-to-speech turn (Gemini Live native audio): learner "
            "audio in, spoken reply out, behind the confidence gate."
        ),
        input_schema_ref="contract:ai.VoiceTurnInput",
        output_schema_ref="contract:ai.VoiceTurnResult",
        track=1,
        least_privilege=CapabilityScope(
            purpose=VOICE_PURPOSE,
            data_scopes=("conversation.context",),
            emits_events=True,
        ),
        requires_verification=True,
        task_class=VOICE_TASK_CLASS,
        consequence=Consequence.RECOMMEND,
    )


def register_voice_capability(registry: CapabilityRegistry) -> Capability:
    """Register the voice capability on an existing registry (idempotent-safe).

    Returns the descriptor. Raises via the registry if a clashing name is
    already present — the caller owns conflict policy.
    """
    cap = voice_capability()
    registry.register(cap)
    return cap


# ---------------------------------------------------------------------------
# Provider SDK seam (absent by default — degrades gracefully)
# ---------------------------------------------------------------------------

class LiveTokenMinter(Protocol):
    """The provider seam that mints an ephemeral Live session token.

    A real implementation wraps the Gemini Live SDK and calls the provider's
    auth-token endpoint with the raw key, returning ONLY the short-lived token.
    The raw key never leaves this seam.
    """

    def mint_ephemeral_token(self, *, raw_key: str, ttl_seconds: int) -> "MintedToken":
        ...


class LiveAudioModel(Protocol):
    """The provider seam for a server-side audio-in -> audio-out turn."""

    def respond(self, *, raw_key: str, audio_in: bytes, model_label: str) -> "AudioCandidate":
        ...


@dataclass(frozen=True)
class MintedToken:
    """A short-lived browser session token (NOT the raw key)."""

    token: str
    expires_in_seconds: int


@dataclass(frozen=True)
class AudioCandidate:
    """A candidate spoken reply from the provider, with a confidence signal."""

    audio_out: bytes
    confidence: float
    transcript: str | None = None


def _load_sdk_minter() -> LiveTokenMinter | None:
    """Locate the Gemini Live SDK token minter if installed; else ``None``.

    Import is guarded so the module is import-safe with no SDK present. We never
    fabricate a minter — absence means the capability reports unavailable.
    """
    try:  # pragma: no cover - depends on optional SDK being installed
        from google import genai  # type: ignore  # noqa: F401
    except Exception:
        return None
    return None  # No verified live wiring yet; treat as unavailable until wired.


def _load_sdk_model() -> LiveAudioModel | None:
    """Locate the Gemini Live native-audio model seam if installed; else ``None``."""
    try:  # pragma: no cover - depends on optional SDK being installed
        from google import genai  # type: ignore  # noqa: F401
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# Results (clearly-marked, key-free)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EphemeralSessionResult:
    """The browser handshake result.

    Carries the ephemeral token ONLY when the provider minted one. The raw key
    is NEVER present here. When unavailable, ``token`` is ``None`` and
    ``provider_available`` is ``False`` with a plain-language reason naming the
    env var to set.
    """

    provider_available: bool
    token: str | None
    expires_in_seconds: int | None
    model_label: str
    track: int
    capability: str
    detail: str | None = None

    def __post_init__(self) -> None:
        # Defence in depth: a token must never be the raw key, and an
        # unavailable result must never carry a token.
        if not self.provider_available and self.token is not None:
            raise ValueError("unavailable session result must not carry a token")


@dataclass(frozen=True)
class VoiceTurnResult:
    """A server-side speech-to-speech turn result, gated by the confidence gate.

    ``audio_out`` is meaningful ONLY when ``verification.served`` is true; when
    the gate refuses (or no provider), it is ``None`` and ``refused`` is true.
    Mirrors the fabric's GenerateResult shape. Never carries the raw key.
    """

    capability: str
    track: int
    provider_available: bool
    audio_out: bytes | None
    transcript: str | None
    verification: GenerateVerification | None
    refused: bool
    requires_approval: bool = False
    detail: str | None = None


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

@dataclass
class VoiceAdapter:
    """Gemini Live native-audio adapter (Track 1).

    Holds no credentials of its own: it reads the named key from settings only
    at the moment it must mint a token or call the provider, and never returns
    or logs it. With no SDK or no key, every entrypoint degrades to a
    clearly-marked unavailable result.
    """

    settings: Settings | None = None
    token_minter: LiveTokenMinter | None = None
    audio_model: LiveAudioModel | None = None
    gate: ConfidenceGate = field(default_factory=ConfidenceGate)
    # No live provider => the second model abstains, keeping the gate closed.
    second_model: SecondModelChecker = field(default_factory=AbstainingSecondModel)
    token_ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = get_settings()
        if self.token_minter is None:
            self.token_minter = _load_sdk_minter()
        if self.audio_model is None:
            self.audio_model = _load_sdk_model()

    # -- internal: key presence, by NAME, never exposed -------------------

    def _raw_key(self) -> str | None:
        """The raw provider key, or ``None``. PRIVATE — never returned/logged."""
        assert self.settings is not None
        key = self.settings.gemini_api_key
        if key is None or not str(key).strip():
            return None
        return str(key)

    def _unavailable_reason(self, *, have_key: bool, seam_present: bool) -> str:
        if not have_key:
            return (
                "Gemini Live provider key is not set. Provide the secret "
                f"'{GEMINI_KEY_SECRET_NAME}' via env var '{GEMINI_KEY_ENV_VAR}'. "
                "Returning unavailable rather than minting or fabricating a token."
            )
        if not seam_present:
            return (
                "Gemini Live SDK is not installed; cannot mint an ephemeral "
                "token or open a native-audio session. Returning unavailable."
            )
        return "Gemini Live provider unavailable."

    # -- browser handshake: MINT an ephemeral token ------------------------

    def mint_browser_session(self, *, ttl_seconds: int | None = None) -> EphemeralSessionResult:
        """Mint a short-lived session token for a browser to open a Live session.

        The raw key stays on the server: only the ephemeral token is returned.
        If the SDK is absent or the key is unset, returns
        ``provider_available=False`` with no token (never fabricated).
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.token_ttl_seconds
        raw_key = self._raw_key()
        seam = self.token_minter

        if raw_key is None or seam is None:
            return EphemeralSessionResult(
                provider_available=False,
                token=None,
                expires_in_seconds=None,
                model_label=GEMINI_LIVE_MODEL_LABEL,
                track=1,
                capability=VOICE_CAPABILITY_NAME,
                detail=self._unavailable_reason(
                    have_key=raw_key is not None, seam_present=seam is not None
                ),
            )

        minted = seam.mint_ephemeral_token(raw_key=raw_key, ttl_seconds=ttl)
        # Guard: the provider must hand back a token distinct from the raw key.
        if not minted.token or minted.token == raw_key:
            return EphemeralSessionResult(
                provider_available=False,
                token=None,
                expires_in_seconds=None,
                model_label=GEMINI_LIVE_MODEL_LABEL,
                track=1,
                capability=VOICE_CAPABILITY_NAME,
                detail="Provider did not return a valid ephemeral token; refusing to expose the raw key.",
            )
        return EphemeralSessionResult(
            provider_available=True,
            token=minted.token,
            expires_in_seconds=minted.expires_in_seconds,
            model_label=GEMINI_LIVE_MODEL_LABEL,
            track=1,
            capability=VOICE_CAPABILITY_NAME,
            detail=None,
        )

    # -- server-side speech-to-speech (audio in -> audio out), GATED -------

    def respond_speech_to_speech(
        self,
        *,
        audio_in: bytes,
        approval_token: str | None = None,
    ) -> VoiceTurnResult:
        """Produce a spoken reply to learner audio, behind the confidence gate.

        Flow: provider availability -> (permission ladder, deferred to the
        consequence rung) -> obtain candidate audio -> deterministic checks ->
        second-model cross-check -> the confidence gate. Audio is SERVED only
        when the gate passes; otherwise the turn is refused with a reason.
        """
        cap = voice_capability()

        raw_key = self._raw_key()
        model = self.audio_model
        if raw_key is None or model is None:
            return VoiceTurnResult(
                capability=cap.name,
                track=cap.track,
                provider_available=False,
                audio_out=None,
                transcript=None,
                verification=None,
                refused=True,
                detail=self._unavailable_reason(
                    have_key=raw_key is not None, seam_present=model is not None
                ),
            )

        # PERMISSION LADDER: a consequential rung would require an approval
        # token before emitting. This turn drafts a reply (RECOMMEND rung), so
        # it proceeds to the gate; consequential follow-ons gate elsewhere.
        if cap.is_consequential and not approval_token:
            return VoiceTurnResult(
                capability=cap.name,
                track=cap.track,
                provider_available=True,
                audio_out=None,
                transcript=None,
                verification=None,
                refused=False,
                requires_approval=True,
                detail=(
                    f"'{cap.name}' is consequential ({cap.consequence.value}); "
                    "explicit human approval is required before audio is emitted."
                ),
            )

        candidate = model.respond(
            raw_key=raw_key, audio_in=audio_in, model_label=GEMINI_LIVE_MODEL_LABEL
        )

        det_checks = self._deterministic_checks(candidate)
        agrees, sm_conf = self.second_model.cross_check(
            task_class=cap.task_class, content=candidate.transcript
        )
        confidence = min(candidate.confidence, sm_conf)
        verification = self.gate.evaluate(det_checks, agrees, confidence)

        served = verification.served
        return VoiceTurnResult(
            capability=cap.name,
            track=cap.track,
            provider_available=True,
            audio_out=candidate.audio_out if served else None,
            transcript=candidate.transcript if served else None,
            verification=verification,
            refused=not served,
            detail=None if served else verification.review_reason,
        )

    @staticmethod
    def _deterministic_checks(candidate: AudioCandidate) -> list[DeterministicCheck]:
        """Deterministic checks for an audio turn (fail-closed).

        We can deterministically assert the provider returned non-empty audio
        and a transcript to cross-check against; absence fails the gate closed.
        """
        checks: list[DeterministicCheck] = []
        has_audio = bool(candidate.audio_out)
        checks.append(DeterministicCheck(
            "audio-present", has_audio,
            "non-empty audio reply" if has_audio else "provider returned no audio",
        ))
        has_transcript = bool(candidate.transcript and candidate.transcript.strip())
        checks.append(DeterministicCheck(
            "transcript-present", has_transcript,
            "transcript available for cross-check" if has_transcript
            else "no transcript to cross-check — cannot verify the spoken reply",
        ))
        return checks
