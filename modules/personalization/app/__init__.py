"""Personalization — implicit profiling, consent + age-tier gated.

The "get to know the user WITHOUT asking" engine. It infers a provisional
personalization profile (interests, preferred subjects, goal, pace, strengths,
preferred learning style) from BEHAVIOURAL SIGNALS and light onboarding choices
— never from an explicit questionnaire. Every inferred trait carries its
evidence and a confidence, and is provisional (updatable on fresh signal), never
a permanent label.

Depth of inference is bounded by the consent + AGE-TIER that legally permits it
(DPDP): a young-child tier infers far less than an adult tier; an inference
beyond the consented tier is DENIED. Profiles are transparent (each trait is
explainable: "inferred because…") and revocable (revoking consent clears
inferred traits, leaving only what consent still permits).

PII-free throughout: keyed by the opaque ``canonical_uuid`` and opaque ontology
ids only. Import-safe and offline.
"""

from .consent_gate import (
    AgeTier,
    ConsentScope,
    InferenceDenied,
    PersonalizationConsent,
    TierPolicy,
    TraitKind,
    permitted_traits,
    require_inference,
    tier_policy,
)
from .infer import (
    InferenceInput,
    InferredProfile,
    InferredTrait,
    OnboardingChoice,
    Signal,
    SignalKind,
    infer_profile,
)
from .profile import (
    PersonalizationProfile,
    project_profile,
    replay,
)
from .preferences import (
    SurfaceHints,
    to_surface_hints,
)
from .events import (
    PersonalizationEventEmitter,
    build_profile_updated_payload,
    build_envelope,
)

__all__ = [
    # consent_gate
    "AgeTier",
    "ConsentScope",
    "InferenceDenied",
    "PersonalizationConsent",
    "TierPolicy",
    "TraitKind",
    "permitted_traits",
    "require_inference",
    "tier_policy",
    # infer
    "InferenceInput",
    "InferredProfile",
    "InferredTrait",
    "OnboardingChoice",
    "Signal",
    "SignalKind",
    "infer_profile",
    # profile
    "PersonalizationProfile",
    "project_profile",
    "replay",
    # preferences
    "SurfaceHints",
    "to_surface_hints",
    # events
    "PersonalizationEventEmitter",
    "build_profile_updated_payload",
    "build_envelope",
]
