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

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

from .config import CommunicationSettings, get_settings


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


class TranslationInterface:
    """Renders messages across languages while preserving subject terminology
    and code-switching. Deterministic + offline in the degraded path."""

    def __init__(
        self,
        *,
        protected_terms: Iterable[str] | None = None,
        settings: CommunicationSettings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
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

        Wired: would mask protected terms, send the masked text through the
        gateway translation provider (token read from the environment by NAME),
        then restore the terms verbatim. That egress path is intentionally not
        implemented while no provider exists.
        """
        preserved = self.find_protected_terms(text)
        spans = self.detect_spans(text)

        if not self._settings.has_translation:
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

        # Provider configured but egress not wired yet — keep the surface honest:
        # mask the terms so the contract is exercised, then refuse to fabricate a
        # translation. Callers should leave the var unset to use passthrough.
        raise NotImplementedError(
            "Gateway-backed translation is not wired yet. Configure "
            "clss.communication.dev.gateway_url + "
            "clss.communication.dev.translation_url and implement the masked "
            "round-trip behind this method (token read from the environment by "
            "NAME). Until then leave them unset to use the passthrough path."
        )

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
