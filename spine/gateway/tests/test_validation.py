"""Schema validation: malformed requests rejected before routing."""

import pytest

from app.validation import (
    FieldSpec,
    FieldType,
    RequestSchema,
    RequestValidationError,
    SchemaRegistry,
    is_valid,
    validate,
)


def _schema():
    return RequestSchema(
        fields={
            "subject_uuid": FieldSpec(FieldType.STRING, required=True, min_length=1),
            "count": FieldSpec(FieldType.INTEGER, minimum=0, maximum=10),
            "mode": FieldSpec(FieldType.STRING, choices=("a", "b")),
            "note": FieldSpec(FieldType.STRING, max_length=5, free_text=True),
        },
        strict=True,
    )


def test_valid_payload_passes():
    validate({"subject_uuid": "u1", "count": 3, "mode": "a"}, _schema())


def test_missing_required_field_rejected():
    with pytest.raises(RequestValidationError) as ei:
        validate({"count": 1}, _schema())
    assert any("subject_uuid" in e.path for e in ei.value.errors)


def test_wrong_type_rejected():
    with pytest.raises(RequestValidationError):
        validate({"subject_uuid": "u1", "count": "three"}, _schema())


def test_bool_is_not_integer():
    with pytest.raises(RequestValidationError):
        validate({"subject_uuid": "u1", "count": True}, _schema())


def test_out_of_bounds_rejected():
    assert is_valid({"subject_uuid": "u1", "count": 11}, _schema()) is False
    assert is_valid({"subject_uuid": "u1", "count": -1}, _schema()) is False


def test_bad_choice_rejected():
    with pytest.raises(RequestValidationError):
        validate({"subject_uuid": "u1", "mode": "z"}, _schema())


def test_unknown_field_rejected_in_strict_mode():
    with pytest.raises(RequestValidationError) as ei:
        validate({"subject_uuid": "u1", "injected": "x"}, _schema())
    assert any("injected" in e.path for e in ei.value.errors)


def test_non_strict_allows_extra_fields():
    schema = RequestSchema(
        fields={"a": FieldSpec(FieldType.STRING, required=True)}, strict=False
    )
    validate({"a": "x", "extra": 1}, schema)


def test_max_length_enforced():
    with pytest.raises(RequestValidationError):
        validate({"subject_uuid": "u1", "note": "toolong"}, _schema())


def test_pattern_enforced():
    schema = RequestSchema(
        fields={"code": FieldSpec(FieldType.STRING, pattern=r"^[A-Z]{3}$")}
    )
    validate({"code": "ABC"}, schema)
    with pytest.raises(RequestValidationError):
        validate({"code": "abc"}, schema)


def test_nested_object_schema():
    inner = RequestSchema(fields={"x": FieldSpec(FieldType.INTEGER, required=True)})
    outer = RequestSchema(
        fields={"obj": FieldSpec(FieldType.OBJECT, required=True, schema=inner)}
    )
    validate({"obj": {"x": 1}}, outer)
    with pytest.raises(RequestValidationError):
        validate({"obj": {"x": "nope"}}, outer)


def test_typed_array_items():
    schema = RequestSchema(
        fields={
            "ids": FieldSpec(
                FieldType.ARRAY,
                items=FieldSpec(FieldType.STRING, min_length=1),
                min_length=1,
            )
        }
    )
    validate({"ids": ["a", "b"]}, schema)
    with pytest.raises(RequestValidationError):
        validate({"ids": [1, 2]}, schema)
    with pytest.raises(RequestValidationError):
        validate({"ids": []}, schema)  # below min_length


def test_error_message_has_no_values_only_paths():
    schema = _schema()
    with pytest.raises(RequestValidationError) as ei:
        validate({"subject_uuid": "secret-uuid", "count": 999}, schema)
    msg = str(ei.value)
    assert "999" not in msg  # never echoes the offending value
    assert "count" in msg


def test_registry_lookup_and_validate():
    reg = SchemaRegistry()
    reg.register("learning.read", _schema())
    assert reg.has("learning.read")
    reg.validate("learning.read", {"subject_uuid": "u1"})
    with pytest.raises(RequestValidationError):
        reg.validate("learning.read", {})


def test_registry_unknown_route_is_strict_empty():
    reg = SchemaRegistry()
    # unregistered route accepts only an empty body.
    reg.validate("nope.read", {})
    with pytest.raises(RequestValidationError):
        reg.validate("nope.read", {"anything": 1})
