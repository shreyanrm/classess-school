"""Clever and ClassLink roster-sync adapters (spine A6).

Both speak a SIS-sync JSON shape (districts, schools, sections, students,
teachers). Records arrive WITH PII (name, email, sis_id, student_number); only
the opaque provider id is consumed for the salted source_key — all PII is
dropped at the seam (INVARIANT 1, 2).

Clever and ClassLink share the mapping engine; they differ only in field names,
captured in a small field map per provider. No live endpoint required.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..connector import Capability, Connector, Direction
from ..mapping import IdentityResolver, map_identity, normalize_role
from ..models import (
    MappedClass,
    MappedEnrollment,
    MappedOrg,
    MappedPerson,
    Role,
    RosterImportResult,
    Standard,
)


class _RosterSyncAdapter(Connector):
    """Shared Clever/ClassLink mapping. Subclasses set ``standard``/``_id_field``."""

    _id_field = "id"

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "roster.sync", Direction.INBOUND,
                f"Sync a {self.standard.value} roster into PII-free internal shapes.",
            ),
            Capability(
                "roster.delta", Direction.INBOUND,
                "Apply an incremental roster delta (adds/changes/removes).",
            ),
        ]

    def _id(self, record: dict[str, Any]) -> str | None:
        return record.get(self._id_field) or record.get("id") or record.get("sourcedId")

    def import_roster(
        self,
        *,
        districts: Iterable[dict[str, Any]] = (),
        schools: Iterable[dict[str, Any]] = (),
        sections: Iterable[dict[str, Any]] = (),
        students: Iterable[dict[str, Any]] = (),
        teachers: Iterable[dict[str, Any]] = (),
        identity_resolver: IdentityResolver | None = None,
    ) -> RosterImportResult:
        result = RosterImportResult(standard=self.standard)

        for d in districts:
            did = self._id(d)
            if did:
                result.orgs.append(MappedOrg(source_key=did, kind="district"))

        for s in schools:
            sid = self._id(s)
            if not sid:
                result.skipped += 1
                continue
            result.orgs.append(
                MappedOrg(
                    source_key=sid,
                    kind="school",
                    parent_source_key=s.get("district") or s.get("districtId"),
                )
            )

        for sec in sections:
            sid = self._id(sec)
            if not sid:
                result.skipped += 1
                continue
            mapped = MappedClass(
                source_key=sid,
                org_source_key=sec.get("school") or sec.get("schoolId") or "",
                subject_code=sec.get("subject"),
                grade=sec.get("grade"),
                course_source_key=sec.get("course") or sec.get("courseId"),
            )
            result.classes.append(mapped)
            # Section membership -> enrollments (ids only, never PII).
            for tid in _as_list(sec.get("teachers") or sec.get("teacher")):
                ref = map_identity(self.standard, str(tid), resolver=identity_resolver)
                result.enrollments.append(
                    MappedEnrollment(ref, sid, Role.TEACHER, primary=True)
                )
            for stud in _as_list(sec.get("students")):
                ref = map_identity(self.standard, str(stud), resolver=identity_resolver)
                result.enrollments.append(MappedEnrollment(ref, sid, Role.STUDENT))

        for st in students:
            sid = self._id(st)
            if not sid:
                result.skipped += 1
                result.warnings.append("student missing id; skipped")
                continue
            ref = map_identity(self.standard, sid, resolver=identity_resolver)
            result.persons.append(MappedPerson(ref=ref, role=Role.STUDENT))

        for t in teachers:
            tid = self._id(t)
            if not tid:
                result.skipped += 1
                continue
            ref = map_identity(self.standard, tid, resolver=identity_resolver)
            role = normalize_role(t.get("role")) if t.get("role") else Role.TEACHER
            result.persons.append(MappedPerson(ref=ref, role=role))

        return result


class CleverAdapter(_RosterSyncAdapter):
    standard = Standard.CLEVER
    _id_field = "id"


class ClassLinkAdapter(_RosterSyncAdapter):
    standard = Standard.CLASSLINK
    _id_field = "sourcedId"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
