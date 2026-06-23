"""The content metadata repository (B3).

The library's index over supporting material — keyed to ontology topics — with:

  - VERSIONING: every change is a new immutable ``ContentVersion``; the record
    keeps the ordered history and a pointer to the live version. History is
    never rewritten (mirrors the append-only spirit of the event store).
  - APPROVAL STATE: a record moves DRAFT -> IN_REVIEW -> APPROVED (or REJECTED /
    RETIRED). Only an APPROVED, served-verified version is publishable to
    learners. The permission ladder lives in ``verification_surface``; this
    module records the state transitions that surface drives.
  - LICENCE METADATA: provenance, holder, licence code and attribution travel
    with every record so nothing is served without clear rights.

Plus a pgvector SEMANTIC-SEARCH interface. The production path is a pgvector
query (behind ``PgVectorSearchIndex``, which needs a DB handle and an embedder);
with neither configured it DEGRADES to ``InMemorySemanticSearchIndex`` — a
deterministic cosine match over locally-held vectors, so search works offline.

Behavioural data is not stored here: content metadata references ontology nodes
by opaque id and never carries learner PII (INVARIANT — behavioural data carries
only the opaque canonical_uuid; content metadata carries no learner identity at
all).

No secret values appear here. The pgvector DSN env var is named, never read for
a value at import time.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Protocol, Sequence


# ---------------------------------------------------------------------------
# Env var NAMES (INVARIANT 4 — names only, never values, never hardcoded keys)
# ---------------------------------------------------------------------------

# The Postgres/pgvector connection string for the content library DB. Read by
# NAME at wiring time; absent => the repository runs in-memory.
PGVECTOR_DSN_ENV = "clss.content.dev.pgvector_dsn"
# The embedding capability key, when an external embedder is wired for search.
EMBEDDING_KEY_ENV = "clss.content.dev.embedding_provider_key"


def env_var_name(dotted: str) -> str:
    """Map a dotted secret name to its OS environment variable key.

    ``clss.content.dev.pgvector_dsn`` -> ``CLSS_CONTENT_DEV_PGVECTOR_DSN``.
    """
    return dotted.replace(".", "_").replace("-", "_").upper()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ContentKind(str, Enum):
    """The kind of supporting material a record describes."""

    EXPLANATION = "explanation"
    WORKED_EXAMPLE = "worked_example"
    PRACTICE_ITEM = "practice_item"
    DIAGRAM = "diagram"
    READING = "reading"
    VIDEO = "video"
    DOCUMENT = "document"  # an ingested/uploaded artefact


class ApprovalState(str, Enum):
    """The lifecycle state of a content record.

    Only ``APPROVED`` content is served to learners, and a record only reaches
    ``APPROVED`` through the human verification surface (INVARIANT 8 — the
    permission ladder; publish is an explicit human act).
    """

    DRAFT = "draft"            # created, not yet submitted for review
    IN_REVIEW = "in_review"    # in the confidence-banded review queue
    APPROVED = "approved"      # a human approved a verified version; publishable
    REJECTED = "rejected"      # a human rejected it; not publishable
    RETIRED = "retired"        # superseded / withdrawn from service


_ALLOWED_TRANSITIONS: dict[ApprovalState, frozenset[ApprovalState]] = {
    ApprovalState.DRAFT: frozenset({ApprovalState.IN_REVIEW, ApprovalState.RETIRED}),
    ApprovalState.IN_REVIEW: frozenset(
        {ApprovalState.APPROVED, ApprovalState.REJECTED, ApprovalState.DRAFT}
    ),
    ApprovalState.APPROVED: frozenset({ApprovalState.RETIRED, ApprovalState.IN_REVIEW}),
    ApprovalState.REJECTED: frozenset({ApprovalState.DRAFT, ApprovalState.RETIRED}),
    ApprovalState.RETIRED: frozenset(),
}


class ApprovalTransitionError(ValueError):
    """Raised on an illegal approval-state transition."""


# ---------------------------------------------------------------------------
# Licence metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LicenceMetadata:
    """Provenance and rights for a piece of content.

    Nothing is served without clear rights. ``licence_code`` is a stable handle
    (e.g. ``"cc-by-4.0"``, ``"all-rights-reserved"``, ``"platform-generated"``),
    never a baked-in assumption about ownership.
    """

    licence_code: str
    holder: str
    source: str  # where it came from: "generated", "uploaded", an attribution URL/name
    attribution_required: bool = False
    attribution_text: str | None = None
    # True when the content was machine-generated (vs human-authored/uploaded).
    machine_generated: bool = False

    @staticmethod
    def for_generated(holder: str = "platform") -> "LicenceMetadata":
        return LicenceMetadata(
            licence_code="platform-generated",
            holder=holder,
            source="generated",
            machine_generated=True,
        )


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContentVersion:
    """One immutable version of a content record's body.

    A new version is appended on every change; existing versions are never
    mutated. ``verified_served`` records whether THIS version's body passed the
    ai-fabric confidence gate at the time it was added — a version that never
    passed verification can never be the live, learner-served version.
    """

    version_id: str
    number: int                      # 1-based, monotonically increasing
    body: dict[str, object]          # the material payload (kind-specific shape)
    created_at: datetime
    author: str                      # "system:generate", "user:<role-label>", "ingest"
    verified_served: bool            # did this body pass the confidence gate?
    verification_summary: str | None = None
    # The ai-fabric request id that produced/verified this version, when any.
    source_request_id: str | None = None


# ---------------------------------------------------------------------------
# The content record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContentRecord:
    """A content record: metadata + version history, keyed to an ontology topic.

    Immutable value object — repository operations return a NEW record rather
    than mutating in place, so callers can never observe a half-applied change.
    """

    content_id: str
    topic_id: str                    # opaque ontology topic id (no PII)
    kind: ContentKind
    title: str
    licence: LicenceMetadata
    approval_state: ApprovalState
    versions: tuple[ContentVersion, ...]
    live_version_id: str | None      # the version currently served (must be verified+approved)
    created_at: datetime
    updated_at: datetime
    # Optional finer ontology references (outcome/competency ids) for routing.
    outcome_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    # -- derived views -----------------------------------------------------

    @property
    def latest_version(self) -> ContentVersion | None:
        return self.versions[-1] if self.versions else None

    @property
    def live_version(self) -> ContentVersion | None:
        if self.live_version_id is None:
            return None
        for v in self.versions:
            if v.version_id == self.live_version_id:
                return v
        return None

    @property
    def is_servable(self) -> bool:
        """True only when an APPROVED record has a live, verified version.

        This is the single gate the rest of the platform reads before showing
        content to a learner.
        """
        live = self.live_version
        return (
            self.approval_state is ApprovalState.APPROVED
            and live is not None
            and live.verified_served
        )


# ---------------------------------------------------------------------------
# Semantic search interface
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SemanticSearchHit:
    """A semantic-search result: a content id and its similarity score [0,1]."""

    content_id: str
    score: float
    topic_id: str


class SemanticSearchIndex(Protocol):
    """A pgvector-shaped semantic-search interface.

    Production is a pgvector ``<=>`` cosine-distance query. With no DB / embedder
    the in-memory implementation provides the same surface deterministically.
    """

    @property
    def available(self) -> bool:
        ...

    def upsert(self, content_id: str, topic_id: str, vector: Sequence[float]) -> None:
        ...

    def remove(self, content_id: str) -> None:
        ...

    def query(self, vector: Sequence[float], *, top_k: int = 10, topic_id: str | None = None) -> list[SemanticSearchHit]:
        ...


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    # Map cosine similarity from [-1,1] to [0,1] for a stable score.
    return max(0.0, min(1.0, (dot / (na * nb) + 1.0) / 2.0))


@dataclass
class InMemorySemanticSearchIndex:
    """Deterministic in-memory cosine match — the graceful-degradation path.

    Same surface as the pgvector index. Holds vectors in a dict and ranks by
    cosine similarity. Stable ordering (score desc, then content_id) so results
    are reproducible for tests and offline use.
    """

    _vectors: dict[str, tuple[str, tuple[float, ...]]] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return True

    def upsert(self, content_id: str, topic_id: str, vector: Sequence[float]) -> None:
        self._vectors[content_id] = (topic_id, tuple(float(x) for x in vector))

    def remove(self, content_id: str) -> None:
        self._vectors.pop(content_id, None)

    def query(self, vector: Sequence[float], *, top_k: int = 10, topic_id: str | None = None) -> list[SemanticSearchHit]:
        query_vec = tuple(float(x) for x in vector)
        hits: list[SemanticSearchHit] = []
        for content_id, (t_id, vec) in self._vectors.items():
            if topic_id is not None and t_id != topic_id:
                continue
            hits.append(SemanticSearchHit(content_id=content_id, score=_cosine(query_vec, vec), topic_id=t_id))
        hits.sort(key=lambda h: (-h.score, h.content_id))
        return hits[: max(0, top_k)]


@dataclass
class PgVectorSearchIndex:
    """The pgvector-backed index (production path).

    Wired with a connection handle (a DB-API-ish ``connection`` object) and an
    embedder elsewhere; this class names the env var for the DSN and reports
    unavailable until a connection is supplied, so importing it never touches a
    network or a secret value.
    """

    connection: object | None = None
    dsn_env: str = PGVECTOR_DSN_ENV
    table: str = "content_embedding"

    @property
    def available(self) -> bool:
        return self.connection is not None

    def _require(self) -> object:
        if self.connection is None:
            raise RuntimeError(
                "pgvector index unavailable: no connection wired. Provide a handle "
                f"built from env var '{env_var_name(self.dsn_env)}' (secret '{self.dsn_env}'). "
                "Degrade to InMemorySemanticSearchIndex when the DB is absent."
            )
        return self.connection

    def upsert(self, content_id: str, topic_id: str, vector: Sequence[float]) -> None:
        conn = self._require()
        cur = conn.cursor()  # type: ignore[attr-defined]
        cur.execute(
            f"INSERT INTO {self.table} (content_id, topic_id, embedding) VALUES (%s, %s, %s) "
            "ON CONFLICT (content_id) DO UPDATE SET topic_id = EXCLUDED.topic_id, embedding = EXCLUDED.embedding",
            (content_id, topic_id, list(vector)),
        )

    def remove(self, content_id: str) -> None:
        conn = self._require()
        cur = conn.cursor()  # type: ignore[attr-defined]
        cur.execute(f"DELETE FROM {self.table} WHERE content_id = %s", (content_id,))

    def query(self, vector: Sequence[float], *, top_k: int = 10, topic_id: str | None = None) -> list[SemanticSearchHit]:
        conn = self._require()
        cur = conn.cursor()  # type: ignore[attr-defined]
        # Cosine distance operator (<=>); score = 1 - distance, clamped.
        where = "WHERE topic_id = %s " if topic_id is not None else ""
        params: list[object] = [list(vector)]
        if topic_id is not None:
            params.append(topic_id)
        params.append(top_k)
        cur.execute(
            f"SELECT content_id, topic_id, 1 - (embedding <=> %s) AS score "
            f"FROM {self.table} {where}ORDER BY score DESC LIMIT %s",
            tuple(params),
        )
        rows = cur.fetchall()  # type: ignore[attr-defined]
        return [
            SemanticSearchHit(content_id=r[0], topic_id=r[1], score=max(0.0, min(1.0, float(r[2]))))
            for r in rows
        ]


# ---------------------------------------------------------------------------
# The repository
# ---------------------------------------------------------------------------

class ContentRepository(Protocol):
    """The content metadata repository surface."""

    def create(
        self,
        *,
        topic_id: str,
        kind: ContentKind,
        title: str,
        body: dict[str, object],
        licence: LicenceMetadata,
        author: str,
        verified_served: bool,
        verification_summary: str | None = ...,
        source_request_id: str | None = ...,
        outcome_ids: Sequence[str] = ...,
        tags: Sequence[str] = ...,
    ) -> ContentRecord:
        ...

    def get(self, content_id: str) -> ContentRecord | None:
        ...

    def add_version(
        self,
        content_id: str,
        *,
        body: dict[str, object],
        author: str,
        verified_served: bool,
        verification_summary: str | None = ...,
        source_request_id: str | None = ...,
    ) -> ContentRecord:
        ...

    def transition(self, content_id: str, target: ApprovalState, *, version_id: str | None = ...) -> ContentRecord:
        ...

    def for_topic(self, topic_id: str, *, only_servable: bool = ...) -> list[ContentRecord]:
        ...


@dataclass
class InMemoryContentRepository:
    """An in-memory content repository — the graceful-degradation path.

    Holds immutable records in a dict; every mutation appends a new version or
    swaps a record for an updated copy. History is never rewritten. Pairs with a
    ``SemanticSearchIndex`` (in-memory by default); a Postgres-backed repository
    implementing the same surface is wired later behind ``PGVECTOR_DSN_ENV``.
    """

    index: SemanticSearchIndex = field(default_factory=InMemorySemanticSearchIndex)
    _records: dict[str, ContentRecord] = field(default_factory=dict)

    # -- create / read -----------------------------------------------------

    def create(
        self,
        *,
        topic_id: str,
        kind: ContentKind,
        title: str,
        body: dict[str, object],
        licence: LicenceMetadata,
        author: str,
        verified_served: bool,
        verification_summary: str | None = None,
        source_request_id: str | None = None,
        outcome_ids: Sequence[str] = (),
        tags: Sequence[str] = (),
    ) -> ContentRecord:
        now = _now()
        version = ContentVersion(
            version_id=_new_id(),
            number=1,
            body=dict(body),
            created_at=now,
            author=author,
            verified_served=verified_served,
            verification_summary=verification_summary,
            source_request_id=source_request_id,
        )
        record = ContentRecord(
            content_id=_new_id(),
            topic_id=topic_id,
            kind=kind,
            title=title,
            licence=licence,
            approval_state=ApprovalState.DRAFT,
            versions=(version,),
            live_version_id=None,  # never live until approved through the surface
            created_at=now,
            updated_at=now,
            outcome_ids=tuple(outcome_ids),
            tags=tuple(tags),
        )
        self._records[record.content_id] = record
        return record

    def get(self, content_id: str) -> ContentRecord | None:
        return self._records.get(content_id)

    def require(self, content_id: str) -> ContentRecord:
        rec = self._records.get(content_id)
        if rec is None:
            raise KeyError(f"unknown content record: {content_id!r}")
        return rec

    def all(self) -> tuple[ContentRecord, ...]:
        return tuple(self._records.values())

    # -- versioning --------------------------------------------------------

    def add_version(
        self,
        content_id: str,
        *,
        body: dict[str, object],
        author: str,
        verified_served: bool,
        verification_summary: str | None = None,
        source_request_id: str | None = None,
    ) -> ContentRecord:
        rec = self.require(content_id)
        next_number = (rec.latest_version.number + 1) if rec.latest_version else 1
        version = ContentVersion(
            version_id=_new_id(),
            number=next_number,
            body=dict(body),
            created_at=_now(),
            author=author,
            verified_served=verified_served,
            verification_summary=verification_summary,
            source_request_id=source_request_id,
        )
        # A new version supersedes the live one: the record returns to review so
        # a human re-approves before the new body is served (permission ladder).
        updated = replace(
            rec,
            versions=rec.versions + (version,),
            approval_state=(
                ApprovalState.IN_REVIEW
                if rec.approval_state is ApprovalState.APPROVED
                else rec.approval_state
            ),
            live_version_id=None if rec.approval_state is ApprovalState.APPROVED else rec.live_version_id,
            updated_at=version.created_at,
        )
        self._records[content_id] = updated
        return updated

    # -- approval ----------------------------------------------------------

    def transition(self, content_id: str, target: ApprovalState, *, version_id: str | None = None) -> ContentRecord:
        rec = self.require(content_id)
        allowed = _ALLOWED_TRANSITIONS[rec.approval_state]
        if target not in allowed:
            raise ApprovalTransitionError(
                f"cannot move content {content_id!r} from {rec.approval_state.value} to {target.value}; "
                f"allowed: {sorted(s.value for s in allowed) or 'none (terminal)'}"
            )

        live_id = rec.live_version_id
        if target is ApprovalState.APPROVED:
            # Approving promotes a specific version to live. It MUST be verified —
            # an unverified body can never become the learner-served version.
            chosen = self._resolve_version(rec, version_id)
            if not chosen.verified_served:
                raise ApprovalTransitionError(
                    f"cannot approve version {chosen.version_id!r}: it did not pass the "
                    "confidence gate (verified_served is False). Nothing unverified is served."
                )
            live_id = chosen.version_id
        elif target in (ApprovalState.REJECTED, ApprovalState.RETIRED, ApprovalState.IN_REVIEW, ApprovalState.DRAFT):
            # Leaving the approved state withdraws the live pointer.
            if rec.approval_state is ApprovalState.APPROVED:
                live_id = None

        updated = replace(rec, approval_state=target, live_version_id=live_id, updated_at=_now())
        self._records[content_id] = updated
        return updated

    @staticmethod
    def _resolve_version(rec: ContentRecord, version_id: str | None) -> ContentVersion:
        if version_id is None:
            latest = rec.latest_version
            if latest is None:
                raise ApprovalTransitionError(f"content {rec.content_id!r} has no versions to approve.")
            return latest
        for v in rec.versions:
            if v.version_id == version_id:
                return v
        raise ApprovalTransitionError(f"version {version_id!r} not found on content {rec.content_id!r}.")

    # -- topic queries -----------------------------------------------------

    def for_topic(self, topic_id: str, *, only_servable: bool = False) -> list[ContentRecord]:
        out = [r for r in self._records.values() if r.topic_id == topic_id]
        if only_servable:
            out = [r for r in out if r.is_servable]
        out.sort(key=lambda r: (r.kind.value, r.created_at, r.content_id))
        return out

    # -- semantic search ---------------------------------------------------

    def index_vector(self, content_id: str, vector: Sequence[float]) -> None:
        """Attach an embedding to a record for semantic search."""
        rec = self.require(content_id)
        self.index.upsert(content_id, rec.topic_id, vector)

    def search(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 10,
        topic_id: str | None = None,
        only_servable: bool = True,
    ) -> list[SemanticSearchHit]:
        """Semantic search, defaulting to servable content only.

        ``only_servable`` keeps unverified / unapproved drafts out of learner
        results by construction.
        """
        hits = self.index.query(vector, top_k=top_k if not only_servable else top_k * 4, topic_id=topic_id)
        if only_servable:
            hits = [h for h in hits if (r := self._records.get(h.content_id)) is not None and r.is_servable]
        return hits[:top_k]
