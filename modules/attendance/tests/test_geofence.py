"""Geofencing for staff: consent-gated, assists only, never auto-marks absent."""

import pytest

from app.geofence import (
    GeoConsent,
    GeoDecision,
    GeoReading,
    propose_from_geofence,
)
from app.staff import CaptureMethod, StaffStatus


def _consent(cuid="staff-1", granted=True):
    return GeoConsent(staff_uuid=cuid, granted=granted)


def test_no_consent_produces_nothing():
    reading = GeoReading(GeoDecision.INSIDE, "main_campus", "on_site")
    assert propose_from_geofence("staff-1", reading, None) is None
    assert propose_from_geofence("staff-1", reading, _consent(granted=False)) is None


def test_consent_for_other_staff_produces_nothing():
    reading = GeoReading(GeoDecision.INSIDE, "main_campus", "on_site")
    other = GeoConsent(staff_uuid="staff-2", granted=True)
    assert propose_from_geofence("staff-1", reading, other) is None


def test_inside_proposes_present_as_draft():
    reading = GeoReading(GeoDecision.INSIDE, "main_campus", "on_site", 0.95)
    prop = propose_from_geofence("staff-1", reading, _consent())
    assert prop is not None
    assert prop.proposed_status is StaffStatus.PRESENT
    assert prop.capture_method is CaptureMethod.DEVICE
    assert prop.needs_review is False


def test_outside_never_auto_marks_absent():
    reading = GeoReading(GeoDecision.OUTSIDE, "main_campus", "far", 0.95)
    prop = propose_from_geofence("staff-1", reading, _consent())
    assert prop is not None
    # not decisive: no status proposed, surfaced for a human
    assert prop.proposed_status is None
    assert prop.needs_review is True


def test_low_confidence_flagged_for_review():
    reading = GeoReading(GeoDecision.INSIDE, "main_campus", "on_site", 0.2)
    prop = propose_from_geofence("staff-1", reading, _consent())
    assert prop.needs_review is True


def test_no_raw_coordinates_on_proposal():
    reading = GeoReading(GeoDecision.INSIDE, "main_campus", "on_site")
    prop = propose_from_geofence("staff-1", reading, _consent())
    # only a zone label and a decision — never a coordinate
    assert prop.zone_label == "main_campus"
    assert not hasattr(prop, "latitude")
    assert not hasattr(prop, "longitude")


def test_pii_staff_ref_rejected():
    reading = GeoReading(GeoDecision.INSIDE, "main_campus", "on_site")
    with pytest.raises(ValueError):
        propose_from_geofence(
            "teacher@example.com", reading, GeoConsent("teacher@example.com", True)
        )
