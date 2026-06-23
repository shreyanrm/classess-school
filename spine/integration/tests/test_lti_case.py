"""LTI 1.3 launch mapping (opaque, approval-gated AGS) and CASE framework parse."""

from __future__ import annotations

import json

from app import Role, Standard
from app.adapters import CASEAdapter, LTIAdapter, LTIMessageError
from app.adapters.lti import (
    CLAIM_AGS,
    CLAIM_DEPLOYMENT_ID,
    CLAIM_MESSAGE_TYPE,
    CLAIM_ROLES,
    CLAIM_VERSION,
    RESOURCE_LINK_REQUEST,
)


def _valid_claims() -> dict:
    return {
        "iss": "https://lms.example.com",
        "sub": "user-abc",
        CLAIM_VERSION: "1.3.0",
        CLAIM_MESSAGE_TYPE: RESOURCE_LINK_REQUEST,
        CLAIM_DEPLOYMENT_ID: "dep-1",
        CLAIM_ROLES: [
            "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner",
        ],
        "name": "Asha Verma",
        "email": "asha@example.com",
        CLAIM_AGS: {"lineitems": "https://lms.example.com/li"},
    }


def test_lti_launch_maps_to_opaque_ref_no_pii():
    adapter = LTIAdapter("lti:test")
    launch = adapter.map_launch(_valid_claims())
    assert launch.role is Role.STUDENT
    assert launch.has_ags is True
    assert launch.actor.source_key.startswith("lti-1.3:")
    # name/email/sub never appear on the opaque ref
    blob = json.dumps({
        "source_key": launch.actor.source_key,
        "deployment_id": launch.deployment_id,
        "issuer": launch.issuer,
    })
    for leaked in ("Asha", "asha@example.com", "user-abc"):
        assert leaked not in blob


def test_lti_missing_version_rejected():
    claims = _valid_claims()
    del claims[CLAIM_VERSION]
    raised = False
    try:
        LTIAdapter("lti:test").map_launch(claims)
    except LTIMessageError:
        raised = True
    assert raised


def test_lti_missing_sub_rejected():
    claims = _valid_claims()
    del claims["sub"]
    raised = False
    try:
        LTIAdapter("lti:test").map_launch(claims)
    except LTIMessageError:
        raised = True
    assert raised


def test_lti_ags_score_request_is_consequential_descriptor():
    adapter = LTIAdapter("lti:test")
    launch = adapter.map_launch(_valid_claims())
    req = adapter.build_ags_score_request(
        launch, line_item_url="https://lms.example.com/li/1",
        score_given=8, score_maximum=10,
    )
    # It is a DESCRIPTOR, flagged consequential — never auto-sent (INVARIANT 8).
    assert req["_consequential"] is True
    assert req["score"]["scoreGiven"] == 8
    # userId is the opaque key, never an email.
    assert "@" not in req["score"]["userId"]


def test_lti_same_sub_two_issuers_distinct_keys():
    adapter = LTIAdapter("lti:test")
    a = adapter.map_launch(_valid_claims())
    other = _valid_claims()
    other["iss"] = "https://other-lms.example.com"
    b = adapter.map_launch(other)
    assert a.actor.source_key != b.actor.source_key


# ---------------------------------------------------------------------------
# CASE
# ---------------------------------------------------------------------------
CASE_PACKAGE = {
    "CFDocument": {"identifier": "doc-1", "title": "State Math Standards"},
    "CFItems": [
        {"identifier": "i1", "humanCodingScheme": "7.NS", "fullStatement": "The Number System"},
        {"identifier": "i2", "humanCodingScheme": "7.NS.A.1", "fullStatement": "Add and subtract rational numbers"},
    ],
    "CFAssociations": [
        {
            "associationType": "isChildOf",
            "originNodeURI": {"identifier": "i2"},
            "destinationNodeURI": {"identifier": "i1"},
        }
    ],
}


def test_case_parse_framework_builds_hierarchy():
    adapter = CASEAdapter("case:test")
    outcomes = adapter.parse_framework(CASE_PACKAGE)
    assert len(outcomes) == 2
    by_code = {o.external_code: o for o in outcomes}
    assert by_code["7.NS.A.1"].parent_external_code == "7.NS"
    assert by_code["7.NS.A.1"].framework == "State Math Standards"
    # offline -> proposed but unmapped (steward confirms downstream)
    assert all(not o.mapped for o in outcomes)


def test_case_with_ontology_resolver_proposes_mapping():
    class _Resolver:
        def resolve_outcome(self, framework, code):
            if code == "7.NS.A.1":
                return {"outcome_id": "ont-out-9", "competency_id": "ont-comp-3"}
            return None

    adapter = CASEAdapter("case:test")
    outcomes = adapter.parse_framework(CASE_PACKAGE, ontology_resolver=_Resolver())
    mapped = [o for o in outcomes if o.mapped]
    assert len(mapped) == 1
    assert mapped[0].ontology_outcome_id == "ont-out-9"
