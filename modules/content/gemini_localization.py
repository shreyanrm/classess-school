"""REAL Gemini-backed hyperlocalization provider (B3, Track 1).

This is the live relevance engine behind :class:`content.hyperlocalize.Hyperlocalizer`.
Given a verified content body, a :class:`~content.hyperlocalize.LocaleContext`
(board / language / region / calendar / culture) and the subject terms that must
survive, it asks Gemini to produce a HYPERLOCALISED variant — same concept,
different surface (worked examples, place names, units, festival-aware calendar
references, reader's language). It never translates the subject terminology and
never alters a correctness-bearing fact; both are then ENFORCED downstream by the
hyperlocalizer's deterministic gate (subject-terms-preserved-verbatim,
concept-correctness-unchanged), so a stray variant is WITHHELD, never served.

LAWS honoured here:

  - INVARIANT 4 — SECRETS ARE ENV-ONLY, READ BY NAME, NEVER HARDCODED. The raw
    key is read by NAME from the environment (secret
    ``clss.aifabric.dev.gemini_api_key`` -> OS env
    ``CLSS_AIFABRIC_DEV_GEMINI_API_KEY``) via the spine's ``app.config`` at the
    moment of the call only. It is never returned, never logged, never placed in
    any result object, and never sent anywhere but the provider over HTTPS.
  - INVARIANT 7 — GENERATE-AND-VERIFY. This module only PRODUCES a candidate
    variant. Nothing it returns is served until the hyperlocalizer's confidence
    gate passes (deterministic checks first, then the independent second model).
  - DEGRADE CLEANLY — with no key (or no ``httpx``, or any provider error), the
    factory returns ``None`` so the hyperlocalizer falls back to the existing
    deterministic/template path and the base content is served marked
    ``not_yet_localised`` (never a fabricated translation). Tests are offline:
    the HTTP call is the only live edge and is never exercised without a key.

No PII leaves this module: only the content body (subject material) and the
locale signal are sent. The opaque request carries no learner identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from . import _spine
from .hyperlocalize import LocaleContext

# The named secret (NAME ONLY — never a value). Mapped OS env key below.
GEMINI_KEY_SECRET_NAME = "clss.aifabric.dev.gemini_api_key"
GEMINI_KEY_ENV_VAR = "CLSS_AIFABRIC_DEV_GEMINI_API_KEY"

# The Track 1 model label and the HTTPS endpoint template. A label only; the call
# is made by httpx when a key is present. ``{model}`` is filled in below.
GEMINI_MODEL_LABEL = "gemini-2.5-flash"
GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# A bounded request timeout so a slow provider degrades rather than hangs.
DEFAULT_TIMEOUT_SECONDS = 30.0

# The provider MAY embed its self-reported localisation confidence under this key
# in the candidate body; the hyperlocalizer strips it before serving.
_CONFIDENCE_KEY = "_localization_confidence"


# ---------------------------------------------------------------------------
# The HTTP seam (so tests can inject a fake transport; absent => no SDK call)
# ---------------------------------------------------------------------------

class HttpPoster(Protocol):
    """The minimal HTTPS seam this provider needs: POST JSON, get JSON back.

    A real implementation wraps ``httpx``; it is given the raw key alone at call
    time (as a query parameter on the provider URL, never logged). Tests inject a
    fake that returns canned JSON so no network is touched.
    """

    def post_json(
        self, *, url: str, api_key: str, payload: Mapping[str, object], timeout: float
    ) -> dict[str, object]:
        ...


def _load_httpx_poster() -> HttpPoster | None:
    """Return a real ``httpx``-backed poster, or ``None`` if ``httpx`` is absent.

    Import is guarded so the module stays import-safe with no dependency. The raw
    key is passed as the provider's ``key`` query parameter over HTTPS and is
    never logged or returned.
    """
    try:
        import httpx  # type: ignore
    except Exception:  # pragma: no cover - httpx is in requirements
        return None

    class _HttpxPoster:
        def post_json(
            self,
            *,
            url: str,
            api_key: str,
            payload: Mapping[str, object],
            timeout: float,
        ) -> dict[str, object]:
            # Key by NAME's VALUE travels only here, over HTTPS, as a query param.
            resp = httpx.post(
                url,
                params={"key": api_key},
                json=dict(payload),
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()

    return _HttpxPoster()


# ---------------------------------------------------------------------------
# Prompt construction (deterministic, key-free, PII-free)
# ---------------------------------------------------------------------------

def _build_prompt(
    *,
    body: Mapping[str, object],
    locale: LocaleContext,
    subject_terms: Sequence[str],
) -> str:
    """Build the instruction that asks for relevance, not translation.

    The model is told, in plain terms, the two non-negotiables the gate will
    enforce: keep every subject term VERBATIM, and never change any
    correctness-bearing value. We send the body and the locale signal as JSON.
    """
    terms = [t for t in subject_terms if t]
    terms_clause = (
        "Keep these subject terms EXACTLY as written, character for character, "
        f"in your output (do NOT translate or alter them): {json.dumps(terms)}."
        if terms
        else "Preserve any technical subject terminology verbatim."
    )
    return (
        "You hyperlocalise educational content. This is RELEVANCE, not "
        "translation: deliver the SAME concept with a surface adapted to the "
        "reader's world — worked examples, place names, units, festival-aware "
        "calendar references, and the reader's language.\n"
        f"{terms_clause}\n"
        "NEVER change any correctness-bearing value (an expression, an answer, a "
        "unit, a result). Copy those fields unchanged.\n"
        "Locale signal (board is a label, never a constraint on correctness):\n"
        f"{json.dumps(locale.as_signal(), ensure_ascii=False)}\n"
        "Base content (a JSON object of string fields and correctness fields):\n"
        f"{json.dumps(dict(body), ensure_ascii=False)}\n"
        "Return ONLY a JSON object: the same keys as the base content, with the "
        "surface (string) fields hyperlocalised and every correctness-bearing "
        "field copied unchanged. Add a numeric field "
        f"{json.dumps(_CONFIDENCE_KEY)} in [0,1] for your confidence."
    )


def _gemini_payload(prompt: str) -> dict[str, object]:
    """The Gemini ``generateContent`` request body for a JSON response."""
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.4,
        },
    }


def _extract_text(response: Mapping[str, object]) -> str | None:
    """Pull the model's text out of a Gemini ``generateContent`` response.

    Returns ``None`` on any unexpected shape so the caller degrades rather than
    fabricating a localisation.
    """
    try:
        candidates = response.get("candidates")  # type: ignore[union-attr]
        if not isinstance(candidates, list) or not candidates:
            return None
        content = candidates[0].get("content")
        parts = content.get("parts") if isinstance(content, Mapping) else None
        if not isinstance(parts, list) or not parts:
            return None
        text = parts[0].get("text") if isinstance(parts[0], Mapping) else None
        return text if isinstance(text, str) else None
    except Exception:  # pragma: no cover - defensive
        return None


def _parse_variant(text: str) -> dict[str, object] | None:
    """Parse the model's JSON variant; ``None`` on anything that is not a dict."""
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


# ---------------------------------------------------------------------------
# The live provider
# ---------------------------------------------------------------------------

@dataclass
class GeminiLocalizationProvider:
    """A REAL Gemini-backed :class:`~content.hyperlocalize.LocalizationProvider`.

    Implements ``localize(...)`` by calling Gemini over HTTPS with the named key.
    Holds no credentials of its own: it reads the key from spine settings only at
    call time and never returns or logs it. Whatever it returns is still subject
    to the hyperlocalizer's gate — so this provider's correctness obligations are
    BELT-AND-BRACES with the deterministic checks downstream.

    Degrades INSIDE ``localize`` too: if the call fails or the response is
    unparseable, it returns the base body UNCHANGED (no fabricated translation),
    which the deterministic gate will pass as a no-op variant or the second model
    will keep closed — never an invented localisation.
    """

    poster: HttpPoster | None = None
    settings: object | None = None
    model_label: str = GEMINI_MODEL_LABEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if self.settings is None and _spine.SPINE_AVAILABLE:
            # Via the unique alias (never the bare ``app.config`` — it would
            # collide with the other ``app`` packages in the single deployable).
            self.settings = _spine.get_settings()
        if self.poster is None:
            self.poster = _load_httpx_poster()

    # -- internal: the raw key, by NAME, never exposed --------------------

    def _raw_key(self) -> str | None:
        """The raw Gemini key, or ``None``. PRIVATE — never returned/logged."""
        settings = self.settings
        if settings is None:
            return None
        key = getattr(settings, "gemini_api_key", None)
        if key is None or not str(key).strip():
            return None
        return str(key)

    def __repr__(self) -> str:
        # The settings object carries the raw key; never let it reach a repr/log.
        return (
            f"GeminiLocalizationProvider(model_label={self.model_label!r}, "
            f"poster={'wired' if self.poster is not None else None}, "
            f"key_present={self._raw_key() is not None})"
        )

    def has_provider(self) -> bool:
        """True only when both a key is present AND an HTTPS poster is wired."""
        return self._raw_key() is not None and self.poster is not None

    # -- the LocalizationProvider protocol --------------------------------

    def localize(
        self,
        *,
        body: Mapping[str, object],
        locale: LocaleContext,
        subject_terms: Sequence[str],
    ) -> dict[str, object]:
        """Produce a candidate hyperlocalised variant of ``body`` for ``locale``.

        Returns a candidate dict (gated downstream). On any failure path it
        returns the base body unchanged — never a fabricated translation.
        """
        raw_key = self._raw_key()
        poster = self.poster
        if raw_key is None or poster is None:
            # No live path: hand back the base unchanged. The gate decides.
            return dict(body)

        prompt = _build_prompt(body=body, locale=locale, subject_terms=subject_terms)
        url = GEMINI_ENDPOINT_TEMPLATE.format(model=self.model_label)
        try:
            response = poster.post_json(
                url=url,
                api_key=raw_key,
                payload=_gemini_payload(prompt),
                timeout=self.timeout_seconds,
            )
        except Exception:
            # A provider/network error must never serve a fabricated localisation.
            return dict(body)

        text = _extract_text(response)
        if text is None:
            return dict(body)
        variant = _parse_variant(text)
        if variant is None:
            return dict(body)
        return variant


# ---------------------------------------------------------------------------
# The factory — picks LIVE vs the template path by config
# ---------------------------------------------------------------------------

def make_localization_provider(
    *,
    settings: object | None = None,
    poster: HttpPoster | None = None,
    env: Mapping[str, str] | None = None,
):
    """Return the live Gemini provider when keyed, else ``None``.

    Returns a :class:`GeminiLocalizationProvider` only when the Gemini key is
    present in the environment (by NAME) AND an HTTPS poster is available;
    otherwise returns ``None`` so :class:`~content.hyperlocalize.Hyperlocalizer`
    degrades to its existing deterministic/template path (base content served
    marked ``not_yet_localised`` — never a fabricated translation).

    ``poster`` / ``settings`` may be injected for tests or real wiring; ``env``
    injects a settings source (also for tests). The raw key is never returned.
    """
    if settings is None and _spine.SPINE_AVAILABLE:
        # Via the unique alias (never the bare ``app.config``).
        settings = _spine.get_settings(dict(env) if env is not None else None)
    provider = GeminiLocalizationProvider(poster=poster, settings=settings)
    if provider.has_provider():
        return provider
    return None
