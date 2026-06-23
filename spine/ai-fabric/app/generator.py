"""The LIVE Track-1 generator — Gemini over HTTPS (A4, INVARIANT 11 Track 1).

The router resolves a tier on Track 1 (external LLM routing). This module makes
the actual GENERATE call for that track:

  - :class:`GeminiGenerator` calls the Gemini ``generateContent`` REST endpoint
    over HTTPS via ``httpx``, reading the key by env NAME
    (``clss.aifabric.dev.gemini_api_key`` -> ``CLSS_AIFABRIC_DEV_GEMINI_API_KEY``).
    Gemini is the Track-1 GENERATOR; the independent cross-check (OpenAI) lives
    in :mod:`app.second_model`, so generate-and-verify uses two distinct
    providers (INVARIANT 7).
  - It requests STRUCTURED OUTPUT (JSON) and VALIDATES the parsed object against
    the expected shape before it is allowed to become a candidate. A response
    that does not parse / does not validate fails CLOSED (no candidate), so the
    confidence gate never sees malformed content.
  - The HTTP transport is injectable so the module imports with no network and
    tests run fully OFFLINE.

INVARIANT 4 — the raw key is read by NAME at call time only and is sent ONLY as
the ``x-goog-api-key`` header. It is never stored on the instance, never logged,
never returned, and never placed in a candidate.

DEGRADES GRACEFULLY — with no key the generator reports UNAVAILABLE and produces
no candidate; the orchestrator turns that into a well-formed refusal rather than
fabricating content.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from .config import ENV_PREFIX, Settings, get_settings

# The Track-1 generator key (NAME only). Mapped OS env var below.
GEMINI_KEY_SECRET_NAME = "clss.aifabric.dev.gemini_api_key"
GEMINI_KEY_ENV_VAR = ENV_PREFIX + "GEMINI_API_KEY"  # CLSS_AIFABRIC_DEV_GEMINI_API_KEY

GENERATOR_PROVIDER = "gemini"
TRACK_ID = 1  # Track 1 — external LLM routing; never conflated with Track 2.

# The Gemini generateContent endpoint (a public URL template, not a secret).
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_DEFAULT_MODEL = "gemini-1.5-flash"


# ---------------------------------------------------------------------------
# Structured-output validation
# ---------------------------------------------------------------------------

class StructuredOutputError(ValueError):
    """Raised internally when a model response does not match the wanted shape."""


def validate_structured_output(
    parsed: Any, *, required_fields: tuple[str, ...]
) -> dict[str, Any]:
    """Validate a parsed model response against an expected object shape.

    The response MUST be a JSON object carrying every required field with a
    non-null value. Anything else raises :class:`StructuredOutputError`, which
    the generator turns into a fail-closed UNAVAILABLE result.
    """
    if not isinstance(parsed, dict):
        raise StructuredOutputError(f"expected a JSON object, got {type(parsed).__name__}")
    missing = [f for f in required_fields if f not in parsed or parsed[f] is None]
    if missing:
        raise StructuredOutputError(f"missing required field(s): {', '.join(missing)}")
    return parsed


# ---------------------------------------------------------------------------
# The HTTP transport seam (real httpx by default; injectable for offline tests)
# ---------------------------------------------------------------------------

class HttpTransport(Protocol):
    """The HTTP seam the generator posts through. Injected in tests for offline
    operation. Returns the parsed JSON body; raises on transport / non-2xx so the
    generator fails closed."""

    def post_json(
        self, *, url: str, headers: dict[str, str], json_body: dict, timeout: float
    ) -> dict:
        ...


@dataclass
class HttpxTransport:
    """A real httpx-backed transport. Imported lazily to stay import-safe."""

    def post_json(
        self, *, url: str, headers: dict[str, str], json_body: dict, timeout: float
    ) -> dict:
        import httpx  # local import: module stays import-safe / tests stay offline

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=json_body)
            resp.raise_for_status()
            return resp.json()


# ---------------------------------------------------------------------------
# The generator result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GenerationResult:
    """A validated generation, or a clearly-marked UNAVAILABLE.

    Carries NO secret. On ``available=False`` the orchestrator must refuse rather
    than fabricate. ``content`` is the validated structured object; token counts
    are populated only when Gemini reports usage metadata.
    """

    available: bool
    content: dict[str, Any] | None = None
    confidence: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    unavailable_reason: str | None = None


# ---------------------------------------------------------------------------
# The live Gemini generator
# ---------------------------------------------------------------------------

@dataclass
class GeminiGenerator:
    """A live Track-1 generator over the Gemini REST API (httpx).

    Reads the key by NAME at call time; sends it ONLY in the ``x-goog-api-key``
    header. Requests JSON output, parses it, and VALIDATES the structured shape
    before returning a candidate. Any missing key, transport error, parse error,
    or validation failure yields a fail-closed UNAVAILABLE result — never a
    fabricated candidate.
    """

    transport: HttpTransport = field(default_factory=HttpxTransport)
    settings: Settings | None = None
    base_url: str = GEMINI_BASE_URL
    model: str = GEMINI_DEFAULT_MODEL
    timeout_seconds: float = 30.0
    provider: str = GENERATOR_PROVIDER

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = get_settings()

    def __repr__(self) -> str:
        # Never let the settings (which holds the raw key) reach a repr/log.
        return (
            f"GeminiGenerator(model={self.model!r}, provider={self.provider!r}, "
            f"key_present={self._raw_key() is not None})"
        )

    # -- the named key, never exposed -------------------------------------

    def _raw_key(self) -> str | None:
        assert self.settings is not None
        key = self.settings.gemini_api_key
        if key is None or not str(key).strip():
            return None
        return str(key)

    def has_key(self) -> bool:
        return self._raw_key() is not None

    # -- generate ---------------------------------------------------------

    def generate(
        self,
        *,
        prompt: str,
        required_fields: tuple[str, ...],
        context: list[str] | None = None,
    ) -> GenerationResult:
        """Generate structured JSON content for a prompt, grounded on ``context``.

        Returns a validated :class:`GenerationResult`, or a fail-closed
        UNAVAILABLE result on any missing-key / transport / parse / validation
        failure. The raw key never appears in the return value under any path.
        """
        raw_key = self._raw_key()
        if raw_key is None:
            return GenerationResult(
                available=False,
                unavailable_reason=(
                    f"No Gemini generator key present. Set env var '{GEMINI_KEY_ENV_VAR}' "
                    f"(secret name '{GEMINI_KEY_SECRET_NAME}'). Generator returns "
                    "unavailable rather than fabricating content."
                ),
            )

        grounding = ""
        if context:
            joined = "\n".join(f"- {c}" for c in context)
            grounding = f"\nGrounding context (use only what is relevant):\n{joined}\n"

        instruction = (
            "Respond with STRICT JSON only — a single object with the fields: "
            f"{', '.join(required_fields)}, plus a numeric field 'confidence' in "
            "0..1 expressing your own confidence. Do not include any prose."
        )
        body = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{prompt}\n{grounding}\n{instruction}"}]}
            ],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        url = f"{self.base_url}/{self.model}:generateContent"
        # The raw key rides ONLY in the header, at call time.
        headers = {"x-goog-api-key": raw_key, "Content-Type": "application/json"}

        try:
            data = self.transport.post_json(
                url=url, headers=headers, json_body=body, timeout=self.timeout_seconds
            )
        except Exception:
            return GenerationResult(
                available=False,
                unavailable_reason="Gemini generation call failed; failing closed (no fabricated content).",
            )

        return self._parse_and_validate(data, required_fields=required_fields)

    @staticmethod
    def _parse_and_validate(
        data: dict, *, required_fields: tuple[str, ...]
    ) -> GenerationResult:
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return GenerationResult(
                available=False, unavailable_reason="Gemini response had no content part."
            )
        try:
            parsed = json.loads(text) if isinstance(text, str) else text
        except (json.JSONDecodeError, TypeError):
            return GenerationResult(
                available=False, unavailable_reason="Gemini response was not valid JSON."
            )
        try:
            validated = validate_structured_output(parsed, required_fields=required_fields)
        except StructuredOutputError as exc:
            return GenerationResult(
                available=False, unavailable_reason=f"structured-output validation failed: {exc}"
            )

        # Confidence: the model's own self-reported value, clamped to [0,1].
        try:
            confidence = float(validated.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        usage = data.get("usageMetadata") if isinstance(data, dict) else None
        prompt_tokens = completion_tokens = None
        if isinstance(usage, dict):
            prompt_tokens = usage.get("promptTokenCount")
            completion_tokens = usage.get("candidatesTokenCount")

        return GenerationResult(
            available=True,
            content=validated,
            confidence=confidence,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
