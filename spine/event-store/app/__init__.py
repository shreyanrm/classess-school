"""Classess Event Store — immutable, append-only behavioral store (Ring 0).

INVARIANT 5: emit a clean, attributed event for every meaningful action; events
are never mutated or deleted in place. There is deliberately NO update or delete
operation anywhere in this service.

INVARIANT 6: reads return only through a governed, consent + purpose-gated view
(platform.read_events). A read without a satisfied consent + purpose check
returns an empty set — never the rows, never a leak of existence.

INVARIANT 1/2: every stored row carries the opaque canonical_uuid only; the
payload is validated to contain no PII.
"""
