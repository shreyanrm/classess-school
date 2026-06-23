"""Classess Intelligence Engine (spine A3, Ring 1).

The evidence -> mastery -> gap projection engine. Computes derived learner state
by REPLAYING immutable events; never authors mastery directly. Pure,
deterministic, no external calls.

  - mastery: the six explicit dimensions and the plain-language bands.
  - gaps: the ten gap types, each a distinct rule; never confirmed from one score.
  - evidence: weighting, freshness, and lineage on every conclusion.
  - profile / graph: per-learner and cohort projections, idempotent on rebuild.
"""

from __future__ import annotations

from .config import IntelligenceSettings, get_settings
from .evidence import EvidenceItem, collect_evidence, has_fresh_evidence, lineage_ids
from .gaps import GapResult, detect_gaps
from .graph import LearnerGraph, TopicCohortSummary, build_learner_graph
from .mastery import MasteryResult, compute_dimensions, compute_mastery, plain_language_for
from .models import (
    AttemptPayload,
    EventEnvelope,
    GapEvidence,
    GapType,
    MasteryBand,
    MasteryDimensions,
    MasteryReading,
    MasteryWeights,
    OntologyRef,
    PrerequisiteEdge,
    PrerequisiteGraph,
    ScoreRecordedPayload,
)
from .mind import (
    ALLOWED_CONDITIONING_PURPOSES,
    MIND_SCHEMA_VERSION,
    CognitiveFingerprint,
    ConditioningPayload,
    ConditioningPurpose,
    ConsentDenied,
    ConsentGrant,
    IndependenceProfile,
    PurposeNotPermitted,
    RetentionParams,
    assert_pii_free,
    build_conditioning_payload,
    build_fingerprint,
    derive_fingerprint,
    open_faucet,
)
from .profile import LearnerProfile, TopicProjection, build_profile, build_topic_projection
from .source import EventSource, InMemoryEventSource, make_event_source

__all__ = [
    "IntelligenceSettings",
    "get_settings",
    "EvidenceItem",
    "collect_evidence",
    "has_fresh_evidence",
    "lineage_ids",
    "GapResult",
    "detect_gaps",
    "LearnerGraph",
    "TopicCohortSummary",
    "build_learner_graph",
    "MasteryResult",
    "compute_dimensions",
    "compute_mastery",
    "plain_language_for",
    "AttemptPayload",
    "EventEnvelope",
    "GapEvidence",
    "GapType",
    "MasteryBand",
    "MasteryDimensions",
    "MasteryReading",
    "MasteryWeights",
    "OntologyRef",
    "PrerequisiteEdge",
    "PrerequisiteGraph",
    "ScoreRecordedPayload",
    "LearnerProfile",
    "TopicProjection",
    "build_profile",
    "build_topic_projection",
    "EventSource",
    "InMemoryEventSource",
    "make_event_source",
    "ALLOWED_CONDITIONING_PURPOSES",
    "MIND_SCHEMA_VERSION",
    "CognitiveFingerprint",
    "ConditioningPayload",
    "ConditioningPurpose",
    "ConsentDenied",
    "ConsentGrant",
    "IndependenceProfile",
    "PurposeNotPermitted",
    "RetentionParams",
    "assert_pii_free",
    "build_conditioning_payload",
    "build_fingerprint",
    "derive_fingerprint",
    "open_faucet",
]
