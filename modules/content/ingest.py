"""Upload / ingest interface (B3).

Takes an uploaded artefact (a scanned worksheet, a photographed textbook page, a
recorded lesson) and produces CONTENT METADATA: a draft record in the library
keyed to an ontology topic, with extracted text/structure attached. The actual
document understanding is an INTERFACE that degrades gracefully:

  - ``OcrProvider``        — image/PDF text extraction,
  - ``Transcriber``        — audio/video speech-to-text,
  - ``DocumentUnderstanding`` — layout/structure extraction (headings, items).

With no provider wired the ``Null*`` implementations report unavailable and the
ingest records the artefact as a DRAFT with NO extracted text — a clearly-marked
"pending extraction" state, never invented OCR output. The provider keys the
live path will read are NAMED here, never read for a value and never hardcoded.

Two laws bind this module:
  - INVARIANT 7 — extracted/understood content is UNVERIFIED. Ingest creates a
    DRAFT only; it never marks a body ``verified_served`` and never makes it
    live. Promotion goes through the verification surface (human approval).
  - PERMISSION LADDER — uploading is preparation; publishing to learners is a
    separate, explicit human act.

No learner PII is stored on a content record (INVARIANT — behavioural data
carries only the opaque canonical_uuid; content metadata carries none). The
uploader is recorded as a generic role label, not a real name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence

from .repository import (
    ApprovalState,
    ContentKind,
    ContentRecord,
    InMemoryContentRepository,
    LicenceMetadata,
)


# ---------------------------------------------------------------------------
# Env var NAMES for the document-understanding providers (names only)
# ---------------------------------------------------------------------------

OCR_PROVIDER_KEY_ENV = "clss.content.dev.ocr_provider_key"
TRANSCRIBE_PROVIDER_KEY_ENV = "clss.content.dev.transcription_provider_key"
DOC_UNDERSTANDING_KEY_ENV = "clss.content.dev.doc_understanding_key"


def env_var_name(dotted: str) -> str:
    return dotted.replace(".", "_").replace("-", "_").upper()


# ---------------------------------------------------------------------------
# Source / extraction shapes
# ---------------------------------------------------------------------------

class SourceMedia(str, Enum):
    """The kind of uploaded artefact."""

    IMAGE = "image"          # photo / scan -> OCR
    PDF = "pdf"              # document -> OCR + layout
    AUDIO = "audio"          # recording -> transcription
    VIDEO = "video"          # recording -> transcription
    TEXT = "text"            # already-text upload; no extraction needed


@dataclass(frozen=True)
class ExtractedText:
    """The result of an extraction step."""

    text: str
    confidence: float            # provider-reported extraction confidence [0,1]
    available: bool              # False when no provider ran (degraded path)
    provider: str                # provider label or "none"
    blocks: tuple[str, ...] = ()  # optional structural blocks (headings/items)
    detail: str | None = None


def _unavailable(provider_env: str, what: str) -> ExtractedText:
    return ExtractedText(
        text="",
        confidence=0.0,
        available=False,
        provider="none",
        detail=(
            f"no {what} provider configured; set env var '{env_var_name(provider_env)}' "
            f"(secret '{provider_env}'). Artefact recorded as pending extraction — "
            "no text fabricated."
        ),
    )


# ---------------------------------------------------------------------------
# Provider interfaces + Null (degrade-gracefully) implementations
# ---------------------------------------------------------------------------

class OcrProvider(Protocol):
    """Optical character recognition over image/PDF bytes."""

    @property
    def available(self) -> bool:
        ...

    def extract(self, *, data: bytes, media: SourceMedia, hint: str | None = None) -> ExtractedText:
        ...


class Transcriber(Protocol):
    """Speech-to-text over audio/video bytes."""

    @property
    def available(self) -> bool:
        ...

    def transcribe(self, *, data: bytes, media: SourceMedia, language: str | None = None) -> ExtractedText:
        ...


class DocumentUnderstanding(Protocol):
    """Layout/structure extraction over an artefact (headings, item boundaries)."""

    @property
    def available(self) -> bool:
        ...

    def understand(self, *, data: bytes, media: SourceMedia) -> ExtractedText:
        ...


@dataclass(frozen=True)
class NullOcrProvider:
    """No-provider OCR — reports unavailable, never invents text."""

    @property
    def available(self) -> bool:
        return False

    def extract(self, *, data: bytes, media: SourceMedia, hint: str | None = None) -> ExtractedText:
        return _unavailable(OCR_PROVIDER_KEY_ENV, "OCR")


@dataclass(frozen=True)
class NullTranscriber:
    """No-provider transcription — reports unavailable, never invents text."""

    @property
    def available(self) -> bool:
        return False

    def transcribe(self, *, data: bytes, media: SourceMedia, language: str | None = None) -> ExtractedText:
        return _unavailable(TRANSCRIBE_PROVIDER_KEY_ENV, "transcription")


@dataclass(frozen=True)
class NullDocumentUnderstanding:
    """No-provider document understanding — reports unavailable."""

    @property
    def available(self) -> bool:
        return False

    def understand(self, *, data: bytes, media: SourceMedia) -> ExtractedText:
        return _unavailable(DOC_UNDERSTANDING_KEY_ENV, "document-understanding")


# ---------------------------------------------------------------------------
# Ingest request / outcome
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IngestRequest:
    """An upload to ingest, keyed to an ontology topic.

    ``data`` is the raw artefact bytes; ``inline_text`` carries already-text
    uploads (``SourceMedia.TEXT``) that need no extraction. ``uploaded_by`` is a
    GENERIC role label (e.g. "user:teacher"), never a real personal name.
    """

    topic_id: str
    media: SourceMedia
    title: str
    licence: LicenceMetadata
    uploaded_by: str = "user:unknown-role"
    data: bytes = b""
    inline_text: str | None = None
    language: str | None = None
    outcome_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class IngestOutcome:
    """The result of an ingest.

    A record is ALWAYS created (the upload is preserved), but it is a DRAFT and
    its body is never marked verified by ingest. ``extraction`` reports whether
    text was extracted or the artefact is pending extraction.
    """

    record: ContentRecord
    extraction: ExtractedText
    extracted: bool   # True when usable text was produced
    detail: str | None = None


# ---------------------------------------------------------------------------
# The ingest interface
# ---------------------------------------------------------------------------

class IngestInterface:
    """Ingests uploads into the content library as DRAFT records.

    Routes by media to the appropriate document-understanding provider; with no
    provider it records the artefact as pending extraction. Never marks content
    verified or live — promotion is a human act via the verification surface.
    """

    def __init__(
        self,
        repository: InMemoryContentRepository,
        *,
        ocr: OcrProvider | None = None,
        transcriber: Transcriber | None = None,
        doc_understanding: DocumentUnderstanding | None = None,
    ) -> None:
        self.repository = repository
        self.ocr = ocr if ocr is not None else NullOcrProvider()
        self.transcriber = transcriber if transcriber is not None else NullTranscriber()
        self.doc_understanding = (
            doc_understanding if doc_understanding is not None else NullDocumentUnderstanding()
        )

    def _extract(self, request: IngestRequest) -> ExtractedText:
        if request.media is SourceMedia.TEXT:
            text = request.inline_text or ""
            return ExtractedText(
                text=text,
                confidence=1.0 if text else 0.0,
                available=bool(text),
                provider="inline-text",
                detail=None if text else "empty text upload.",
            )
        if request.media in (SourceMedia.IMAGE, SourceMedia.PDF):
            return self.ocr.extract(data=request.data, media=request.media, hint=request.title)
        if request.media in (SourceMedia.AUDIO, SourceMedia.VIDEO):
            return self.transcriber.transcribe(
                data=request.data, media=request.media, language=request.language
            )
        return _unavailable(DOC_UNDERSTANDING_KEY_ENV, "document-understanding")

    @staticmethod
    def _content_kind(media: SourceMedia) -> ContentKind:
        if media is SourceMedia.VIDEO:
            return ContentKind.VIDEO
        if media is SourceMedia.TEXT:
            return ContentKind.READING
        return ContentKind.DOCUMENT

    def ingest(self, request: IngestRequest) -> IngestOutcome:
        """Ingest an upload, returning the created DRAFT record + extraction."""
        extraction = self._extract(request)
        extracted = bool(extraction.available and extraction.text.strip())

        body: dict[str, object] = {
            "media": request.media.value,
            "extracted_text": extraction.text,
            "extraction_provider": extraction.provider,
            "extraction_confidence": extraction.confidence,
            "extraction_available": extraction.available,
            "blocks": list(extraction.blocks),
            "pending_extraction": not extracted,
        }
        if extraction.detail:
            body["extraction_detail"] = extraction.detail

        record = self.repository.create(
            topic_id=request.topic_id,
            kind=self._content_kind(request.media),
            title=request.title,
            body=body,
            licence=request.licence,
            author=request.uploaded_by,
            # Ingest NEVER verifies. Extraction is unverified content; it must go
            # through the human verification surface before it can be served.
            verified_served=False,
            verification_summary=(
                "ingested; unverified. Pending human verification before service."
            ),
            outcome_ids=request.outcome_ids,
            tags=request.tags,
        )
        assert record.approval_state is ApprovalState.DRAFT

        detail = (
            None
            if extracted
            else (extraction.detail or "no text extracted; artefact stored pending extraction.")
        )
        return IngestOutcome(
            record=record, extraction=extraction, extracted=extracted, detail=detail
        )
