"""§1 onboarding — the consent + age-tier-gated IMPLICIT PROFILING circuit.

Proves the ProfilingCap is wired through the full circuit and obeys the
non-negotiables: identity -> gateway (wall) -> capability -> consent-stamped
event. The capability is registered (route + RBAC + dispatch), and:

  * INFER re-derives a PROVISIONAL profile from light BEHAVIOURAL signals (NO
    questionnaire) and emits a consent-stamped ``profile.updated`` event.
  * The consent + AGE TIER bounds inference DEPTH (DPDP children's-data): a
    minor tier infers strictly LESS than an adult tier (child ⊂ teen ⊂ adult);
    over-tier kinds are DENIED (recorded for transparency), never inferred.
  * REVOCATION severs it: a revoked consent clears the inferred traits.
  * NO PII is ever stored — the emitted event carries only the opaque
    canonical_uuid + opaque ids; a PII-shaped key is asserted absent.
  * Every fallback is OBSERVABLE: the degraded (no-gateway-sink) emission
    reports source='fallback', never a silent mock.
  * A LEARNER can drive their OWN onboarding profiling (account creation begins
    with the learner), while deny-by-default still holds (no token -> denied).

Runs fully offline with a Starlette ``TestClient``: no network, no DB, no secret.
"""

from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from backend import dispatch
from backend.main import app

client = TestClient(app)

SUBJ = "22222222-2222-4222-8222-222222222222"

# Light BEHAVIOURAL signals (what the learner DID) + one onboarding goal tap.
# There is no questionnaire field anywhere — only actions and a light choice.
_SIGNALS = [
    {"signal_id": "s1", "kind": "topic_engagement", "subject_id": "algebra", "weight": 3.0},
    {"signal_id": "s2", "kind": "attempt", "subject_id": "algebra",
     "correct": True, "independent": True, "weight": 2.0, "dwell_ms": 15000},
    {"signal_id": "s3", "kind": "content_interaction", "subject_id": "algebra",
     "content_format": "video", "weight": 2.0},
]
_CHOICES = [{"choice_id": "ch1", "kind": "goal", "value": "exam-prep"}]


def _dev_token(canonical_uuid: str, role: str, *, scopes=(), scope: str = "inst-1") -> str:
    claims = {
        "canonical_uuid": canonical_uuid,
        "app": "school",
        "memberships": [{"app": "school", "role": role, "scope": scope}],
        "consent_scopes": list(scopes),
    }
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "DEV-UNSIGNED." + body


def _infer(age_tier: str, *, role: str = "learner", revoked: bool = False) -> dict:
    payload = {
        "subject_uuid": SUBJ,
        "consents": [{
            "consent_id": "c-1",
            "age_tier": age_tier,
            "scopes": ["profiling", "preferences-hints"],
            "revoked": revoked,
        }],
        "consent_ref": "c-1",
        "signals": _SIGNALS,
        "onboarding_choices": _CHOICES,
    }
    resp = client.post(
        "/capabilities/personalization/infer",
        headers={"Authorization": f"Bearer {_dev_token(SUBJ, role)}",
                 "X-Consent-Purpose": "account"},
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "admitted"
    return body["result"]


# --------------------------------------------------------------------------- #
# Registration — the capability is wired (route + RBAC + dispatch).
# --------------------------------------------------------------------------- #
def test_personalization_is_registered_behind_the_wall():
    body = client.get("/health").json()
    assert "personalization" in body["capabilities"]


def test_dispatch_has_handlers():
    assert dispatch.has_handler("personalization", "infer")
    assert dispatch.has_handler("personalization", "hints")


# --------------------------------------------------------------------------- #
# The learner drives their OWN onboarding profiling (deny-by-default still holds).
# --------------------------------------------------------------------------- #
def test_learner_drives_own_profiling_and_emits_consent_stamped_event():
    result = _infer("teen")
    assert result["dispatched"] is True
    assert result["provisional"] is True
    # A consent-stamped profile.updated event was emitted (the circuit terminal).
    event = result["event"]
    assert event["type"] == "profile.updated"
    assert event["consent_ref"] == "c-1"
    assert event["purpose"] == "account"


def test_no_token_is_denied_by_default():
    resp = client.post(
        "/capabilities/personalization/infer",
        json={"subject_uuid": SUBJ, "signals": _SIGNALS},
    )
    assert resp.status_code in (401, 403)
    assert resp.json()["reason"] in ("no_token", "invalid_token")


# --------------------------------------------------------------------------- #
# CONSENT + AGE TIER bounds inference DEPTH (DPDP children's-data).
# --------------------------------------------------------------------------- #
def test_age_tier_bounds_inference_depth_child_subset_teen_subset_adult():
    child = set(_infer("child")["trait_kinds"])
    teen = set(_infer("teen")["trait_kinds"])
    adult = set(_infer("adult")["trait_kinds"])

    # A minor tier infers strictly LESS — the ceilings are nested.
    assert child < teen < adult
    # The child tier sees only the lightweight surface traits, never deep ones.
    assert child == {"interest", "preferred_subject"}
    # The deepest inference (learning_style) is adult-only.
    assert "learning_style" not in child and "learning_style" not in teen
    assert "learning_style" in adult


def test_over_tier_kinds_are_denied_for_transparency_not_inferred():
    child = _infer("child")
    # The over-tier kinds the gate refused are recorded (so a surface can say
    # "we do not infer this for you"), and NONE of them appear as inferred traits.
    denied = set(child["denied_trait_kinds"])
    assert {"pace", "goal", "strength", "learning_style"} <= denied
    assert denied.isdisjoint(set(child["trait_kinds"]))


def test_no_consent_in_payload_infers_nothing_denied_by_default():
    # No consents -> the gate denies every trait; nothing is inferred.
    resp = client.post(
        "/capabilities/personalization/infer",
        headers={"Authorization": f"Bearer {_dev_token(SUBJ, 'learner')}",
                 "X-Consent-Purpose": "account"},
        json={"subject_uuid": SUBJ, "signals": _SIGNALS, "onboarding_choices": _CHOICES},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["trait_kinds"] == []
    assert result["trait_count"] == 0


# --------------------------------------------------------------------------- #
# REVOCATION severs it.
# --------------------------------------------------------------------------- #
def test_revocation_clears_the_inferred_profile():
    # An adult tier infers the full set...
    assert _infer("adult")["trait_count"] > 0
    # ...but revoking the consent clears every inferred trait on replay.
    revoked = _infer("adult", revoked=True)
    assert revoked["trait_kinds"] == []
    assert revoked["trait_count"] == 0


# --------------------------------------------------------------------------- #
# NO PII is stored, and the fallback is OBSERVABLE.
# --------------------------------------------------------------------------- #
def test_emitted_event_is_pii_free_and_fallback_is_observable():
    result = _infer("adult")
    event = result["event"]
    # No gateway sink wired -> the emission DEGRADES, and it SAYS so (never a
    # silent mock): source='fallback', delivered=False, with a named sink.
    assert event["source"] == "fallback"
    assert event["delivered"] is False
    assert "in-memory" in event["sink"]

    # PII-free: the whole result blob carries no PII-shaped key (only opaque ids).
    blob = json.dumps(result).lower()
    for pii in ("name", "email", "phone", "dob", "address", "fullname", "username"):
        assert pii not in blob, f"PII-shaped key '{pii}' leaked into the profiling result"


# --------------------------------------------------------------------------- #
# HINTS — learner-safe surface hints, never leaking raw internals.
# --------------------------------------------------------------------------- #
def test_hints_are_learner_safe_no_internals():
    payload = {
        "subject_uuid": SUBJ,
        "consents": [{"consent_id": "c-1", "age_tier": "teen",
                      "scopes": ["profiling", "preferences-hints"]}],
        "signals": _SIGNALS,
        "onboarding_choices": _CHOICES,
    }
    resp = client.post(
        "/capabilities/personalization/hints",
        headers={
            # The hints READ is consent-scoped at the wall (personalization.read).
            "Authorization": f"Bearer {_dev_token(SUBJ, 'learner', scopes=['personalization.read'])}",
            "X-Consent-Purpose": "account",
        },
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["is_empty"] is False
    # Hints carry plain-language reasons + opaque values — NEVER raw internals.
    for hint in result["suggested_subjects"]:
        assert set(hint.keys()) == {"value", "why"}
        assert "confidence" not in hint and "evidence_signal_ids" not in hint
