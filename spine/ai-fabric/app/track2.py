"""Track 2 — proprietary / edge SLM adapter (A4).

This fills the reserved TRACK 2 slot: small, fast, on-device-style SLMs that
serve the high-frequency "ocean" of edge-tier work (hints, intent classification,
bounded companion turns). It is the proprietary / edge counterpart to Track 1's
external LLM routing and is owned by a DIFFERENT team.

INVARIANT 11 — TWO TRACKS ARE NEVER CONFLATED. This adapter runs ONLY on
Track 2. Its capabilities are registered with ``track=2``; its endpoint URL and
key are read from Track 2's OWN named secrets, distinct from Track 1's. The
router selects the edge tier for the appropriate task class while Track 1 stays
untouched; an edge selection is only fulfilled by Track 2 when an explicit
Track 2 intent is routed — selection never crosses tracks.

INVARIANT 4 — SECRETS ARE ENV-ONLY, READ BY NAME, NEVER HARDCODED. The endpoint
URL and key are read by NAME from the environment (secrets
``clss.aifabric.dev.track2_endpoint_url`` / ``clss.aifabric.dev.track2_endpoint_key``,
mapped to OS env ``CLSS_AIFABRIC_DEV_TRACK2_ENDPOINT_URL`` /
``CLSS_AIFABRIC_DEV_TRACK2_ENDPOINT_KEY``) via :mod:`app.config`. The raw key is
never returned, never logged, and never placed in any result object.

INVARIANT 7 — THE CONFIDENCE GATE. Track 2 output is generated content and runs
behind the SAME generate-and-verify gate as every other served capability:
deterministic checks pass, an independent second model agrees, and confidence
clears the threshold. With no live endpoint the gate stays closed (degrades
safely, never fabricates content).

INVARIANT 8 — THE PERMISSION LADDER. The edge capabilities here sit on the
``RECOMMEND`` rung (read/draft only). This adapter never self-approves and holds
no credentials of its own beyond the named env.

DEGRADES GRACEFULLY — when the endpoint is unset (no URL or no key) OR no edge
SLM seam is wired, every entrypoint returns a clearly-marked
``provider_available=False`` result with no content. No network is required to
import or test this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .capability_registry import (
    Capability,
    CapabilityRegistry,
    CapabilityScope,
    Consequence,
)
from .config import ENV_PREFIX, Settings, get_settings
from .router import (
    ModelRouter,
    ModelTier,
    RouteResolution,
    RouterSelectionInput,
    Track2Config,
)
from .verify import (
    AbstainingSecondModel,
    ConfidenceGate,
    DeterministicCheck,
    GenerateVerification,
    SecondModelChecker,
)

# ---------------------------------------------------------------------------
# Track 2 identity (INVARIANT 11 — never conflated with Track 1)
# ---------------------------------------------------------------------------

TRACK_ID = 2

# The named secrets (NAMES ONLY — never values). Mapped OS env keys below.
TRACK2_ENDPOINT_URL_SECRET_NAME = "clss.aifabric.dev.track2_endpoint_url"
TRACK2_ENDPOINT_KEY_SECRET_NAME = "clss.aifabric.dev.track2_endpoint_key"
TRACK2_ENDPOINT_URL_ENV_VAR = ENV_PREFIX + "TRACK2_ENDPOINT_URL"
TRACK2_ENDPOINT_KEY_ENV_VAR = ENV_PREFIX + "TRACK2_ENDPOINT_KEY"

# Owner string — distinct ownership from Track 1's router.
TRACK2_OWNER = "proprietary / edge models team (Ring 2)"

# Edge SLM model labels per Track 2 capability. Labels only; the call is made by
# the endpoint seam when present. These are the small, fast, on-device-style
# models that serve the high-frequency ocean.
EDGE_SLM_HINT_MODEL_LABEL = "edge-slm-hint"
EDGE_SLM_INTENT_MODEL_LABEL = "edge-slm-intent"


# ---------------------------------------------------------------------------
# Track 2 capabilities — edge tier, least-privilege, track=2
# ---------------------------------------------------------------------------

# Capability name -> task class. The task classes map to the EDGE tier in the
# router's auditable table, so the router selects the edge tier for these.
HINT_CAPABILITY_NAME = "content.generate-hint"
HINT_TASK_CLASS = "content.generate-hint"
INTENT_CAPABILITY_NAME = "classify.intent"
INTENT_TASK_CLASS = "classify.intent"


def track2_capabilities() -> tuple[Capability, ...]:
    """The governed Track 2 capabilities (edge tier).

    Each runs on ``track=2`` with a LEAST-PRIVILEGE scope: a single purpose code
    and the minimal data scopes — the opaque conversation handle and ontology
    references only, no PII (behavioural data carries the canonical_uuid only).
    Both require verification so their output passes the confidence gate.
    """
    return (
        Capability(
            name=HINT_CAPABILITY_NAME,
            description=(
                "Generate a single short hint for a learner, on a fast edge SLM "
                "(Track 2). High-frequency, low-stakes, behind the confidence gate."
            ),
            input_schema_ref="contract:ai.GenerateHintInput",
            output_schema_ref="contract:ai.HintResult",
            track=TRACK_ID,
            least_privilege=CapabilityScope(
                purpose="hint_generation",
                data_scopes=("ontology.skill", "conversation.context"),
                emits_events=True,
            ),
            requires_verification=True,
            task_class=HINT_TASK_CLASS,
            consequence=Consequence.RECOMMEND,
        ),
        Capability(
            name=INTENT_CAPABILITY_NAME,
            description=(
                "Classify a learner's free-text intent on a fast edge SLM "
                "(Track 2). High-frequency routing signal, behind the confidence gate."
            ),
            input_schema_ref="contract:ai.ClassifyIntentInput",
            output_schema_ref="contract:ai.IntentResult",
            track=TRACK_ID,
            least_privilege=CapabilityScope(
                purpose="intent_classification",
                data_scopes=("conversation.context",),
                emits_events=True,
            ),
            requires_verification=True,
            task_class=INTENT_TASK_CLASS,
            consequence=Consequence.RECOMMEND,
        ),
    )


def register_track2_capabilities(registry: CapabilityRegistry) -> tuple[Capability, ...]:
    """Register the Track 2 capabilities on an existing registry.

    Returns the registered descriptors. Raises via the registry if a clashing
    name is already present — the caller owns conflict policy.
    """
    caps = track2_capabilities()
    for cap in caps:
        registry.register(cap)
    return caps


def track2_config() -> Track2Config:
    """The Track 2 router config with the edge SLM models bound.

    Enabling Track 2 is config-only (INVARIANT 11 — no re-architecture): this
    binds the edge-tier model label and points at Track 2's OWN endpoint key by
    NAME. The router still requires the key to be present in the environment
    before it resolves available; absence degrades to unavailable.
    """
    return Track2Config(
        enabled=True,
        endpoint_base_url_env=TRACK2_ENDPOINT_URL_SECRET_NAME,
        provider_key_env=TRACK2_ENDPOINT_KEY_SECRET_NAME,
        tier_models={ModelTier.EDGE: EDGE_SLM_HINT_MODEL_LABEL},
        owner=TRACK2_OWNER,
    )


# ---------------------------------------------------------------------------
# Edge SLM endpoint seam (absent by default — degrades gracefully)
# ---------------------------------------------------------------------------

class EdgeSLMEndpoint(Protocol):
    """The Track 2 seam for a proprietary / edge SLM inference call.

    A real implementation wraps the edge endpoint (HTTP or on-device runtime)
    and is given the raw key + the resolved endpoint URL. The raw key never
    leaves this seam. With no seam wired, the adapter reports unavailable and
    never fabricates output.
    """

    def infer(
        self,
        *,
        raw_key: str,
        endpoint_url: str,
        model_label: str,
        task_class: str,
        prompt: str,
    ) -> "EdgeCandidate":
        ...


@dataclass(frozen=True)
class EdgeCandidate:
    """A candidate edge SLM output, with a confidence signal for the gate."""

    text: str
    confidence: float


def _load_edge_endpoint() -> EdgeSLMEndpoint | None:
    """Locate a wired edge SLM endpoint if available; else ``None``.

    No verified live wiring yet: this returns ``None`` so the adapter degrades
    to a clearly-marked unavailable result rather than fabricating an endpoint.
    A real deployment swaps in a concrete ``EdgeSLMEndpoint`` here or injects one
    via :class:`Track2Adapter`.
    """
    return None


# ---------------------------------------------------------------------------
# Result (clearly-marked, key-free)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Track2Result:
    """A Track 2 edge SLM turn result, gated by the confidence gate.

    ``text`` is meaningful ONLY when ``verification.served`` is true; when the
    gate refuses (or no endpoint), it is ``None`` and ``refused`` is true.
    Always carries ``track == 2`` and never the raw key.
    """

    capability: str
    track: int
    provider_available: bool
    text: str | None
    verification: GenerateVerification | None
    refused: bool
    requires_approval: bool = False
    detail: str | None = None

    def __post_init__(self) -> None:
        # Defence in depth: this is a Track 2 result and must never claim to be
        # Track 1 (INVARIANT 11 — never conflated).
        if self.track != TRACK_ID:
            raise ValueError(f"Track2Result must carry track={TRACK_ID}, got {self.track}")


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

@dataclass
class Track2Adapter:
    """Proprietary / edge SLM adapter (Track 2).

    Holds no credentials of its own: it reads the named endpoint key from
    settings only at the moment it must call the endpoint, and never returns or
    logs it. With no endpoint URL, no key, or no seam, every entrypoint degrades
    to a clearly-marked unavailable result — it never fabricates content and
    never borrows Track 1's keys.
    """

    settings: Settings | None = None
    endpoint: EdgeSLMEndpoint | None = None
    gate: ConfidenceGate = field(default_factory=ConfidenceGate)
    # No live endpoint => the second model abstains, keeping the gate closed.
    second_model: SecondModelChecker = field(default_factory=AbstainingSecondModel)
    router: ModelRouter | None = None

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = get_settings()
        if self.endpoint is None:
            self.endpoint = _load_edge_endpoint()
        if self.router is None:
            # The router carries Track 2 config so selection resolves on Track 2.
            self.router = ModelRouter(track2=track2_config())

    # -- internal: secrets, by NAME, never exposed ------------------------

    def _raw_key(self) -> str | None:
        """The raw endpoint key, or ``None``. PRIVATE — never returned/logged."""
        assert self.settings is not None
        key = self.settings.track2_endpoint_key
        if key is None or not str(key).strip():
            return None
        return str(key)

    def _endpoint_url(self) -> str | None:
        """The resolved endpoint URL, or ``None``."""
        assert self.settings is not None
        url = self.settings.track2_endpoint_url
        if url is None or not str(url).strip():
            return None
        return str(url)

    def _unavailable_reason(
        self, *, have_url: bool, have_key: bool, seam_present: bool
    ) -> str:
        missing: list[str] = []
        if not have_url:
            missing.append(
                f"endpoint URL (secret '{TRACK2_ENDPOINT_URL_SECRET_NAME}' "
                f"via env '{TRACK2_ENDPOINT_URL_ENV_VAR}')"
            )
        if not have_key:
            missing.append(
                f"endpoint key (secret '{TRACK2_ENDPOINT_KEY_SECRET_NAME}' "
                f"via env '{TRACK2_ENDPOINT_KEY_ENV_VAR}')"
            )
        if missing:
            return (
                "Track 2 (proprietary / edge) endpoint is not configured: missing "
                + " and ".join(missing)
                + ". Returning unavailable rather than fabricating content."
            )
        if not seam_present:
            return (
                "Track 2 edge SLM endpoint seam is not wired; cannot run an edge "
                "inference. Returning unavailable rather than fabricating content."
            )
        return "Track 2 (proprietary / edge) endpoint unavailable."

    # -- routing: confirm the edge tier resolves on Track 2 ----------------

    def resolve_route(self, *, task_class: str) -> RouteResolution:
        """Resolve the route for a Track 2 edge task class.

        Always routes with ``track=2`` so selection stays on Track 2 and never
        crosses to Track 1 (INVARIANT 11). The router selects the EDGE tier for
        the edge task classes via its auditable table.
        """
        assert self.router is not None
        return self.router.resolve(
            RouterSelectionInput(
                task_class=task_class,
                requires_verification=True,
                latency_sensitive=True,  # edge ocean is latency-sensitive
                track=TRACK_ID,
            )
        )

    # -- the edge SLM turn, GATED -----------------------------------------

    def run(self, *, task_class: str, prompt: str) -> Track2Result:
        """Run an edge SLM turn for a Track 2 task class, behind the gate.

        Flow: endpoint availability -> obtain candidate -> deterministic checks
        -> second-model cross-check -> the confidence gate. Text is SERVED only
        when the gate passes; otherwise the turn is refused with a reason. With
        no endpoint or no key, returns a clearly-marked unavailable result.
        """
        cap = self._capability_for(task_class)

        raw_key = self._raw_key()
        endpoint_url = self._endpoint_url()
        seam = self.endpoint
        model_label = _model_label_for(task_class)

        if raw_key is None or endpoint_url is None or seam is None:
            return Track2Result(
                capability=cap.name,
                track=TRACK_ID,
                provider_available=False,
                text=None,
                verification=None,
                refused=True,
                detail=self._unavailable_reason(
                    have_url=endpoint_url is not None,
                    have_key=raw_key is not None,
                    seam_present=seam is not None,
                ),
            )

        # PERMISSION LADDER: edge capabilities sit on the RECOMMEND rung. A
        # consequential rung would require an approval token before emitting.
        if cap.is_consequential:
            return Track2Result(
                capability=cap.name,
                track=TRACK_ID,
                provider_available=True,
                text=None,
                verification=None,
                refused=False,
                requires_approval=True,
                detail=(
                    f"'{cap.name}' is consequential ({cap.consequence.value}); "
                    "explicit human approval is required before output is emitted."
                ),
            )

        candidate = seam.infer(
            raw_key=raw_key,
            endpoint_url=endpoint_url,
            model_label=model_label,
            task_class=task_class,
            prompt=prompt,
        )

        det_checks = self._deterministic_checks(candidate)
        agrees, sm_conf = self.second_model.cross_check(
            task_class=cap.task_class, content=candidate.text
        )
        confidence = min(candidate.confidence, sm_conf)
        verification = self.gate.evaluate(det_checks, agrees, confidence)

        served = verification.served
        return Track2Result(
            capability=cap.name,
            track=TRACK_ID,
            provider_available=True,
            text=candidate.text if served else None,
            verification=verification,
            refused=not served,
            detail=None if served else verification.review_reason,
        )

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _capability_for(task_class: str) -> Capability:
        for cap in track2_capabilities():
            if cap.task_class == task_class:
                return cap
        raise KeyError(f"no Track 2 capability for task class {task_class!r}")

    @staticmethod
    def _deterministic_checks(candidate: EdgeCandidate) -> list[DeterministicCheck]:
        """Deterministic checks for an edge turn (fail-closed).

        We can deterministically assert the endpoint returned non-empty text and
        a confidence in the unit interval; absence fails the gate closed.
        """
        checks: list[DeterministicCheck] = []
        has_text = bool(candidate.text and candidate.text.strip())
        checks.append(DeterministicCheck(
            "output-present", has_text,
            "non-empty edge output" if has_text else "endpoint returned no text",
        ))
        conf_ok = 0.0 <= candidate.confidence <= 1.0
        checks.append(DeterministicCheck(
            "confidence-in-range", conf_ok,
            f"confidence {candidate.confidence}"
            + ("" if conf_ok else " out of [0,1] — cannot trust the signal"),
        ))
        return checks


def _model_label_for(task_class: str) -> str:
    """The edge SLM model label for a Track 2 task class."""
    if task_class == INTENT_TASK_CLASS:
        return EDGE_SLM_INTENT_MODEL_LABEL
    return EDGE_SLM_HINT_MODEL_LABEL
