"""Ingest: produces unverified DRAFT metadata; degrades without a provider."""

import content
from content.ingest import (
    ExtractedText,
    IngestInterface,
    IngestRequest,
    SourceMedia,
    OCR_PROVIDER_KEY_ENV,
    env_var_name,
)
from content.repository import (
    ApprovalState,
    ContentKind,
    InMemoryContentRepository,
    LicenceMetadata,
)


def _lic() -> LicenceMetadata:
    return LicenceMetadata(
        licence_code="all-rights-reserved", holder="institution", source="uploaded"
    )


def test_text_upload_extracts_inline_and_files_draft():
    repo = InMemoryContentRepository()
    ingest = IngestInterface(repo)
    out = ingest.ingest(IngestRequest(
        topic_id="topic-1", media=SourceMedia.TEXT, title="Notes",
        licence=_lic(), inline_text="Euclid's division lemma states ...",
        uploaded_by="user:teacher",
    ))
    assert out.extracted is True
    assert out.record.approval_state is ApprovalState.DRAFT
    assert out.record.kind is ContentKind.READING
    # Ingest never verifies.
    assert out.record.latest_version.verified_served is False
    assert out.record.is_servable is False


def test_image_upload_without_ocr_provider_is_pending_extraction():
    repo = InMemoryContentRepository()
    ingest = IngestInterface(repo)  # Null OCR by default
    out = ingest.ingest(IngestRequest(
        topic_id="topic-1", media=SourceMedia.IMAGE, title="Scanned worksheet",
        licence=_lic(), data=b"\x89PNG...", uploaded_by="user:teacher",
    ))
    assert out.extracted is False
    assert out.record.latest_version.body["pending_extraction"] is True
    assert out.record.latest_version.body["extracted_text"] == ""  # never fabricated
    assert env_var_name(OCR_PROVIDER_KEY_ENV) in (out.detail or "")
    assert out.record.approval_state is ApprovalState.DRAFT


class _FakeOcr:
    @property
    def available(self):
        return True

    def extract(self, *, data, media, hint=None):
        return ExtractedText(
            text="x squared plus one", confidence=0.92, available=True,
            provider="fake-ocr", blocks=("heading", "item-1"),
        )


def test_image_upload_with_ocr_provider_extracts_but_stays_unverified():
    repo = InMemoryContentRepository()
    ingest = IngestInterface(repo, ocr=_FakeOcr())
    out = ingest.ingest(IngestRequest(
        topic_id="topic-1", media=SourceMedia.PDF, title="Worksheet",
        licence=_lic(), data=b"%PDF-1.4",
    ))
    assert out.extracted is True
    assert out.record.latest_version.body["extracted_text"] == "x squared plus one"
    assert out.record.latest_version.body["extraction_provider"] == "fake-ocr"
    # Extracted, but still UNVERIFIED — must go through the verification surface.
    assert out.record.latest_version.verified_served is False
    assert out.record.is_servable is False


def test_audio_upload_without_transcriber_is_pending():
    repo = InMemoryContentRepository()
    ingest = IngestInterface(repo)
    out = ingest.ingest(IngestRequest(
        topic_id="topic-1", media=SourceMedia.AUDIO, title="Lesson recording",
        licence=_lic(), data=b"RIFF....",
    ))
    assert out.extracted is False
    assert out.record.kind is ContentKind.DOCUMENT
    assert out.record.latest_version.body["pending_extraction"] is True
