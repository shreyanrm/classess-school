"""OneRoster 1.2 adapter (spine A6).

Imports a OneRoster roster (orgs, classes, users, enrollments) and maps it into
the PII-free internal shapes. Supports both the CSV bulk format and the REST
JSON resource shape. The keystone discipline: every user record arrives WITH PII
(``givenName``, ``familyName``, ``email``, ``sourcedId``) — only the opaque
``sourcedId`` is consumed to derive a salted source_key; all name/email fields
are dropped at the seam (INVARIANT 1, 2).

Also maps OneRoster ``lineItems``/learning-objectives onto ontology candidates.

No live endpoint required — parses in-process structures. The REST fetch (which
WOULD go through the gateway) is described in capabilities only; this adapter
performs no network call.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Iterable

from ..connector import Capability, Connector, Direction
from ..mapping import IdentityResolver, OntologyResolver, map_identity, map_outcome, normalize_role
from ..models import (
    MappedClass,
    MappedEnrollment,
    MappedOrg,
    MappedOutcome,
    MappedPerson,
    RosterImportResult,
    Standard,
)


class OneRosterAdapter(Connector):
    standard = Standard.ONEROSTER_1_2

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "roster.import.csv", Direction.INBOUND,
                "Import a OneRoster 1.2 CSV bulk set into PII-free internal shapes.",
            ),
            Capability(
                "roster.import.rest", Direction.INBOUND,
                "Import OneRoster 1.2 REST JSON resources (fetched via the gateway).",
            ),
            Capability(
                "outcomes.import", Direction.INBOUND,
                "Map OneRoster learning objectives onto ontology candidates.",
            ),
            Capability(
                "results.passback", Direction.OUTBOUND,
                "Write line-item results back (via a governed gateway capability).",
                consequential=True,
            ),
        ]

    # -- CSV bulk import ----------------------------------------------------
    def import_csv(
        self,
        *,
        orgs_csv: str = "",
        classes_csv: str = "",
        users_csv: str = "",
        enrollments_csv: str = "",
        identity_resolver: IdentityResolver | None = None,
    ) -> RosterImportResult:
        result = RosterImportResult(standard=self.standard)

        for row in _rows(orgs_csv):
            sid = row.get("sourcedId")
            if not sid:
                result.skipped += 1
                continue
            result.orgs.append(
                MappedOrg(
                    source_key=sid,
                    kind=(row.get("type") or "org").lower(),
                    parent_source_key=row.get("parentSourcedId") or None,
                )
            )

        for row in _rows(classes_csv):
            sid = row.get("sourcedId")
            if not sid:
                result.skipped += 1
                continue
            result.classes.append(
                MappedClass(
                    source_key=sid,
                    org_source_key=row.get("schoolSourcedId", ""),
                    subject_code=row.get("subjectCodes") or row.get("subjects") or None,
                    grade=row.get("grades") or None,
                    course_source_key=row.get("courseSourcedId") or None,
                )
            )

        for row in _rows(users_csv):
            sid = row.get("sourcedId")
            if not sid:
                result.skipped += 1
                result.warnings.append("user row missing sourcedId; skipped")
                continue
            # PII (givenName/familyName/email) is present here and DROPPED — only
            # the opaque sourcedId is used to derive the salted source_key.
            ref = map_identity(self.standard, sid, resolver=identity_resolver)
            role = normalize_role(row.get("role"))
            result.persons.append(MappedPerson(ref=ref, role=role))

        for row in _rows(enrollments_csv):
            user_sid = row.get("userSourcedId")
            class_sid = row.get("classSourcedId")
            if not user_sid or not class_sid:
                result.skipped += 1
                continue
            ref = map_identity(self.standard, user_sid, resolver=identity_resolver)
            result.enrollments.append(
                MappedEnrollment(
                    person=ref,
                    class_source_key=class_sid,
                    role=normalize_role(row.get("role")),
                    primary=(str(row.get("primary", "")).lower() in {"true", "1", "yes"}),
                )
            )

        return result

    # -- REST JSON import ---------------------------------------------------
    def import_rest(
        self,
        *,
        orgs: Iterable[dict[str, Any]] = (),
        classes: Iterable[dict[str, Any]] = (),
        users: Iterable[dict[str, Any]] = (),
        enrollments: Iterable[dict[str, Any]] = (),
        identity_resolver: IdentityResolver | None = None,
    ) -> RosterImportResult:
        result = RosterImportResult(standard=self.standard)

        for o in orgs:
            sid = o.get("sourcedId")
            if not sid:
                result.skipped += 1
                continue
            parent = o.get("parent") or {}
            result.orgs.append(
                MappedOrg(
                    source_key=sid,
                    kind=(o.get("type") or "org").lower(),
                    parent_source_key=parent.get("sourcedId") if isinstance(parent, dict) else None,
                )
            )

        for c in classes:
            sid = c.get("sourcedId")
            if not sid:
                result.skipped += 1
                continue
            school = c.get("school") or {}
            course = c.get("course") or {}
            subjects = c.get("subjects") or c.get("subjectCodes")
            if isinstance(subjects, list):
                subjects = ",".join(subjects)
            grades = c.get("grades")
            if isinstance(grades, list):
                grades = ",".join(grades)
            result.classes.append(
                MappedClass(
                    source_key=sid,
                    org_source_key=(school.get("sourcedId") if isinstance(school, dict) else "") or "",
                    subject_code=subjects or None,
                    grade=grades or None,
                    course_source_key=(course.get("sourcedId") if isinstance(course, dict) else None),
                )
            )

        for u in users:
            sid = u.get("sourcedId")
            if not sid:
                result.skipped += 1
                result.warnings.append("user resource missing sourcedId; skipped")
                continue
            ref = map_identity(self.standard, sid, resolver=identity_resolver)
            roles = u.get("roles") or []
            raw_role = u.get("role")
            if not raw_role and roles:
                first = roles[0]
                raw_role = first.get("role") if isinstance(first, dict) else first
            result.persons.append(MappedPerson(ref=ref, role=normalize_role(raw_role)))

        for e in enrollments:
            user = e.get("user") or {}
            klass = e.get("class") or {}
            user_sid = user.get("sourcedId") if isinstance(user, dict) else None
            class_sid = klass.get("sourcedId") if isinstance(klass, dict) else None
            if not user_sid or not class_sid:
                result.skipped += 1
                continue
            ref = map_identity(self.standard, user_sid, resolver=identity_resolver)
            result.enrollments.append(
                MappedEnrollment(
                    person=ref,
                    class_source_key=class_sid,
                    role=normalize_role(e.get("role")),
                    primary=bool(e.get("primary", False)),
                )
            )

        return result

    # -- outcomes -----------------------------------------------------------
    def import_outcomes(
        self,
        objectives: Iterable[dict[str, Any]],
        *,
        ontology_resolver: OntologyResolver | None = None,
    ) -> list[MappedOutcome]:
        out: list[MappedOutcome] = []
        for o in objectives:
            code = o.get("sourcedId") or o.get("code")
            if not code:
                continue
            out.append(
                map_outcome(
                    self.standard,
                    code,
                    human_label=o.get("title") or o.get("description") or code,
                    framework=o.get("source") or o.get("framework"),
                    resolver=ontology_resolver,
                )
            )
        return out


def _rows(blob: str) -> list[dict[str, str]]:
    if not blob or not blob.strip():
        return []
    reader = csv.DictReader(io.StringIO(blob.strip()))
    return [dict(r) for r in reader]
