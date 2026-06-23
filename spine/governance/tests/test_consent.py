"""Consent + retention + lineage. No network/DB.

INVARIANT 6 — consent gates every cross-context read; lineage on every insight.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.consent import (
    ConsentNotSatisfiedError,
    ConsentService,
    LineageRequiredError,
    LineageService,
    RetentionService,
)
from app.models import RetentionAction, new_id


# -- consent gate -----------------------------------------------------------

def test_no_consent_means_gate_closed():
    svc = ConsentService()
    subject = new_id()
    assert svc.is_satisfied(subject, "mastery") is False
    with pytest.raises(ConsentNotSatisfiedError):
        svc.require(subject, "mastery")


def test_grant_opens_the_gate_for_its_purpose_only():
    svc = ConsentService()
    subject = new_id()
    svc.grant(canonical_uuid=subject, purpose="mastery", scope="learning",
              age_tier="teen", granted_by=new_id(), retention_days=365)
    assert svc.is_satisfied(subject, "mastery") is True
    # A different purpose is not covered.
    assert svc.is_satisfied(subject, "communication") is False


def test_revoke_closes_the_gate():
    svc = ConsentService()
    subject = new_id()
    g = svc.grant(canonical_uuid=subject, purpose="mastery", scope="learning",
                  age_tier="teen", granted_by=new_id(), retention_days=365)
    assert svc.is_satisfied(subject, "mastery") is True
    svc.revoke(consent_id=g.consent_id)
    assert svc.is_satisfied(subject, "mastery") is False


# -- retention --------------------------------------------------------------

def test_retention_keep_then_expire():
    rs = RetentionService()
    svc = ConsentService()
    g = svc.grant(canonical_uuid=new_id(), purpose="mastery", scope="s",
                  age_tier="teen", granted_by=new_id(), retention_days=30)
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Within the window.
    assert rs.due_action(consent=g, record_created_at=created,
                         now=created + timedelta(days=10)) is RetentionAction.KEEP
    # Past the window -> expire (sever the linkable row).
    assert rs.due_action(consent=g, record_created_at=created,
                         now=created + timedelta(days=31)) is RetentionAction.EXPIRE


def test_legal_hold_overrides_expiry():
    rs = RetentionService()
    svc = ConsentService()
    g = svc.grant(canonical_uuid=new_id(), purpose="mastery", scope="s",
                  age_tier="teen", granted_by=new_id(), retention_days=1)
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert rs.due_action(consent=g, record_created_at=created, legal_hold=True,
                         now=created + timedelta(days=999)) is RetentionAction.LEGAL_HOLD


def test_revoked_consent_expires_retention():
    rs = RetentionService()
    svc = ConsentService()
    g = svc.grant(canonical_uuid=new_id(), purpose="mastery", scope="s",
                  age_tier="teen", granted_by=new_id(), retention_days=999)
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    revoked = svc.revoke(consent_id=g.consent_id, at=created + timedelta(days=5))
    assert rs.due_action(consent=revoked, record_created_at=created,
                         now=created + timedelta(days=6)) is RetentionAction.EXPIRE


# -- lineage ----------------------------------------------------------------

def test_lineage_built_with_consent_and_sources():
    ls = LineageService()
    lin = ls.build_lineage(
        canonical_uuid=new_id(), purpose="mastery", consent_id=new_id(),
        confidence=0.91, evidence_event_ids=[new_id(), new_id()],
        model_ref="mid-tier", capability_ref="evaluate.response",
    )
    kinds = {n.kind for n in lin.nodes}
    assert "event" in kinds and "consent" in kinds and "model" in kinds
    assert lin.confidence == 0.91


def test_insight_without_consent_ref_is_refused():
    ls = LineageService()
    with pytest.raises(LineageRequiredError):
        ls.build_lineage(canonical_uuid=new_id(), purpose="mastery",
                         consent_id=None, confidence=0.9,
                         evidence_event_ids=[new_id()])


def test_insight_without_any_source_is_refused():
    ls = LineageService()
    with pytest.raises(LineageRequiredError):
        ls.build_lineage(canonical_uuid=new_id(), purpose="mastery",
                         consent_id=new_id(), confidence=0.9)
