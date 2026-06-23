"""Roster import maps to opaque ids with NO PII bleed (INVARIANT 1, 2).

Covers OneRoster CSV + REST, Clever, ClassLink, Ed-Fi. The crux assertion: a raw
record full of names/emails/SIS ids produces mapped objects that, serialised for
the seam, contain NONE of those values and trip ``assert_no_pii`` if they did.
"""

from __future__ import annotations

import json

from app import (
    Role,
    RosterImportResult,
    Standard,
    assert_no_pii,
    derive_source_key,
)
from app.adapters import (
    ClassLinkAdapter,
    CleverAdapter,
    EdFiAdapter,
    OneRosterAdapter,
)
from app.models import PIILeakError
from app.mapping import map_identity, strip_pii


def _serialized_blob(result: RosterImportResult) -> str:
    return json.dumps(result.to_safe_dict())


# ---------------------------------------------------------------------------
# OneRoster CSV
# ---------------------------------------------------------------------------
ORGS_CSV = "sourcedId,type,name,parentSourcedId\norg-1,school,Greenwood High,\n"
CLASSES_CSV = (
    "sourcedId,schoolSourcedId,title,grades,subjectCodes,courseSourcedId\n"
    "cls-1,org-1,Grade 7 Math,07,MATH,crs-1\n"
)
USERS_CSV = (
    "sourcedId,role,givenName,familyName,email\n"
    "usr-1,student,Asha,Verma,asha.verma@example.com\n"
    "usr-2,teacher,Ravi,Kumar,ravi.kumar@example.com\n"
    ",student,Orphan,NoId,orphan@example.com\n"
)
ENROLL_CSV = (
    "userSourcedId,classSourcedId,role,primary\n"
    "usr-1,cls-1,student,false\n"
    "usr-2,cls-1,teacher,true\n"
)


def test_oneroster_csv_maps_to_opaque_ids_with_no_pii():
    adapter = OneRosterAdapter("oneroster:test")
    result = adapter.import_csv(
        orgs_csv=ORGS_CSV,
        classes_csv=CLASSES_CSV,
        users_csv=USERS_CSV,
        enrollments_csv=ENROLL_CSV,
    )

    assert result.person_count == 2  # the id-less third row is skipped
    assert result.skipped == 1
    assert {p.role for p in result.persons} == {Role.STUDENT, Role.TEACHER}

    blob = _serialized_blob(result)
    for leaked in ("Asha", "Verma", "asha.verma@example.com", "Ravi", "ravi.kumar"):
        assert leaked not in blob, f"PII '{leaked}' bled into the mapped roster"

    # source keys are opaque, salted, and stable across re-import.
    assert all(p.ref.source_key.startswith("oneroster-1.2:") for p in result.persons)
    again = adapter.import_csv(users_csv=USERS_CSV)
    assert again.persons[0].ref.source_key == result.persons[0].ref.source_key
    # canonical_uuid unresolved offline (no identity resolver) -> None.
    assert all(p.ref.canonical_uuid is None for p in result.persons)


def test_oneroster_csv_serialisation_passes_no_pii_backstop():
    adapter = OneRosterAdapter("oneroster:test")
    result = adapter.import_csv(users_csv=USERS_CSV, enrollments_csv=ENROLL_CSV)
    # to_safe_dict runs assert_no_pii internally; a clean dict round-trips.
    safe = result.to_safe_dict()
    assert_no_pii(safe, where="test")
    assert safe["standard"] == Standard.ONEROSTER_1_2.value


def test_assert_no_pii_catches_a_buried_email():
    bad = {"persons": [{"source_key": "x", "email": "leak@example.com"}]}
    raised = False
    try:
        assert_no_pii(bad)
    except PIILeakError:
        raised = True
    assert raised, "assert_no_pii must reject a buried PII field"


# ---------------------------------------------------------------------------
# OneRoster REST JSON
# ---------------------------------------------------------------------------
def test_oneroster_rest_maps_users_and_enrollments():
    adapter = OneRosterAdapter("oneroster:test")
    result = adapter.import_rest(
        orgs=[{"sourcedId": "org-1", "type": "school"}],
        classes=[{
            "sourcedId": "cls-1",
            "school": {"sourcedId": "org-1"},
            "subjects": ["Mathematics"],
            "grades": ["07"],
        }],
        users=[
            {"sourcedId": "u1", "roles": [{"role": "student"}],
             "givenName": "Mira", "email": "mira@example.com"},
        ],
        enrollments=[{"user": {"sourcedId": "u1"}, "class": {"sourcedId": "cls-1"}, "role": "student"}],
    )
    assert result.person_count == 1
    assert result.persons[0].role is Role.STUDENT
    assert result.classes[0].subject_code == "Mathematics"
    blob = _serialized_blob(result)
    assert "Mira" not in blob and "mira@example.com" not in blob


# ---------------------------------------------------------------------------
# Clever / ClassLink
# ---------------------------------------------------------------------------
def test_clever_roster_drops_pii_and_builds_enrollments():
    adapter = CleverAdapter("clever:test")
    result = adapter.import_roster(
        districts=[{"id": "d1", "name": "Metro District"}],
        schools=[{"id": "s1", "district": "d1", "name": "Metro High"}],
        sections=[{
            "id": "sec1", "school": "s1", "subject": "math",
            "teachers": ["t1"], "students": ["p1", "p2"],
        }],
        students=[{"id": "p1", "name": {"first": "Lee"}, "email": "lee@example.com", "sis_id": "SIS-1"}],
        teachers=[{"id": "t1", "name": {"first": "Sam"}, "email": "sam@example.com"}],
    )
    # 1 student + 1 teacher
    assert result.person_count == 2
    # section membership -> 1 teacher (primary) + 2 student enrollments
    roles = [(e.role, e.primary) for e in result.enrollments]
    assert (Role.TEACHER, True) in roles
    assert roles.count((Role.STUDENT, False)) == 2

    blob = _serialized_blob(result)
    for leaked in ("Lee", "lee@example.com", "SIS-1", "Sam", "sam@example.com"):
        assert leaked not in blob


def test_classlink_uses_sourcedid_field():
    adapter = ClassLinkAdapter("classlink:test")
    result = adapter.import_roster(
        students=[{"sourcedId": "cl-1", "name": "Pat", "email": "pat@example.com"}],
    )
    assert result.person_count == 1
    assert result.persons[0].ref.source_key.startswith("classlink:")
    assert "Pat" not in _serialized_blob(result)


# ---------------------------------------------------------------------------
# Ed-Fi
# ---------------------------------------------------------------------------
def test_edfi_maps_students_staff_and_associations():
    adapter = EdFiAdapter("edfi:test")
    result = adapter.import_resources(
        schools=[{"schoolId": 255901001, "nameOfInstitution": "Grand High"}],
        sections=[{
            "sectionIdentifier": "ALG-1",
            "schoolReference": {"schoolId": 255901001},
            "courseOfferingReference": {"localCourseCode": "ALG1"},
        }],
        students=[{"studentUniqueId": "604821", "firstName": "Dana", "lastSurname": "Quill"}],
        staff=[{"staffUniqueId": "S-77", "firstName": "Reed"}],
        student_section_associations=[{
            "studentReference": {"studentUniqueId": "604821"},
            "sectionReference": {"sectionIdentifier": "ALG-1"},
        }],
        staff_section_associations=[{
            "staffReference": {"staffUniqueId": "S-77"},
            "sectionReference": {"sectionIdentifier": "ALG-1"},
        }],
    )
    assert result.person_count == 2
    assert any(e.role is Role.STUDENT for e in result.enrollments)
    assert any(e.role is Role.TEACHER and e.primary for e in result.enrollments)
    blob = _serialized_blob(result)
    for leaked in ("Dana", "Quill", "604821", "Reed"):
        assert leaked not in blob


def test_strip_pii_removes_known_fields():
    record = {"sourcedId": "u1", "givenName": "X", "email": "x@y.z", "nested": {"phone": "123", "role": "student"}}
    cleaned = strip_pii(record)
    assert cleaned == {"sourcedId": "u1", "nested": {"role": "student"}}


def test_source_key_is_one_way_and_salt_scoped():
    a = derive_source_key(Standard.CLEVER, "abc")
    b = derive_source_key(Standard.CLEVER, "abc")
    c = derive_source_key(Standard.ONEROSTER_1_2, "abc")
    assert a == b  # stable
    assert "abc" not in a  # one-way
    assert a != c  # scoped by standard
