"""The translation interface (B9) — multilingual + code-switching.

Law 9 (multilingual by design) and the dossier:

  Offline-capable and multilingual with code-switching. Interface, conversation,
  content, and reports support local languages while PRESERVING subject
  terminology.

This is the INTERFACE the communication surfaces call to render a message in a
reader's language. Two non-negotiables, both enforced here:

  1. **Subject terminology is preserved.** A glossary of protected subject terms
     is never translated or paraphrased — "photosynthesis", "Pythagoras
     theorem", "denominator" stay intact in any target language, so meaning is
     never lost across a translation. Protected spans are masked, the rest is
     translated, and the terms are restored verbatim.
  2. **Code-switching is first-class.** Real classroom/home language mixes two
     languages in one sentence. The interface detects and preserves the switch
     points rather than flattening to one language.

Degrade-safe: with no translation provider wired the interface PASSES TEXT
THROUGH unchanged, tagged ``untranslated``, with the protected terms still
identified. It never silently drops or garbles content, and it never sends text
to an external provider without the gateway.

Import-safe: no I/O, no provider, no secret read at import. The pass-through and
the term-protection are pure and deterministic.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Protocol

from .config import CommunicationSettings, env_var_name, get_settings


# A small, illustrative protected glossary. In production this is sourced from
# the ontology steward (A2) per subject/board; here it seeds the deterministic
# path so subject terms are never lost. Terms are matched case-insensitively but
# restored in their canonical form.
DEFAULT_PROTECTED_TERMS: tuple[str, ...] = (
    "photosynthesis",
    "denominator",
    "numerator",
    "Pythagoras theorem",
    "mitochondria",
    "hypotenuse",
    "valency",
    "quadratic equation",
)


@dataclass(frozen=True)
class LanguageSpan:
    """A run of text tagged with the language it is written in. Code-switching
    produces more than one span for a single message."""

    text: str
    lang: str  # BCP-47-ish tag, e.g. "en", "hi". "und" = undetermined.


@dataclass
class TranslationResult:
    """The outcome of rendering text for a reader. PII-free: text only, no ids.

    ``status`` is ``translated`` only when a provider actually translated it;
    otherwise ``passthrough`` (degraded — the text is returned intact, never
    dropped). ``preserved_terms`` lists the subject terms kept verbatim.
    """

    source_text: str
    rendered_text: str
    source_lang: str
    target_lang: str
    status: Literal["translated", "passthrough"]
    preserved_terms: tuple[str, ...]
    spans: tuple[LanguageSpan, ...]
    provider: Literal["gateway_translation", "none_passthrough"]


_TOKEN = "␟"  # a unit-separator sentinel unlikely to appear in real text.

# The gateway bearer, read by NAME at call time only (INVARIANT 4, 8 — never a
# literal, never stored, never logged). Mapped OS env key below.
GATEWAY_TOKEN_SECRET_NAME = "clss.communication.dev.gateway_token"
GATEWAY_TOKEN_ENV_VAR = env_var_name(GATEWAY_TOKEN_SECRET_NAME)

# The gateway's generic route entrypoint + the communication translate operation
# (the AI fabric / model router — Gemini — sits behind it). Public route
# templates, not secrets.
GATEWAY_ROUTE_PATH = "/v1/route/communication/translate"


class TranslationTransport(Protocol):
    """The HTTP seam the live translation posts through (the gateway route to the
    model router). Injected in tests so the round-trip runs fully OFFLINE; a real
    implementation wraps httpx. Returns the parsed JSON body; raises on transport
    / non-2xx so the interface degrades to passthrough."""

    def post_json(
        self, *, url: str, headers: dict[str, str], json_body: dict, timeout: float
    ) -> Any:
        ...


@dataclass
class HttpxTranslationTransport:
    """A real httpx-backed transport. Imported lazily to stay import-safe."""

    def post_json(
        self, *, url: str, headers: dict[str, str], json_body: dict, timeout: float
    ) -> Any:
        import httpx  # local import: module stays import-safe / tests stay offline

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=json_body)
            resp.raise_for_status()
            return resp.json()


class TranslationInterface:
    """Renders messages across languages while preserving subject terminology
    and code-switching. Deterministic + offline in the degraded path."""

    def __init__(
        self,
        *,
        protected_terms: Iterable[str] | None = None,
        settings: CommunicationSettings | None = None,
        transport: TranslationTransport | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._settings = settings or get_settings()
        # The live egress transport (the gateway route to the model router).
        # Injectable for offline tests; absent => the real httpx transport.
        self._transport: TranslationTransport = transport or HttpxTranslationTransport()
        self._timeout = timeout_seconds
        terms = tuple(protected_terms) if protected_terms is not None else DEFAULT_PROTECTED_TERMS
        # Longest-first so multi-word terms match before their parts.
        self._terms = tuple(sorted(terms, key=len, reverse=True))
        self._patterns = tuple(
            (t, re.compile(rf"(?<![A-Za-z]){re.escape(t)}(?![A-Za-z])", re.IGNORECASE))
            for t in self._terms
        )

    @property
    def settings(self) -> CommunicationSettings:
        return self._settings

    def protected_terms(self) -> tuple[str, ...]:
        return self._terms

    def find_protected_terms(self, text: str) -> tuple[str, ...]:
        """The canonical protected terms present in ``text`` (order of glossary)."""
        found: list[str] = []
        for canonical, pat in self._patterns:
            if pat.search(text or ""):
                found.append(canonical)
        return tuple(found)

    def detect_spans(self, text: str) -> tuple[LanguageSpan, ...]:
        """Split text into language spans, preserving code-switch points.

        Deterministic heuristic for the offline path: a Devanagari run is "hi",
        a Latin run is "en". A real provider would refine this; the point is that
        the SWITCH is preserved as separate spans, never flattened.
        """
        if not text:
            return (LanguageSpan(text="", lang="und"),)
        spans: list[LanguageSpan] = []
        # Group consecutive chars by script bucket.
        current_chars: list[str] = []
        current_lang: str | None = None
        for ch in text:
            lang = self._script_lang(ch)
            if current_lang is None:
                current_lang = lang
            # Whitespace/punctuation inherits the current run so we don't split
            # on every space.
            if lang == "und":
                current_chars.append(ch)
                continue
            if lang != current_lang and current_chars:
                spans.append(LanguageSpan(text="".join(current_chars), lang=current_lang))
                current_chars = [ch]
                current_lang = lang
            else:
                current_chars.append(ch)
                current_lang = lang
        if current_chars:
            spans.append(LanguageSpan(text="".join(current_chars), lang=current_lang or "und"))
        return tuple(spans)

    @staticmethod
    def _script_lang(ch: str) -> str:
        o = ord(ch)
        if 0x0900 <= o <= 0x097F:  # Devanagari
            return "hi"
        if ("a" <= ch.lower() <= "z"):
            return "en"
        return "und"

    def is_code_switched(self, text: str) -> bool:
        """True when the text mixes more than one detected language."""
        langs = {s.lang for s in self.detect_spans(text) if s.lang != "und"}
        return len(langs) > 1

    def render(
        self,
        text: str,
        *,
        target_lang: str,
        source_lang: str = "und",
    ) -> TranslationResult:
        """Render ``text`` for a reader of ``target_lang``.

        Degraded (no provider): returns the text intact (``passthrough``) with
        protected terms and code-switch spans identified — never dropped, never
        garbled, never sent off-box.

        Wired: masks protected terms, sends the masked text through the gateway
        translation route to the model router (Gemini, token read from the
        environment by NAME), then restores the terms verbatim. Any missing
        token / transport / parse failure DEGRADES to passthrough — the text is
        returned intact, never dropped, never garbled.
        """
        preserved = self.find_protected_terms(text)
        spans = self.detect_spans(text)

        if not self._settings.has_translation:
            return self._passthrough(text, source_lang, target_lang, preserved, spans)

        # WIRED: the real masked round-trip through the gateway to the model
        # router. A failure at any step degrades to passthrough (observably),
        # never a fabricated or garbled translation.
        rendered = self._translate_via_gateway(
            text, target_lang=target_lang, source_lang=source_lang
        )
        if rendered is None:
            return self._passthrough(text, source_lang, target_lang, preserved, spans)
        return TranslationResult(
            source_text=text,
            rendered_text=rendered,
            source_lang=source_lang,
            target_lang=target_lang,
            status="translated",
            preserved_terms=preserved,
            # Re-detect spans on the rendered text so a code-switched output keeps
            # its switch points (the provider may translate one span, keep another).
            spans=self.detect_spans(rendered),
            provider="gateway_translation",
        )

    def _passthrough(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        preserved: tuple[str, ...],
        spans: tuple[LanguageSpan, ...],
    ) -> TranslationResult:
        return TranslationResult(
            source_text=text,
            rendered_text=text,  # intact — never dropped.
            source_lang=source_lang,
            target_lang=target_lang,
            status="passthrough",
            preserved_terms=preserved,
            spans=spans,
            provider="none_passthrough",
        )

    def _raw_gateway_token(self) -> str | None:
        """The gateway bearer, read by NAME, or ``None``. Never returned/logged."""
        raw = os.environ.get(GATEWAY_TOKEN_ENV_VAR)
        if raw is None or not raw.strip():
            return None
        return raw

    def _translate_via_gateway(
        self, text: str, *, target_lang: str, source_lang: str
    ) -> str | None:
        """Mask protected terms, POST the masked text through the gateway to the
        model router, restore the terms verbatim. Returns the rendered text, or
        ``None`` to signal a clean degrade to passthrough.

        INVARIANT 4/8: the bearer is read by NAME at call time and rides ONLY in
        the Authorization header; the engine holds no credential of its own. The
        request asserts the purpose (INVARIANT 6). Subject terminology is masked
        before egress and restored after, so it is NEVER sent to or altered by the
        provider — meaning is preserved across the translation."""
        token = self._raw_gateway_token()
        gateway_url = self._settings.gateway_url
        if token is None or not gateway_url:
            return None  # no credential / no egress => degrade to passthrough.

        masked, mapping = self.mask_protected_terms(text)
        url = gateway_url.rstrip("/") + GATEWAY_ROUTE_PATH
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Consent-Purpose": "communication",
            "Content-Type": "application/json",
        }
        body = {
            "text": masked,
            "target_lang": target_lang,
            "source_lang": source_lang,
            # The provider must keep these placeholders intact so the terms can be
            # restored verbatim — subject terminology is preserved by construction.
            "preserve_tokens": list(mapping.keys()),
        }
        try:
            data = self._transport.post_json(
                url=url, headers=headers, json_body=body, timeout=self._timeout
            )
        except Exception:
            return None  # transport failure => passthrough (never garble/drop).

        translated = self._extract_translated_text(data)
        if translated is None:
            return None
        # Restore the protected terms verbatim, whatever the provider returned.
        return self.restore_protected_terms(translated, mapping)

    @staticmethod
    def _extract_translated_text(data: Any) -> str | None:
        """Pull the translated string out of the gateway/model-router response.

        Accepts ``{"rendered_text": ...}`` / ``{"translated_text": ...}`` /
        ``{"text": ...}``. A shape we do not recognise => ``None`` (degrade), so a
        malformed provider reply never garbles or drops the message."""
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            for key in ("rendered_text", "translated_text", "text", "output"):
                value = data.get(key)
                if isinstance(value, str) and value:
                    return value
        return None

    def render_for_reader(
        self,
        text: str,
        *,
        preferred_lang: str | None,
        source_lang: str = "und",
    ) -> TranslationResult:
        """Render ``text`` into a READER's preferred language (B9: translate-to-
        preferred-language).

        ``preferred_lang`` is the reader's chosen interface language (resolved
        from their account/settings by the caller — this module holds no profile).
        An absent/undetermined preference is honoured as "no translation wanted":
        the text is returned intact (passthrough), never guessed at and never sent
        off-box. Otherwise this delegates to :meth:`render`, which preserves
        subject terminology and code-switch spans.
        """
        target = (preferred_lang or "").strip() or "und"
        if target == "und":
            return TranslationResult(
                source_text=text,
                rendered_text=text,  # no preference -> intact, never guessed.
                source_lang=source_lang,
                target_lang="und",
                status="passthrough",
                preserved_terms=self.find_protected_terms(text),
                spans=self.detect_spans(text),
                provider="none_passthrough",
            )
        return self.render(text, target_lang=target, source_lang=source_lang)

    def mask_protected_terms(self, text: str) -> tuple[str, dict[str, str]]:
        """Replace protected terms with opaque placeholders (for the wired path).

        Returns the masked text and the placeholder->term map for restoration.
        Pure + deterministic; exposed so the round-trip is testable offline.
        """
        mapping: dict[str, str] = {}
        masked = text
        for i, (canonical, pat) in enumerate(self._patterns):
            placeholder = f"{_TOKEN}{i}{_TOKEN}"
            if pat.search(masked):
                masked = pat.sub(placeholder, masked)
                mapping[placeholder] = canonical
        return masked, mapping

    @staticmethod
    def restore_protected_terms(text: str, mapping: dict[str, str]) -> str:
        """Restore masked placeholders to their canonical terms, verbatim."""
        restored = text
        for placeholder, canonical in mapping.items():
            restored = restored.replace(placeholder, canonical)
        return restored
