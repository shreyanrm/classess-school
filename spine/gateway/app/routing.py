"""Capability operation -> upstream HTTP route map.

The gateway exposes a single generic entrypoint
``POST /v1/route/{capability}/{operation}`` (gateway contract). This table maps
each contract operationId to the concrete upstream method + path template on the
target capability service. The gateway is the ONLY caller of these upstreams.

Keeping the map explicit (rather than blindly proxying any path) is part of the
wall: an operation that is not in this table is not routable, which composes
with the deny-by-default policy engine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpstreamRoute:
    method: str
    path: str  # may contain {placeholders} filled from the request body/query
    # Whether this operation is a cross-context READ that must assert a purpose.
    purpose_required: bool = False


# capability -> operationId -> UpstreamRoute
ROUTE_MAP: dict[str, dict[str, UpstreamRoute]] = {
    "identity": {
        "resolveMemberships": UpstreamRoute("GET", "/v1/identity/memberships/resolve"),
        "consentCheck": UpstreamRoute("POST", "/v1/identity/consent/check"),
        "consentGrant": UpstreamRoute("POST", "/v1/identity/consent/grant"),
        "issueCanonicalUser": UpstreamRoute("POST", "/v1/identity/internal/users"),
    },
    "event-store": {
        "emitEvent": UpstreamRoute("POST", "/v1/event-store/events"),
        "readEvents": UpstreamRoute("GET", "/v1/event-store/events", purpose_required=True),
        "readEvent": UpstreamRoute("GET", "/v1/event-store/events/{event_id}", purpose_required=True),
    },
    # The deep intelligence engine (mastery / gaps / recommendations / class
    # insights) is the ONE source of truth — the Python spine. The web surface
    # routes its high-value governed reads here FIRST; only on a 503/unauthorised
    # /unreachable wall does it fall back to its in-browser engine port. These
    # are cross-context reads, so a purpose assertion is required (INVARIANT 6).
    "learning": {
        "read": UpstreamRoute("POST", "/v1/intelligence/read", purpose_required=True),
    },
    "intelligence-views": {
        "read": UpstreamRoute("POST", "/v1/intelligence/read", purpose_required=True),
        # The proactive loop's recommend -> approve -> execute, served by the
        # workflow runtime (spine A5) behind the wall. RECOMMEND is a governed
        # cross-context read of the recommendation feed (purpose asserted).
        # APPROVE records the human decision; EXECUTE clears a consequential
        # action AFTER approval (the wall forces the X-Approval-Token on it).
        "recommend": UpstreamRoute("POST", "/v1/workflow/recommend", purpose_required=True),
        "approve": UpstreamRoute("POST", "/v1/workflow/approve"),
        "execute": UpstreamRoute("POST", "/v1/workflow/execute"),
    },
    # The workflow runtime (spine A5) — the proactive loop + permission ladder.
    # Its three rungs are routable through the gateway to the in-process mount.
    "workflow": {
        "recommend": UpstreamRoute("POST", "/v1/workflow/recommend", purpose_required=True),
        "approve": UpstreamRoute("POST", "/v1/workflow/approve"),
        "execute": UpstreamRoute("POST", "/v1/workflow/execute"),
    },
    # GAP#10 — the Wave-2 feature-module fronts. Each is dispatched IN-PROCESS
    # behind the deployable's own governed capability door (the target base url is
    # {self}/capabilities; the path is /{capability}/{operation}). The door is
    # itself the wall, so this is the full circuit: identity -> gateway ->
    # capability door (wall) -> module -> event. Cross-context module reads assert
    # a purpose (INVARIANT 6).
    "institution": {
        "policy": UpstreamRoute("POST", "/institution/policy"),
    },
    "scheduling": {
        "recommend_recovery": UpstreamRoute("POST", "/scheduling/recommend_recovery"),
    },
    "attendance": {
        "capture": UpstreamRoute("POST", "/attendance/capture"),
    },
    "communication": {
        "translate": UpstreamRoute("POST", "/communication/translate", purpose_required=True),
        "make_tasks": UpstreamRoute("POST", "/communication/make_tasks"),
        "ptm": UpstreamRoute("POST", "/communication/ptm"),
        "parent_feedback": UpstreamRoute("POST", "/communication/parent_feedback", purpose_required=True),
    },
    "teacher-growth": {
        "coaching": UpstreamRoute("POST", "/teacher-growth/coaching", purpose_required=True),
    },
    # PERSONALIZATION — the consent + age-tier-gated implicit-profiling capability
    # powering §1 onboarding. INFER re-derives the learner's PROVISIONAL profile
    # from light behavioural signals and emits a consent-stamped profile.updated
    # event; HINTS projects that gated profile into learner-safe surface hints.
    # Both are cross-context reads of behavioural signals, so a purpose is
    # required (INVARIANT 6); the inference DEPTH is bounded inside the module by
    # the consent + age tier (DPDP). PII-free: opaque canonical_uuid only.
    "personalization": {
        "infer": UpstreamRoute("POST", "/personalization/infer", purpose_required=True),
        "hints": UpstreamRoute("POST", "/personalization/hints", purpose_required=True),
    },
    # The generate-and-verify CONTENT door (B3). External operationIds are
    # hyphenated (contract); the upstream operation segment is the deployable
    # door's underscore action name (see backend _ACTION_ALIASES). Each PREPARES
    # a draft behind the confidence gate; every served item passed the gate
    # (INVARIANT 7). A prepare, never an assign. (Lesson visuals are already
    # reachable via generate-and-verify-content with kind=lesson_visual.)
    "content": {
        "generate-worksheet": UpstreamRoute("POST", "/content/generate_worksheet"),
        "generate-and-verify-content": UpstreamRoute("POST", "/content/generate_and_verify_content"),
    },
    # PLANNING (d6): course outline / lesson plan / session plan. Each PREPARED
    # (a draft) behind the confidence gate; publishing is the separate
    # consequential human act (the permission ladder).
    "planning": {
        "generate-course-outline": UpstreamRoute("POST", "/planning/generate_course_outline"),
        "generate-lesson-plan": UpstreamRoute("POST", "/planning/generate_lesson_plan"),
        "generate-session-plan": UpstreamRoute("POST", "/planning/generate_session_plan"),
    },
    # The GOVERNANCE control plane (GAP#3/#5/#7). The consequential controls
    # (toggle / break-glass / policy version) PERSIST + emit an immutable audit
    # event; the audit-trail is the READ.
    "governance": {
        "toggle": UpstreamRoute("POST", "/governance/toggle"),
        "breakglass": UpstreamRoute("POST", "/governance/breakglass"),
        "policy_version": UpstreamRoute("POST", "/governance/policy_version"),
        "audit_trail": UpstreamRoute("POST", "/governance/audit_trail", purpose_required=True),
    },
}


def lookup(capability: str, operation: str) -> UpstreamRoute | None:
    return ROUTE_MAP.get(capability, {}).get(operation)
