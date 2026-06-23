"""The LIVE second-model cross-checker (INVARIANT 7, Track 1 capability).

The generate-and-verify confidence gate (see :mod:`app.verify`) serves content
ONLY when an INDEPENDENT second model agrees. This module supplies that second
model for real:

  - :class:`LiveSecondModel` asks an independent provider model to CONFIRM or
    REFUTE generated content and returns ``(agrees, confidence)``. It is a
    Track 1 capability (external LLM routing) — kept SEPARATE from Track 2.
  - :func:`make_second_model` is the FACTORY the verify pipeline wires as its
    default: it picks LIVE when the cross-check provider key is present in the
    environment (by NAME only — secret ``clss.aifabric.dev.crosscheck_model_key``,
    read via :mod:`app.config`), and falls back to the existing
    :class:`~app.verify.AbstainingSecondModel` when no key is set, so the gate
    stays CLOSED rather than passing unverified content.

INVARIANT 4 — SECRETS ARE ENV-ONLY, READ BY NAME, NEVER HARDCODED. The raw key
is read by NAME from settings only at the moment the provider is called. It is
NEVER returned, NEVER logged, and NEVER placed in any result object — the
cross-check returns only ``(agrees, confidence)``.

INVARIANT 11 — TWO TRACKS ARE NEVER CONFLATED. The cross-check is Track 1
(external LLM routing). It uses Track 1's own named secret and never borrows
Track 2's endpoint key.

DEGRADES GRACEFULLY — when the key is unset OR no provider seam is wired, the
factory returns the abstaining model, which never agrees (gate stays closed).
No network is required to import or test this module.
"""

from __future__ import annotations

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

# The independent model label routed on Track 1. A label only; the call is made
# by the provider seam when present.
CROSSCHECK_MODEL_LABEL = "crosscheck-independent"


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


def _load_crosscheck_provider() -> CrossCheckProvider | None:
    """Locate a wired cross-check provider if available; else ``None``.

    No verified live wiring ships here: this returns ``None`` so the factory
    degrades to the abstaining model rather than fabricating a provider. A real
    deployment swaps in a concrete :class:`CrossCheckProvider` or injects one via
    :func:`make_second_model` / :class:`LiveSecondModel`.
    """
    return None


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
