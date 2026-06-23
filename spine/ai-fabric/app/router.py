"""The model router (A4).

Maps a task class to a TIER:

  - ``frontier`` — the hardest, rarest reasoning (used sparingly),
  - ``mid``      — high-volume capable work (the workhorse),
  - ``edge``     — the high-frequency ocean of small, fast, low-stakes tasks.

INVARIANT 11 — TWO TRACKS ARE NEVER CONFLATED.
``Track1Config`` (external LLM routing, present now) and ``Track2Config``
(proprietary / edge models, the slot that exists from line one and is filled
later) are DISTINCT structures with distinct ownership and config. Selection
respects which track owns the capability. Adding Track 2 is a config change,
not a re-architecture.

INVARIANT 4 — SECRETS ARE ENV-ONLY, READ BY NAME, NEVER HARDCODED.
The router reads the provider key by the env var NAME declared in config
(convention ``clss.<app>.<env>.<purpose>``, mapped to an OS env var). When no
key is present the router returns a clearly-marked UNAVAILABLE result — it
never fabricates content and never invents a key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------

class ModelTier(str, Enum):
    """Router tiers. Mirrors the contract ``ModelTier`` enum."""

    FRONTIER = "frontier"
    MID = "mid"
    EDGE = "edge"


TIER_DOCS: dict[ModelTier, str] = {
    ModelTier.FRONTIER: "Hardest, rarest reasoning — highest capability, used sparingly.",
    ModelTier.MID: "High-volume capable work — the workhorse tier.",
    ModelTier.EDGE: "The high-frequency ocean of small, fast, low-stakes tasks.",
}


# ---------------------------------------------------------------------------
# Track configuration — DISTINCT structures (INVARIANT 11)
# ---------------------------------------------------------------------------

# Convention for the env var NAME holding the secret value. The dotted name is
# the canonical secret name; ``env_var_name()`` maps it to an OS-safe env key.
DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"


def env_var_name(dotted: str) -> str:
    """Map a dotted secret name to its OS environment variable key.

    ``clss.aifabric.dev.track1_provider_key`` -> ``CLSS_AIFABRIC_DEV_TRACK1_PROVIDER_KEY``.
    """
    return dotted.replace(".", "_").replace("-", "_").upper()


@dataclass(frozen=True)
class TierModel:
    """A model slot bound to a tier. The model id is a label; the actual call
    is made elsewhere. ``provider_key_env`` is the env var NAME (never a value)."""

    tier: ModelTier
    model_label: str
    provider_key_env: str


@dataclass(frozen=True)
class Track1Config:
    """TRACK 1 — external LLM routing (Ring 1, present now).

    Routes through an external gateway (e.g. LiteLLM). The provider key is read
    by NAME from the environment; absent => the track reports unavailable.
    """

    enabled: bool = True
    router_base_url_env: str = "clss.aifabric.dev.track1_router_url"
    provider_key_env: str = "clss.aifabric.dev.track1_provider_key"
    # Per-tier model labels for the external path.
    tier_models: dict[ModelTier, str] = field(
        default_factory=lambda: {
            ModelTier.FRONTIER: "frontier-external",
            ModelTier.MID: "mid-external",
            ModelTier.EDGE: "edge-external",
        }
    )
    owner: str = "ai-fabric router (Ring 1, external LLM)"

    def model_for(self, tier: ModelTier) -> TierModel:
        return TierModel(
            tier=tier,
            model_label=self.tier_models[tier],
            provider_key_env=self.provider_key_env,
        )


@dataclass(frozen=True)
class Track2Config:
    """TRACK 2 — proprietary / edge models (the reserved slot).

    INVARIANT 11: this slot EXISTS from the start, is filled later, and requires
    NO re-architecture. Distinct ownership and config from Track 1. Disabled by
    default; when disabled, selecting it yields an unavailable result.
    """

    enabled: bool = False
    endpoint_base_url_env: str = "clss.aifabric.dev.track2_endpoint_url"
    provider_key_env: str = "clss.aifabric.dev.track2_endpoint_key"
    tier_models: dict[ModelTier, str] = field(default_factory=dict)
    owner: str = "proprietary / edge models team (Ring 2)"
    note: str = "Reserved slot. Filled later, no re-architecture. Never conflated with Track 1."

    def model_for(self, tier: ModelTier) -> TierModel | None:
        label = self.tier_models.get(tier)
        if label is None:
            return None
        return TierModel(tier=tier, model_label=label, provider_key_env=self.provider_key_env)


# ---------------------------------------------------------------------------
# Selection input / output
# ---------------------------------------------------------------------------

TrackId = Literal[1, 2]


@dataclass(frozen=True)
class RouterSelectionInput:
    """The signals the router selects a tier on. Mirrors the contract."""

    task_class: str
    requires_verification: bool
    difficulty: float | None = None          # [0,1]; pushes toward frontier
    latency_sensitive: bool | None = None     # favours the edge tier
    # Which track OWNS this capability. Selection respects this; never crosses.
    track: TrackId = 1


@dataclass(frozen=True)
class RouterSelection:
    """The router's decision."""

    task_class: str
    tier: ModelTier
    track: TrackId
    rationale: str


@dataclass(frozen=True)
class RouteResolution:
    """A resolved route, ready to dispatch — or a clearly-marked unavailable.

    When ``available`` is False the caller MUST NOT fabricate content. The
    generate-and-verify substrate turns this into a well-formed refusal.
    """

    selection: RouterSelection
    model: TierModel | None
    available: bool
    unavailable_reason: str | None = None
    provider_key_env: str | None = None  # the env var NAME to set (never a value)


# ---------------------------------------------------------------------------
# Task-class -> tier mapping
# ---------------------------------------------------------------------------

# A small, explicit, auditable map. Unknown classes fall through to the
# difficulty/latency heuristic. Frontier is reserved for hard/rare reasoning.
_TASK_CLASS_TIER: dict[str, ModelTier] = {
    # Hard / rare reasoning -> frontier
    "evaluation.deep-reasoning": ModelTier.FRONTIER,
    "content.generate-assessment-blueprint": ModelTier.FRONTIER,
    "gap.root-cause-analysis": ModelTier.FRONTIER,
    # High-volume capable work -> mid
    "content.generate-practice-item": ModelTier.MID,
    "evaluation.response": ModelTier.MID,
    "content.explain-step": ModelTier.MID,
    # High-frequency ocean -> edge
    "conversation.companion-turn": ModelTier.EDGE,
    "conversation.voice-speech-to-speech": ModelTier.EDGE,  # interactive, latency-sensitive
    "content.generate-hint": ModelTier.EDGE,
    "classify.intent": ModelTier.EDGE,
}


class ModelRouter:
    """Selects a tier for a task class and resolves it on the owning track."""

    # Difficulty at or above this routes to frontier when no explicit mapping.
    FRONTIER_DIFFICULTY = 0.8

    def __init__(
        self,
        track1: Track1Config | None = None,
        track2: Track2Config | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        # Tracks stay DISTINCT objects (INVARIANT 11).
        self.track1 = track1 if track1 is not None else Track1Config()
        self.track2 = track2 if track2 is not None else Track2Config()
        # Inject env for tests; default to the process environment.
        self._env = env if env is not None else dict(os.environ)

    # -- tier selection ----------------------------------------------------

    def select_tier(self, inp: RouterSelectionInput) -> RouterSelection:
        mapped = _TASK_CLASS_TIER.get(inp.task_class)
        if mapped is not None:
            tier = mapped
            why = f"task_class '{inp.task_class}' is mapped to {tier.value}"
        elif inp.difficulty is not None and inp.difficulty >= self.FRONTIER_DIFFICULTY:
            tier = ModelTier.FRONTIER
            why = f"difficulty {inp.difficulty:.2f} >= {self.FRONTIER_DIFFICULTY} -> frontier"
        elif inp.latency_sensitive:
            tier = ModelTier.EDGE
            why = "latency_sensitive -> edge (the high-frequency ocean)"
        else:
            tier = ModelTier.MID
            why = "no explicit mapping; defaulting to the mid workhorse tier"
        return RouterSelection(task_class=inp.task_class, tier=tier, track=inp.track, rationale=why)

    # -- track resolution --------------------------------------------------

    def _has_key(self, dotted_env: str) -> bool:
        value = self._env.get(env_var_name(dotted_env))
        return bool(value and value.strip())

    def resolve(self, inp: RouterSelectionInput) -> RouteResolution:
        """Select a tier and resolve it on the OWNING track.

        Never crosses tracks. Returns a clearly-marked unavailable result when
        the owning track is disabled or its provider key is absent.
        """
        selection = self.select_tier(inp)

        if inp.track == 2:
            return self._resolve_track2(selection)
        return self._resolve_track1(selection)

    def _resolve_track1(self, selection: RouterSelection) -> RouteResolution:
        cfg = self.track1
        key_env = cfg.provider_key_env
        if not cfg.enabled:
            return RouteResolution(
                selection=selection, model=None, available=False,
                unavailable_reason="Track 1 is disabled in config.",
                provider_key_env=key_env,
            )
        if not self._has_key(key_env):
            return RouteResolution(
                selection=selection, model=None, available=False,
                unavailable_reason=(
                    f"No Track 1 provider key present. Set env var '{env_var_name(key_env)}' "
                    f"(secret name '{key_env}'). Router returns unavailable rather than fabricating content."
                ),
                provider_key_env=key_env,
            )
        return RouteResolution(
            selection=selection, model=cfg.model_for(selection.tier),
            available=True, provider_key_env=key_env,
        )

    def _resolve_track2(self, selection: RouterSelection) -> RouteResolution:
        cfg = self.track2
        key_env = cfg.provider_key_env
        if not cfg.enabled:
            return RouteResolution(
                selection=selection, model=None, available=False,
                unavailable_reason=(
                    "Track 2 (proprietary / edge) is the reserved slot — disabled until filled. "
                    "No re-architecture needed to enable it."
                ),
                provider_key_env=key_env,
            )
        model = cfg.model_for(selection.tier)
        if model is None:
            return RouteResolution(
                selection=selection, model=None, available=False,
                unavailable_reason=f"Track 2 has no model bound for tier '{selection.tier.value}'.",
                provider_key_env=key_env,
            )
        if not self._has_key(key_env):
            return RouteResolution(
                selection=selection, model=None, available=False,
                unavailable_reason=(
                    f"No Track 2 endpoint key present. Set env var '{env_var_name(key_env)}' "
                    f"(secret name '{key_env}')."
                ),
                provider_key_env=key_env,
            )
        return RouteResolution(selection=selection, model=model, available=True, provider_key_env=key_env)
