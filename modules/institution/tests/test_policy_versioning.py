"""Policy versioning + effective dates, and the extended hyperlocalization keys.

Covers the deepening for /admin/policies ("versioned with effective dates +
audit") and /admin/hyperlocalization (board terminology + local exam format as
policy).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.hierarchy import build_hierarchy
from app.policy import (
    PolicySet,
    PolicyError,
    PolicyVersion,
    LocalizationConfig,
    LOCALE_LANGUAGE,
    LOCALE_BOARD_TERMS,
    LOCALE_EXAM_FORMAT,
)


def _hierarchy():
    spec = [
        {"key": "g", "kind": "group", "label": "Example Group", "parent": None},
        {"key": "r", "kind": "region", "label": "Region West", "parent": "g"},
        {"key": "s", "kind": "school", "label": "Senior School", "parent": "r"},
        {"key": "sec", "kind": "section", "label": "Section 10-B", "parent": "s"},
    ]
    h = build_hierarchy("tenant-A", spec)
    ids = {n.label: n.id for n in h.all_nodes()}
    return h, ids


def test_set_policy_appends_versions_not_overwrites():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    ps.set_policy(ids["Senior School"], "grading.scheme", "marks",
                  effective_from=date(2025, 4, 1))
    ps.set_policy(ids["Senior School"], "grading.scheme", "competency",
                  effective_from=date(2026, 4, 1), note="board reform")

    hist = ps.history(ids["Senior School"], "grading.scheme")
    assert [v.version for v in hist] == [1, 2]
    assert hist[0].value == "marks" and hist[1].value == "competency"
    assert hist[1].note == "board reform"
    # History is the queryable audit trail — both versions retained.
    assert all(isinstance(v, PolicyVersion) for v in hist)


def test_resolution_is_effective_dated():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    ps.set_policy(ids["Senior School"], "grading.scheme", "marks",
                  effective_from=date(2025, 4, 1))
    ps.set_policy(ids["Senior School"], "grading.scheme", "competency",
                  effective_from=date(2026, 4, 1))

    # Before the new version's effective date -> old value still wins.
    old = ps.resolve(ids["Section 10-B"], "grading.scheme", as_of=date(2026, 1, 1))
    assert old.value == "marks"
    assert old.version == 1

    # On/after the effective date -> the staged version takes over.
    new = ps.resolve(ids["Section 10-B"], "grading.scheme", as_of=date(2026, 4, 1))
    assert new.value == "competency"
    assert new.version == 2
    assert new.effective_from == date(2026, 4, 1)
    assert "version 2" in new.why and "2026-04-01" in new.why


def test_future_dated_version_not_yet_in_force():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    # A version whose effective_from is entirely in the future is not in force
    # for an as-of before it.
    ps.set_policy(ids["Senior School"], "fee.late", 50,
                  effective_from=date(2027, 1, 1))
    assert ps.resolve(ids["Section 10-B"], "fee.late", as_of=date(2026, 6, 1)) is None
    assert ps.resolve(ids["Section 10-B"], "fee.late", as_of=date(2027, 6, 1)).value == 50


def test_lock_respects_effective_date():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    # Region stages a lock that only takes effect next year.
    ps.set_policy(ids["Region West"], "retention.months", 36, locked=True,
                  effective_from=date(2027, 4, 1))
    # Before the lock is effective, a descendant MAY still set its own value.
    ps.set_policy(ids["Senior School"], "retention.months", 6,
                  effective_from=date(2026, 4, 1))
    assert ps.resolve(ids["Section 10-B"], "retention.months",
                      as_of=date(2026, 6, 1)).value == 6
    # Once the lock is effective, it becomes the floor.
    locked = ps.resolve(ids["Section 10-B"], "retention.months", as_of=date(2027, 6, 1))
    assert locked.value == 36 and locked.locked is True


def test_setting_under_active_lock_is_rejected():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    ps.set_policy(ids["Region West"], "safety.min", "strict", locked=True,
                  effective_from=date(2025, 1, 1))
    with pytest.raises(PolicyError):
        ps.set_policy(ids["Senior School"], "safety.min", "lenient",
                      effective_from=date(2026, 1, 1))


def test_default_effective_is_immediate_and_backwards_compatible():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    # No effective_from -> takes effect today; resolve() with no as_of -> today.
    ps.set_policy(ids["Example Group"], "grading.scheme", "competency-based")
    resolved = ps.resolve(ids["Section 10-B"], "grading.scheme")
    assert resolved.value == "competency-based"
    assert resolved.inherited is True
    assert resolved.version == 1


def test_board_terminology_as_policy():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    terms = {"grade": "Standard", "section": "Division"}
    ps.set_policy(ids["Region West"], LOCALE_BOARD_TERMS, terms)
    loc = LocalizationConfig.from_policy_set(ps, ids["Section 10-B"])
    assert loc.board_terms == terms
    assert loc.term_for("grade") == "Standard"
    assert loc.term_for("school") is None  # uses the default
    # No terms set -> term_for returns None, no default invented.
    bare = LocalizationConfig.from_policy_set(PolicySet(h), ids["Section 10-B"])
    assert bare.board_terms is None and bare.term_for("grade") is None


def test_local_exam_format_as_policy_inherits_and_refines():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    region_fmt = {"name": "regional", "components": ["term1", "term2"]}
    school_fmt = {"name": "school-refined", "components": ["unit", "term1", "term2"]}
    ps.set_policy(ids["Region West"], LOCALE_EXAM_FORMAT, region_fmt)
    ps.set_policy(ids["Senior School"], LOCALE_EXAM_FORMAT, school_fmt)
    loc = LocalizationConfig.from_policy_set(ps, ids["Section 10-B"])
    assert loc.exam_format == school_fmt  # nearest refinement wins
    # The region keeps its own.
    at_region = LocalizationConfig.from_policy_set(ps, ids["Region West"])
    assert at_region.exam_format == region_fmt


def test_hyperlocalization_keys_no_default_invented():
    h, ids = _hierarchy()
    loc = LocalizationConfig.from_policy_set(PolicySet(h), ids["Section 10-B"])
    assert loc.language is None
    assert loc.board_terms is None
    assert loc.exam_format is None
