"""Request schema validation at the wall.

A malformed request is rejected BEFORE it is routed to any capability module.
Validation is pluggable per route: each routable capability declares a
:class:`RequestSchema`, and the wall validates the incoming payload against it
prior to RBAC/ABAC/consent evaluation and dispatch.

The validator is dependency-free (stdlib only) and import-safe. It is
deliberately small but covers the shapes the gateway needs:

  - required / optional fields
  - primitive types (str, int, float, bool, dict, list)
  - bounds (min/max length, min/max value)
  - enums (choices)
  - regex pattern match
  - nested object schemas and typed list items
  - rejection of unknown fields (strict by default -- the wall does not forward
    fields a module did not declare)

CHILD-SAFETY: free-text fields are flagged with ``free_text=True``. The wall
uses that flag to route those fields through the child-safety screen before the
request is forwarded. Validation never logs the field VALUE (it may contain
PII / free text); errors reference the field PATH only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


_PY_TYPES = {
    FieldType.STRING: str,
    FieldType.INTEGER: int,
    FieldType.NUMBER: (int, float),
    FieldType.BOOLEAN: bool,
    FieldType.OBJECT: dict,
    FieldType.ARRAY: list,
}


@dataclass(frozen=True)
class FieldSpec:
    type: FieldType
    required: bool = False
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    choices: Optional[Tuple[Any, ...]] = None
    pattern: Optional[str] = None
    # For OBJECT fields: a nested schema.
    schema: Optional["RequestSchema"] = None
    # For ARRAY fields: the spec each item must satisfy.
    items: Optional["FieldSpec"] = None
    # CHILD-SAFETY: marks a free-text surface the wall must screen.
    free_text: bool = False

    def __post_init__(self) -> None:
        if self.type is FieldType.OBJECT and self.schema is None:
            # objects without a declared schema are allowed but opaque
            pass
        if self.pattern is not None:
            # compile eagerly so a bad pattern fails at declaration, not request
            re.compile(self.pattern)


@dataclass(frozen=True)
class RequestSchema:
    """Declares the accepted shape of a request body for one route."""

    fields: Dict[str, FieldSpec] = field(default_factory=dict)
    # When True, fields not declared here are rejected.
    strict: bool = True

    def free_text_fields(self) -> List[str]:
        return [name for name, spec in self.fields.items() if spec.free_text]


@dataclass(frozen=True)
class ValidationError:
    path: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.path}: {self.message}"


class RequestValidationError(Exception):
    """Aggregate validation failure. The wall maps this to HTTP 422.

    The message intentionally contains field PATHS and rule names only, never
    field values.
    """

    def __init__(self, errors: List[ValidationError]):
        self.errors = errors
        super().__init__(
            "request validation failed: "
            + "; ".join(str(e) for e in errors)
        )


def _type_name(spec_type: FieldType) -> str:
    return spec_type.value


def _validate_field(
    path: str, spec: FieldSpec, value: Any, errors: List[ValidationError]
) -> None:
    py_type = _PY_TYPES[spec.type]

    # bool is a subclass of int in Python -- guard so a bool is not an integer.
    if spec.type in (FieldType.INTEGER, FieldType.NUMBER) and isinstance(
        value, bool
    ):
        errors.append(
            ValidationError(path, f"expected {_type_name(spec.type)}, got boolean")
        )
        return

    if not isinstance(value, py_type):
        errors.append(
            ValidationError(path, f"expected {_type_name(spec.type)}")
        )
        return

    if spec.type is FieldType.STRING:
        if spec.min_length is not None and len(value) < spec.min_length:
            errors.append(
                ValidationError(path, f"shorter than min_length {spec.min_length}")
            )
        if spec.max_length is not None and len(value) > spec.max_length:
            errors.append(
                ValidationError(path, f"longer than max_length {spec.max_length}")
            )
        if spec.pattern is not None and not re.search(spec.pattern, value):
            errors.append(ValidationError(path, "does not match required pattern"))

    if spec.type in (FieldType.INTEGER, FieldType.NUMBER):
        if spec.minimum is not None and value < spec.minimum:
            errors.append(ValidationError(path, f"below minimum {spec.minimum}"))
        if spec.maximum is not None and value > spec.maximum:
            errors.append(ValidationError(path, f"above maximum {spec.maximum}"))

    if spec.choices is not None and value not in spec.choices:
        errors.append(ValidationError(path, "not an allowed value"))

    if spec.type is FieldType.OBJECT and spec.schema is not None:
        _validate_object(path, spec.schema, value, errors)

    if spec.type is FieldType.ARRAY:
        if spec.min_length is not None and len(value) < spec.min_length:
            errors.append(
                ValidationError(path, f"fewer than min_length {spec.min_length}")
            )
        if spec.max_length is not None and len(value) > spec.max_length:
            errors.append(
                ValidationError(path, f"more than max_length {spec.max_length}")
            )
        if spec.items is not None:
            for i, item in enumerate(value):
                _validate_field(f"{path}[{i}]", spec.items, item, errors)


def _validate_object(
    prefix: str,
    schema: RequestSchema,
    payload: Any,
    errors: List[ValidationError],
) -> None:
    if not isinstance(payload, dict):
        errors.append(ValidationError(prefix or "<root>", "expected object"))
        return

    if schema.strict:
        declared = set(schema.fields.keys())
        for key in payload.keys():
            if key not in declared:
                p = f"{prefix}.{key}" if prefix else key
                errors.append(ValidationError(p, "unknown field"))

    for name, spec in schema.fields.items():
        path = f"{prefix}.{name}" if prefix else name
        if name not in payload or payload[name] is None:
            if spec.required:
                errors.append(ValidationError(path, "required field is missing"))
            continue
        _validate_field(path, spec, payload[name], errors)


def validate(payload: Any, schema: RequestSchema) -> None:
    """Validate ``payload`` against ``schema``; raise on any failure."""
    errors: List[ValidationError] = []
    _validate_object("", schema, payload, errors)
    if errors:
        raise RequestValidationError(errors)


def is_valid(payload: Any, schema: RequestSchema) -> bool:
    try:
        validate(payload, schema)
        return True
    except RequestValidationError:
        return False


# --------------------------------------------------------------------------- #
# Registry of per-route schemas
# --------------------------------------------------------------------------- #


class SchemaRegistry:
    """Maps a route/capability id to its declared request schema.

    The wall looks up a schema here before routing. A route with no registered
    schema is treated as accepting an empty body in ``strict`` mode -- i.e. it
    rejects any unexpected payload rather than forwarding it blindly.
    """

    _EMPTY = RequestSchema(fields={}, strict=True)

    def __init__(self) -> None:
        self._schemas: Dict[str, RequestSchema] = {}

    def register(self, route: str, schema: RequestSchema) -> None:
        self._schemas[route] = schema

    def get(self, route: str) -> RequestSchema:
        return self._schemas.get(route, self._EMPTY)

    def has(self, route: str) -> bool:
        return route in self._schemas

    def validate(self, route: str, payload: Any) -> None:
        validate(payload, self.get(route))
