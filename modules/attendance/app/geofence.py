"""Geofencing for STAFF attendance — a consent-gated seam (d8).

The document lists "geofencing for staff" as an OPTIONAL capture aid. Like
on-device face / liveness, location is sensitive: it is only ever used where it
is PERMITTED and CONSENTED, and it only ever ASSISTS — a geofence reading is a
proposal a human confirms, never an auto-finalised mark.

CONSENT-GATED SEAM (INVARIANT 5 + 6): every entry point demands an explicit
consent grant for the staff member. With no grant — the default — this module
PRODUCES NOTHING (fail-closed). It never reads a live location service here;
the device/integration layer resolves coordinates upstream and passes an
already-evaluated, opaque :class:`GeoReading`. No raw coordinates are stored on
the proposal; only the inside/outside decision and a coarse distance band.

PII / location-minimisation: the proposal carries the opaque ``staff_uuid``,
the campus-zone label, and whether the reading was inside the fence — never a
name and never a precise lat/long.

Import-safe: pure functions over plain data; no I/O, no provider, no secret.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .safety import assert_no_pii_identifier
from .staff import CaptureMethod, StaffStatus


class GeoDecision(str, Enum):
    INSIDE = "inside"        # within the campus geofence
    OUTSIDE = "outside"      # outside the campus geofence
    UNKNOWN = "unknown"      # no usable reading — never inferred as either


@dataclass(frozen=True)
class GeoConsent:
    """A staff member's consent to use geofencing for attendance.

    Fail-closed: only an explicit ``granted=True`` enables a proposal, and only
    for the scope it was granted for (``purpose``)."""

    staff_uuid: str
    granted: bool
    purpose: str = "attendance_geofence"


@dataclass(frozen=True)
class GeoReading:
    """An already-evaluated geofence reading from the device/integration layer.

    Carries the inside/outside DECISION and a coarse distance band only — never
    raw coordinates (location minimisation)."""

    decision: GeoDecision
    zone_label: str = ""          # e.g. "main_campus" — a label, not a coordinate
    distance_band: str = ""       # e.g. "on_site" | "near" | "far"
    confidence: float = 1.0


@dataclass(frozen=True)
class GeoProposal:
    """A geofence-assisted PROPOSAL for a staff member. Never a finalised mark.

    Feeds :func:`app.staff.record_staff` (capture_method=DEVICE) as a draft a
    human confirms. ``needs_review`` is set on any non-clean reading.
    """

    staff_uuid: str
    decision: GeoDecision
    zone_label: str
    proposed_status: Optional[StaffStatus]
    confidence: float
    needs_review: bool
    capture_method: CaptureMethod = CaptureMethod.DEVICE
    note: str = ""


def propose_from_geofence(
    staff_uuid: str,
    reading: GeoReading,
    consent: Optional[GeoConsent],
) -> Optional[GeoProposal]:
    """Turn a consented geofence reading into a staff-attendance PROPOSAL.

    Returns ``None`` — producing nothing — unless a matching, granted
    :class:`GeoConsent` is supplied (fail-closed, consent-gated). Even with
    consent the result is only a proposal: an INSIDE reading proposes PRESENT,
    an OUTSIDE reading proposes nothing decisive (a human checks why), and any
    low-confidence or UNKNOWN reading is flagged ``needs_review``. Geofencing
    NEVER auto-marks a staff member absent.
    """

    assert_no_pii_identifier(staff_uuid)
    if consent is None or not consent.granted or consent.staff_uuid != staff_uuid:
        return None  # no consent -> no location signal at all

    if reading.decision is GeoDecision.INSIDE:
        proposed: Optional[StaffStatus] = StaffStatus.PRESENT
        note = "inside_campus_geofence"
    else:
        # OUTSIDE / UNKNOWN: never auto-mark absent — surface for a human.
        proposed = None
        note = "outside_or_unknown_geofence"

    needs_review = (
        reading.decision is not GeoDecision.INSIDE or reading.confidence < 0.5
    )
    return GeoProposal(
        staff_uuid=staff_uuid,
        decision=reading.decision,
        zone_label=reading.zone_label,
        proposed_status=proposed,
        confidence=float(reading.confidence),
        needs_review=needs_review,
        note=note,
    )
