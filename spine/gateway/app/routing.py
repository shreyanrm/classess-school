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
}


def lookup(capability: str, operation: str) -> UpstreamRoute | None:
    return ROUTE_MAP.get(capability, {}).get(operation)
