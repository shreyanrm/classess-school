"""Curriculum & ontology ingestion module (A2, Ring 1).

A2's ingestion pipeline over the board-agnostic ontology contract. The seed
ontology lives in ``contracts/src/ontology``; this module ingests curriculum
INTO that graph, stewards its prerequisite edges, maps equivalence across
boards, and indexes nodes semantically. The package surface:

  - ``ingest``      — ingests curriculum from documents / standards / publisher
                      content into the ontology graph. The document-understanding
                      step is an INTERFACE that degrades gracefully (Null
                      provider; structured-source path; never invents output).
                      Produces DRAFT nodes with a confidence gate.
  - ``steward``     — the prerequisite-edge steward. PROPOSES edges that must be
                      expert-confirmed before trusted; never auto-trusted.
  - ``equivalence`` — cross-board equivalence mapping. SYMMETRIC and
                      board-agnostic (every board is a code label).
  - ``embeddings``  — the pgvector semantic-index interface with an in-memory
                      fallback; Track 1 / Track 2 model lanes kept separate.
  - ``events``      — emit ontology lifecycle events on the contract envelope
                      (opaque ids only; append-only).
  - ``config``      — env-var NAMES only (degrades gracefully with none set).
  - ``seed``        — a Python view of the Slice 1 seed snapshot, mirroring the
                      contract for tests and projections.

Import-safe: importing the package, or any submodule, performs no I/O, reads no
secret value, and never requires a live provider. The deterministic (degraded)
paths are the supported paths until the gateway, document-understanding provider,
pgvector index, and event store are wired.
"""

from __future__ import annotations

from . import (  # noqa: F401
    config,
    embeddings,
    equivalence,
    events,
    ingest,
    seed,
    steward,
)

__all__ = [
    "config",
    "embeddings",
    "equivalence",
    "events",
    "ingest",
    "seed",
    "steward",
]

__version__ = "0.1.0"
