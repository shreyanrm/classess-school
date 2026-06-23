"""The LIVE second-model cross-checker (INVARIANT 7, Track 1 capability).

The generate-and-verify confidence gate (see :mod:`app.verify`) serves content
ONLY when an INDEPENDENT second model agrees. This module supplies that second
model for real:

  - :class:`LiveSecondModel` asks an INDEPENDENT provider model to CONFIRM or
    REFUTE generated content and returns ``(agrees, confidence)``. It is a
    Track 1 capability (external LLM routing) — kept SEPARATE from Track 2.
  - :class:`OpenAICrossCheckProvider` is the REAL provider seam: it calls the
    OpenAI Chat Completions API over HTTPS via ``httpx``, reading the key by env
    NAME (``clss.aifabric.dev.crosscheck_model_key`` ->
    ``CLSS_AIFABRIC_DEV_CROSSCHECK_MODEL_KEY``). OpenAI is deliberately a
    DIFFERENT provider than the Track-1 GENERATOR (Gemini), so the cross-check is
    truly independent — a second opinion from another model family, not the same
    model grading itself.
  - :func:`make_second_model` is the FACTORY the verify pipeline wires as its
    default: it picks LIVE (with the OpenAI provider) when the cross-check key is
    present in the environment (by NAME only), and falls back to the existing
    :class:`~app.verify.AbstainingSecondModel` when no key is set, so the gate
    stays CLOSED rather than passing unverified content.

INVARIANT 4 — SECRETS ARE ENV-ONLY, READ BY NAME, NEVER HARDCODED. The raw key
is read by NAME from settings only at the moment the provider is called and is
sent ONLY in the OpenAI ``Authorization`` header. It is NEVER returned, NEVER
logged, and NEVER placed in any result object — the cross-check returns only
``(agrees, confidence)``.

INVARIANT 11 — TWO TRACKS ARE NEVER CONFLATED. The cross-check is Track 1
(external LLM routing). It uses Track 1's own named cross-check secret and never
borrows Track 2's endpoint key. It is also a DIFFERENT provider than the Track-1
generator, so generate-and-verify is two distinct providers, not one.

DEGRADES GRACEFULLY — when the key is unset, the factory returns the abstaining
model, which never agrees (gate stays closed). A network/parse/refusal error in
the live provider also fails CLOSED. No network is required to import or test
this module: the httpx transport is injectable, so tests run fully offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Protocol

from .config import ENV_PREFIX, Settings, get_settings
from .verify import AbstainingSecondModel, SecondModelChecker

# ---------------------------------------------------------------------------
# The named secret (NAME ONLY — never a value). Mapped OS env key below.
# ---------------------------------------------------------------------------

# Track 1 cross-check provider key. Read by NAME via app.config.
CROSSCHECK_KEY_SECRET_NAME = "clss.aifabric.dev.crosscheck_model_key"
CROSSCHECK_KEY_ENV_VAR = ENV_PREFIX + "CROSSCHECK_MODEL_KEY"  # CLSS_AIFABRIC_DEV_CROSSCHECK_MODEL_KEY

# This cross-check is Track 1 (external LLM routing) — never conflated with Track 2.
TRACK_ID = 1

# The independent model label routed on Track 1. The cross-check model is OpenAI
# — a DIFFERENT provider family than the Track-1 generator (Gemini) — so the
# second opinion is genuinely independent.
CROSSCHECK_MODEL_LABEL = "openai:gpt-4o-mini"

# The OpenAI provider family for the independent cross-check. Named here so a
# test (and an auditor) can assert the cross-check is NOT the generator provider.
CROSSCHECK_PROVIDER = "openai"
# The Track-1 GENERATOR provider family (Gemini). The cross-check provider MUST
# differ from this — generate-and-verify uses two distinct providers.
GENERATOR_PROVIDER = "gemini"

# The OpenAI Chat Completions endpoint (a public URL, not a secret).
OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


# ---------------------------------------------------------------------------
# The provider seam (absent by default — degrades gracefully)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CrossCheckVerdict:
    """An independent model's verdict on generated content.

    ``agrees`` is the second model's confirm/refute decision; ``confidence`` is
    its own confidence in [0, 1]. Carries no content and never the raw key.
    """

    agrees: bool
    confidence: float


class CrossCheckProvider(Protocol):
    """The Track 1 seam for an independent cross-check inference call.

    A real implementation wraps an external provider (HTTP/SDK) and is given the
    raw key alone at call time. The raw key NEVER leaves this seam; the provider
    returns only a :class:`CrossCheckVerdict`. With no seam wired, the factory
    falls back to abstaining and never fabricates agreement.
    """

    def cross_check(
        self,
        *,
        raw_key: str,
        model_label: str,
        task_class: str,
        content: object,
    ) -> CrossCheckVerdict:
        ...


# ---------------------------------------------------------------------------
# The HTTP transport seam (real httpx by default; injectable for offline tests)
# ---------------------------------------------------------------------------

class HttpTransport(Protocol):
    """The HTTP seam the OpenAI provider posts through.

    A real implementation wraps httpx; injected in tests so the provider is
    exercised entirely OFFLINE (no live calls in tests). Returns the parsed JSON
    response body. Raises on transport / non-2xx so the live model fails closed.
    """

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
# The REAL OpenAI cross-check provider (a DIFFERENT provider than the generator)
# ---------------------------------------------------------------------------

@dataclass
class OpenAICrossCheckProvider:
    """An independent cross-check via OpenAI Chat Completions over HTTPS (httpx).

    The Track-1 GENERATOR is Gemini; this second opinion is OpenAI — a different
    provider family, so the verification is genuinely independent. The provider
    asks the model to CONFIRM or REFUTE the generated content and to report its
    own confidence; it parses a strict JSON verdict and returns only
    :class:`CrossCheckVerdict` (``agrees``, ``confidence``).

    INVARIANT 4 — the raw key arrives only at call time and is placed ONLY in the
    ``Authorization`` header; it is never stored on the instance, never logged,
    and never returned. Any transport / parse error raises, and the LIVE model
    above turns that into a fail-closed ``(False, 0.0)``.
    """

    transport: HttpTransport = field(default_factory=HttpxTransport)
    url: str = OPENAI_CHAT_COMPLETIONS_URL
    model: str = OPENAI_DEFAULT_MODEL
    timeout_seconds: float = 20.0
    provider: str = CROSSCHECK_PROVIDER

    def cross_check(
        self,
        *,
        raw_key: str,
        model_label: str,
        task_class: str,
        content: object,
    ) -> CrossCheckVerdict:
        system = (
            "You are an INDEPENDENT verifier from a different model provider than "
            "the generator. Decide whether the generated content is correct and "
            "appropriate for its task. Reply with STRICT JSON only: "
            '{"agrees": <true|false>, "confidence": <number 0..1>}. '
            "Set agrees=false if you cannot confirm it; never explain."
        )
        user = (
            f"Task class: {task_class}\n"
            f"Generated content to verify:\n{content!r}\n\n"
            "Return the JSON verdict now."
        )
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        # The raw key rides ONLY in the Authorization header, at call time.
        headers = {
            "Authorization": f"Bearer {raw_key}",
            "Content-Type": "application/json",
        }
        data = self.transport.post_json(
            url=self.url, headers=headers, json_body=body, timeout=self.timeout_seconds
        )
        return self._parse_verdict(data)

    @staticmethod
    def _parse_verdict(data: dict) -> CrossCheckVerdict:
        """Parse the OpenAI response into a verdict; malformed => fail closed."""
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return CrossCheckVerdict(agrees=False, confidence=0.0)
        try:
            parsed = json.loads(text) if isinstance(text, str) else text
        except (json.JSONDecodeError, TypeError):
            return CrossCheckVerdict(agrees=False, confidence=0.0)
        if not isinstance(parsed, dict):
            return CrossCheckVerdict(agrees=False, confidence=0.0)
        agrees = bool(parsed.get("agrees", False))
        try:
            confidence = float(parsed.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        return CrossCheckVerdict(agrees=agrees, confidence=confidence)


def _load_crosscheck_provider() -> CrossCheckProvider | None:
    """The default cross-check provider: the REAL OpenAI verifier (httpx).

    Returns an :class:`OpenAICrossCheckProvider` so that whenever the cross-check
    key is present, the factory wires a LIVE, INDEPENDENT second model (OpenAI) —
    a different provider than the Track-1 generator. With no key the factory
    never calls it (it abstains), so importing this module makes no live call.
    """
    return OpenAICrossCheckProvider()


# ---------------------------------------------------------------------------
# The live second model
# ---------------------------------------------------------------------------

@dataclass
class LiveSecondModel:
    """A live, independent second-model cross-checker (Track 1).

    Holds no credentials of its own: it reads the named cross-check key from
    settings only at the moment it must call the provider, and never returns or
    logs it. When the key is unset OR no provider seam is wired, it FAILS CLOSED
    — it does not agree and reports zero confidence, exactly like the abstaining
    model, so the confidence gate stays closed rather than passing unverified
    content.
    """

    provider: CrossCheckProvider | None = None
    settings: Settings | None = None
    model_label: str = CROSSCHECK_MODEL_LABEL

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = get_settings()
        if self.provider is None:
            self.provider = _load_crosscheck_provider()

    def __repr__(self) -> str:
        # The settings object carries the raw key; never let it reach a repr (and
        # thus a log line). Report only the seam presence, not any secret value.
        return (
            f"LiveSecondModel(model_label={self.model_label!r}, "
            f"provider={'wired' if self.provider is not None else None}, "
            f"key_present={self._raw_key() is not None})"
        )

    # -- internal: the raw key, by NAME, never exposed --------------------

    def _raw_key(self) -> str | None:
        """The raw cross-check key, or ``None``. PRIVATE — never returned/logged."""
        assert self.settings is not None
        key = self.settings.crosscheck_model_key
        if key is None or not str(key).strip():
            return None
        return str(key)

    def has_provider(self) -> bool:
        """True only when both a key is present AND a provider seam is wired."""
        return self._raw_key() is not None and self.provider is not None

    # -- the cross-check (returns ONLY agrees, confidence) ----------------

    def cross_check(self, *, task_class: str, content: object) -> tuple[bool, float]:
        """Ask the independent model to confirm/refute ``content``.

        Returns ``(agrees, confidence)``. Fails closed to ``(False, 0.0)`` when
        the key is unset, no seam is wired, or the provider errors — the raw key
        never appears in the return value under any path.
        """
        raw_key = self._raw_key()
        provider = self.provider
        if raw_key is None or provider is None:
            # No live cross-check available => abstain (keep the gate closed).
            return (False, 0.0)

        try:
            verdict = provider.cross_check(
                raw_key=raw_key,
                model_label=self.model_label,
                task_class=task_class,
                content=content,
            )
        except Exception:
            # A provider error must never serve unverified content; fail closed.
            return (False, 0.0)

        confidence = float(verdict.confidence)
        # Clamp to the unit interval so a misbehaving provider cannot force the
        # gate open with an out-of-range confidence.
        if confidence < 0.0:
            confidence = 0.0
        elif confidence > 1.0:
            confidence = 1.0
        # On refute, confidence is meaningless for the gate; report zero so the
        # threshold condition also closes, not just the agreement condition.
        if not verdict.agrees:
            return (False, 0.0)
        return (True, confidence)


# ---------------------------------------------------------------------------
# The factory — picks LIVE vs ABSTAIN by config
# ---------------------------------------------------------------------------

def make_second_model(
    *,
    settings: Settings | None = None,
    provider: CrossCheckProvider | None = None,
    env: dict[str, str] | None = None,
) -> SecondModelChecker:
    """Return the second-model cross-checker the verify pipeline should use.

    Picks the LIVE cross-checker when the cross-check provider key is present in
    the environment (by NAME) AND a provider seam is available; otherwise returns
    the existing :class:`~app.verify.AbstainingSecondModel` so the gate stays
    closed (degrades safely, never serves unverified content).

    ``provider`` may be injected for tests / real wiring; ``env`` injects a
    settings source (also for tests). The raw key is never returned.
    """
    if settings is None:
        settings = get_settings(env)
    live = LiveSecondModel(provider=provider, settings=settings)
    if live.has_provider():
        return live
    return AbstainingSecondModel()


def crosscheck_is_independent_of_generator() -> bool:
    """True when the cross-check provider differs from the Track-1 generator.

    Generate-and-verify must use TWO distinct providers: the generator (Gemini)
    and an independent verifier (OpenAI). This guards that invariant.
    """
    return CROSSCHECK_PROVIDER != GENERATOR_PROVIDER
