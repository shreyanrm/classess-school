"""LTI 1.3 adapter (spine A6).

Validates and maps LTI 1.3 launch claims (the OIDC id_token body) into the
PII-free internal shapes. LTI launches carry the user's ``sub`` plus optional
name/email — only the opaque ``sub`` (scoped by ``iss``/``deployment_id``) is
consumed for the salted source_key; name/email are dropped at the seam
(INVARIANT 1, 2).

This adapter does NOT verify the JWT signature itself — signature verification
(JWKS, nonce, audience) is a governed gateway concern; this adapter holds no
keys (INVARIANT 4, 8). It validates the REQUIRED claim *shape* and maps. It also
builds AGS (grade passback) / NRPS (names-and-roles) request descriptors as
CONSEQUENTIAL capabilities the gateway executes — never auto-fired here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..connector import Capability, Connector, Direction
from ..mapping import IdentityResolver, map_identity, normalize_role
from ..models import CanonicalRef, Role, Standard

# LTI 1.3 message-type and role claim URIs.
CLAIM_MESSAGE_TYPE = "https://purl.imsglobal.org/spec/lti/claim/message_type"
CLAIM_VERSION = "https://purl.imsglobal.org/spec/lti/claim/version"
CLAIM_DEPLOYMENT_ID = "https://purl.imsglobal.org/spec/lti/claim/deployment_id"
CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"
CLAIM_CONTEXT = "https://purl.imsglobal.org/spec/lti/claim/context"
CLAIM_RESOURCE_LINK = "https://purl.imsglobal.org/spec/lti/claim/resource_link"
CLAIM_AGS = "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"
CLAIM_NRPS = "https://purl.imsglobal.org/spec/lti-nrps/claim/namesroleservice"

RESOURCE_LINK_REQUEST = "LtiResourceLinkRequest"
DEEP_LINKING_REQUEST = "LtiDeepLinkingRequest"

# IMS membership role URI suffix -> internal role.
_ROLE_SUFFIX = {
    "Learner": Role.STUDENT,
    "Student": Role.STUDENT,
    "Instructor": Role.TEACHER,
    "Teacher": Role.TEACHER,
    "Mentor": Role.GUARDIAN,
    "Administrator": Role.ADMINISTRATOR,
    "Staff": Role.STAFF,
}


class LTIMessageError(ValueError):
    """Raised when a launch payload is missing required LTI 1.3 claims."""


@dataclass
class LTILaunch:
    """A validated, PII-free view of an LTI 1.3 launch."""

    actor: CanonicalRef
    role: Role
    message_type: str
    deployment_id: str
    issuer: str
    context_source_key: str | None = None
    resource_link_source_key: str | None = None
    has_ags: bool = False
    has_nrps: bool = False


class LTIAdapter(Connector):
    standard = Standard.LTI_1_3

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "launch.map", Direction.INBOUND,
                "Validate LTI 1.3 launch claim shape and map to a PII-free launch.",
            ),
            Capability(
                "ags.scores", Direction.OUTBOUND,
                "Post AGS grade results (via a governed gateway capability).",
                consequential=True,
            ),
            Capability(
                "nrps.members", Direction.INBOUND,
                "Pull names-and-roles membership (via the gateway) into opaque refs.",
            ),
            Capability(
                "deeplink.respond", Direction.OUTBOUND,
                "Return a deep-linking response (via a governed gateway capability).",
                consequential=True,
            ),
        ]

    def map_launch(
        self,
        claims: dict[str, Any],
        *,
        identity_resolver: IdentityResolver | None = None,
    ) -> LTILaunch:
        # Required claims per LTI 1.3 core.
        version = claims.get(CLAIM_VERSION)
        if version != "1.3.0":
            raise LTIMessageError("missing or unsupported LTI version claim (expected 1.3.0).")
        message_type = claims.get(CLAIM_MESSAGE_TYPE)
        if message_type not in (RESOURCE_LINK_REQUEST, DEEP_LINKING_REQUEST):
            raise LTIMessageError(f"unsupported LTI message_type: {message_type!r}.")
        deployment_id = claims.get(CLAIM_DEPLOYMENT_ID)
        if not deployment_id:
            raise LTIMessageError("missing deployment_id claim.")
        issuer = claims.get("iss")
        sub = claims.get("sub")
        if not issuer or not sub:
            raise LTIMessageError("missing iss/sub — cannot derive an opaque identity.")

        # Scope the external id by issuer + deployment so the same sub from two
        # platforms never collides. The raw sub/name/email never leave here.
        scoped_external_id = f"{issuer}|{deployment_id}|{sub}"
        ref = map_identity(self.standard, scoped_external_id, resolver=identity_resolver)

        role = _map_roles(claims.get(CLAIM_ROLES) or [])

        context = claims.get(CLAIM_CONTEXT) or {}
        resource_link = claims.get(CLAIM_RESOURCE_LINK) or {}
        context_key = None
        if isinstance(context, dict) and context.get("id"):
            # context id scoped by issuer (opaque, no PII)
            context_key = f"{issuer}|ctx|{context['id']}"
        rl_key = None
        if isinstance(resource_link, dict) and resource_link.get("id"):
            rl_key = f"{issuer}|rl|{resource_link['id']}"

        return LTILaunch(
            actor=ref,
            role=role,
            message_type=message_type,
            deployment_id=str(deployment_id),
            issuer=str(issuer),
            context_source_key=context_key,
            resource_link_source_key=rl_key,
            has_ags=CLAIM_AGS in claims,
            has_nrps=CLAIM_NRPS in claims,
        )

    def build_ags_score_request(
        self,
        launch: LTILaunch,
        *,
        line_item_url: str,
        score_given: float,
        score_maximum: float,
    ) -> dict[str, Any]:
        """Build an AGS Score request descriptor (CONSEQUENTIAL — gateway executes).

        The userId is the OPAQUE canonical/source key, never an email. This is a
        descriptor only; this adapter does not send it (INVARIANT 8).
        """

        if launch.actor.canonical_uuid is None and not launch.actor.source_key:
            raise LTIMessageError("cannot build score request without an opaque user ref.")
        return {
            "_capability": "lti.ags.scores",
            "_consequential": True,
            "line_item_url": line_item_url,
            "score": {
                "userId": launch.actor.canonical_uuid or launch.actor.source_key,
                "scoreGiven": score_given,
                "scoreMaximum": score_maximum,
                "activityProgress": "Completed",
                "gradingProgress": "FullyGraded",
            },
        }


def _map_roles(roles: list[str]) -> Role:
    for r in roles:
        suffix = str(r).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        if suffix in _ROLE_SUFFIX:
            return _ROLE_SUFFIX[suffix]
        mapped = normalize_role(suffix)
        if mapped is not Role.UNKNOWN:
            return mapped
    return Role.UNKNOWN
