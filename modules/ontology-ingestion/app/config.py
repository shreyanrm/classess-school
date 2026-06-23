"""Ontology ingestion configuration (A2, Ring 1).

SECURITY INVARIANT (secrets ENV-ONLY): secrets are environment-only, read by
NAME, never hardcoded and never invented. Dotted names follow
``clss.<app>.<env>.<purpose>`` and map to ``CLSS_ONTOLOGY_DEV_*`` env vars
(uppercased, dots/dashes -> underscores). No secret value is ever a literal here
and no ``NEXT_PUBLIC_`` secret exists — ingestion is a server-side core service.

This module holds NO credentials. Every cross-service call (the
document-understanding provider, the embeddings/pgvector index, the event store)
passes the gateway; this names the gateway URL var but never stores a key value.
With no provider configured the deterministic paths all work:

  - document ingestion records DRAFT nodes with no invented extraction,
  - the steward proposes UNCONFIRMED prerequisite edges,
  - equivalence mapping runs as in-memory symmetric references,
  - the embeddings index falls back to a deterministic in-memory vector store,
  - event emission degrades to a clearly-labelled in-memory append-only sink.

TRACK SEPARATION: Track 1 (external model providers) and Track 2 (proprietary /
edge providers) are named in SEPARATE env vars and never merged. A live router
picks one lane; the config never blends them into a single key.

Import-safe: this module reads no environment VALUE and opens no connection at
import. Settings are resolved lazily by :func:`get_settings`, and only env-var
NAMES are ever referenced.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# Dotted secret/config NAMES (names only). Single source of truth shared by the
# README and the degraded-reasons report.
ENV_GATEWAY_URL = "clss.ontology.dev.gateway_url"
ENV_EVENT_SINK_URL = "clss.ontology.dev.event_sink_url"
ENV_DATABASE_URL = "clss.ontology.dev.database_url"
ENV_PGVECTOR_URL = "clss.ontology.dev.pgvector_url"

# Document-understanding (curriculum extraction). The live extraction provider
# the ingest interface would call THROUGH the gateway. Unset -> draft-only.
ENV_DOC_UNDERSTANDING_KEY = "clss.ontology.dev.doc_understanding_key"

# Embeddings model lanes — kept SEPARATE (Track 1 external vs Track 2 edge).
# A router selects a lane; config never blends them.
ENV_EMBEDDINGS_TRACK1_KEY = "clss.ontology.dev.embeddings_track1_key"  # external
ENV_EMBEDDINGS_TRACK2_KEY = "clss.ontology.dev.embeddings_track2_key"  # proprietary/edge

_ENV_PREFIX = "CLSS_ONTOLOGY_DEV_"

DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"


def env_var_name(dotted: str) -> str:
    """Map a dotted secret name to its OS environment variable key.

    ``clss.ontology.dev.gateway_url`` -> ``CLSS_ONTOLOGY_DEV_GATEWAY_URL``.
    """
    return dotted.replace(".", "_").replace("-", "_").upper()


@dataclass(frozen=True)
class OntologySettings:
    """Resolved configuration. Every field is optional; absence -> graceful
    degradation. No secret value is ever defaulted to a literal here — only
    ``None``.
    """

    env: str = "dev"
    service_name: str = "ontology"

    # The only egress. Every cross-service call (event store, the
    # document-understanding provider, the pgvector index) passes the gateway.
    gateway_url: str | None = None
    # Where emitted ontology events are POSTed (through the gateway).
    event_sink_url: str | None = None
    # The operational store for ontology rows. Unset -> in-memory snapshot.
    database_url: str | None = None
    # The pgvector-backed semantic index. Unset -> in-memory vector fallback.
    pgvector_url: str | None = None
    # Document-understanding provider for curriculum extraction. Unset -> draft.
    doc_understanding_key: str | None = None
    # Embeddings lanes, kept separate (TRACK SEPARATION). Unset -> hashing
    # fallback embedder (deterministic, offline).
    embeddings_track1_key: str | None = None  # external
    embeddings_track2_key: str | None = None  # proprietary/edge

    @property
    def has_gateway(self) -> bool:
        return bool(self.gateway_url)

    @property
    def has_event_sink(self) -> bool:
        """True only when BOTH the gateway and the sink are configured — every
        cross-service write passes the gateway, so a sink without a gateway is
        still degraded (we never write directly)."""
        return bool(self.gateway_url and self.event_sink_url)

    @property
    def has_doc_understanding(self) -> bool:
        """A live extraction provider needs the gateway AND a provider key."""
        return bool(self.gateway_url and self.doc_understanding_key)

    @property
    def has_pgvector(self) -> bool:
        """A live semantic index needs the gateway AND a pgvector URL."""
        return bool(self.gateway_url and self.pgvector_url)

    @property
    def has_embeddings(self) -> bool:
        """A live embedder needs the gateway AND at least one model lane key.
        The two lanes are kept distinct; this only asks whether ANY lane is
        usable, never merges their keys."""
        return bool(self.gateway_url and (self.embeddings_track1_key or self.embeddings_track2_key))

    def degraded_reasons(self) -> list[str]:
        """Dotted NAMES (NEVER values) of env vars whose absence keeps the
        module in degraded (deterministic, in-memory) mode."""
        missing: list[str] = []
        if not self.gateway_url:
            missing.append(ENV_GATEWAY_URL)
        if not self.event_sink_url:
            missing.append(ENV_EVENT_SINK_URL)
        if not self.database_url:
            missing.append(ENV_DATABASE_URL)
        if not self.pgvector_url:
            missing.append(ENV_PGVECTOR_URL)
        if not self.doc_understanding_key:
            missing.append(ENV_DOC_UNDERSTANDING_KEY)
        if not (self.embeddings_track1_key or self.embeddings_track2_key):
            missing.append(ENV_EMBEDDINGS_TRACK1_KEY)
        return missing


def _read_env(dotted: str) -> str | None:
    value = os.environ.get(env_var_name(dotted))
    if value is None:
        return None
    value = value.strip()
    return value or None


_cached: OntologySettings | None = None


def get_settings(*, refresh: bool = False) -> OntologySettings:
    """Resolve settings from the environment (by NAME) once, then cache.

    Reads only environment variables — no file, no network, no secret literal.
    Pass ``refresh=True`` to re-read (e.g. after the environment changes in a
    test).
    """
    global _cached
    if _cached is not None and not refresh:
        return _cached
    _cached = OntologySettings(
        env=os.environ.get(_ENV_PREFIX + "ENV", "dev"),
        gateway_url=_read_env(ENV_GATEWAY_URL),
        event_sink_url=_read_env(ENV_EVENT_SINK_URL),
        database_url=_read_env(ENV_DATABASE_URL),
        pgvector_url=_read_env(ENV_PGVECTOR_URL),
        doc_understanding_key=_read_env(ENV_DOC_UNDERSTANDING_KEY),
        embeddings_track1_key=_read_env(ENV_EMBEDDINGS_TRACK1_KEY),
        embeddings_track2_key=_read_env(ENV_EMBEDDINGS_TRACK2_KEY),
    )
    return _cached
