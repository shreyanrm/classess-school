"""Ed-Fi adapter (spine A6).

Maps Ed-Fi Data Standard resources (educationOrganizations, schools, sections,
students, staff, studentSectionAssociations, staffSectionAssociations) into the
PII-free internal shapes.

Ed-Fi student/staff resources carry a ``*UniqueId`` plus name fields; only the
unique id is consumed for the salted source_key — names are dropped at the seam
(INVARIANT 1, 2). No live endpoint required; the REST fetch would go through the
gateway.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..connector import Capability, Connector, Direction
from ..mapping import IdentityResolver, map_identity
from ..models import (
    MappedClass,
    MappedEnrollment,
    MappedOrg,
    MappedPerson,
    Role,
    RosterImportResult,
    Standard,
)


class EdFiAdapter(Connector):
    standard = Standard.EDFI

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "roster.import", Direction.INBOUND,
                "Import Ed-Fi resources into PII-free internal shapes.",
            ),
            Capability(
                "descriptors.import", Direction.INBOUND,
                "Map Ed-Fi academic-subject descriptors onto ontology candidates.",
            ),
        ]

    def import_resources(
        self,
        *,
        education_organizations: Iterable[dict[str, Any]] = (),
        schools: Iterable[dict[str, Any]] = (),
        sections: Iterable[dict[str, Any]] = (),
        students: Iterable[dict[str, Any]] = (),
        staff: Iterable[dict[str, Any]] = (),
        student_section_associations: Iterable[dict[str, Any]] = (),
        staff_section_associations: Iterable[dict[str, Any]] = (),
        identity_resolver: IdentityResolver | None = None,
    ) -> RosterImportResult:
        result = RosterImportResult(standard=self.standard)

        for eo in education_organizations:
            eoid = eo.get("educationOrganizationId")
            if eoid is None:
                result.skipped += 1
                continue
            result.orgs.append(MappedOrg(source_key=str(eoid), kind="education-organization"))

        for sc in schools:
            scid = sc.get("schoolId")
            if scid is None:
                result.skipped += 1
                continue
            parent = sc.get("localEducationAgencyReference") or {}
            result.orgs.append(
                MappedOrg(
                    source_key=str(scid),
                    kind="school",
                    parent_source_key=(
                        str(parent.get("localEducationAgencyId"))
                        if isinstance(parent, dict) and parent.get("localEducationAgencyId") is not None
                        else None
                    ),
                )
            )

        for sec in sections:
            sid = sec.get("sectionIdentifier")
            if not sid:
                result.skipped += 1
                continue
            school_ref = sec.get("schoolReference") or {}
            course_ref = sec.get("courseOfferingReference") or {}
            result.classes.append(
                MappedClass(
                    source_key=str(sid),
                    org_source_key=str(school_ref.get("schoolId", "")) if isinstance(school_ref, dict) else "",
                    course_source_key=(
                        str(course_ref.get("localCourseCode"))
                        if isinstance(course_ref, dict) and course_ref.get("localCourseCode")
                        else None
                    ),
                )
            )

        for s in students:
            uid = s.get("studentUniqueId")
            if not uid:
                result.skipped += 1
                result.warnings.append("student missing studentUniqueId; skipped")
                continue
            ref = map_identity(self.standard, str(uid), resolver=identity_resolver)
            result.persons.append(MappedPerson(ref=ref, role=Role.STUDENT))

        for st in staff:
            uid = st.get("staffUniqueId")
            if not uid:
                result.skipped += 1
                continue
            ref = map_identity(self.standard, str(uid), resolver=identity_resolver)
            result.persons.append(MappedPerson(ref=ref, role=Role.STAFF))

        for assoc in student_section_associations:
            student_ref = assoc.get("studentReference") or {}
            section_ref = assoc.get("sectionReference") or {}
            uid = student_ref.get("studentUniqueId") if isinstance(student_ref, dict) else None
            sec_id = section_ref.get("sectionIdentifier") if isinstance(section_ref, dict) else None
            if not uid or not sec_id:
                result.skipped += 1
                continue
            ref = map_identity(self.standard, str(uid), resolver=identity_resolver)
            result.enrollments.append(MappedEnrollment(ref, str(sec_id), Role.STUDENT))

        for assoc in staff_section_associations:
            staff_ref = assoc.get("staffReference") or {}
            section_ref = assoc.get("sectionReference") or {}
            uid = staff_ref.get("staffUniqueId") if isinstance(staff_ref, dict) else None
            sec_id = section_ref.get("sectionIdentifier") if isinstance(section_ref, dict) else None
            if not uid or not sec_id:
                result.skipped += 1
                continue
            ref = map_identity(self.standard, str(uid), resolver=identity_resolver)
            result.enrollments.append(MappedEnrollment(ref, str(sec_id), Role.TEACHER, primary=True))

        return result
