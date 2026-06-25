"""Content & resources module (B3).

The content library, generated supporting material, and the human verification
surface. Three laws shape every line here:

  - GENERATE-AND-VERIFY (INVARIANT 7): nothing generated is served unverified.
    ``generate.py`` wires to the ai-fabric orchestrator's confidence gate; only
    content whose verification block reports ``served`` is returned.
  - THE PERMISSION LADDER (INVARIANT 8): generated material is PREPARED, never
    auto-published. Approval (publish to the live library) is an explicit human
    act, surfaced through ``verification_surface.py`` (the confidence-banded
    review queue). Agents hold no credentials.
  - DEGRADE GRACEFULLY: no live LLM key, no Supabase, no OCR provider yet. Every
    interface has a deterministic in-memory path and names the env var it will
    read; absence yields a clearly-marked unavailable result, never a fabrication.

This package is import-safe and depends only on the standard library plus the
ai-fabric spine (which is itself standard-library-only for the deterministic
paths). It does not modify the spine.
"""

from __future__ import annotations

from .repository import (
    ApprovalState,
    ContentKind,
    ContentRecord,
    ContentRepository,
    ContentVersion,
    InMemoryContentRepository,
    LicenceMetadata,
    SemanticSearchHit,
    SemanticSearchIndex,
)
from .generate import (
    ContentGenerator,
    GeneratedMaterial,
    GenerationOutcome,
    MaterialKind,
    MaterialRequest,
    WorksheetItem,
    WorksheetOutcome,
)
from .hyperlocalize import (
    Hyperlocalizer,
    HyperlocalizationOutcome,
    LocaleContext,
    LocalizationProvider,
)
from .gemini_localization import (
    GeminiLocalizationProvider,
    make_localization_provider,
    GEMINI_KEY_ENV_VAR,
    GEMINI_KEY_SECRET_NAME,
)
from .ingest import (
    DocumentUnderstanding,
    IngestInterface,
    IngestOutcome,
    IngestRequest,
    NullDocumentUnderstanding,
    OcrProvider,
    NullOcrProvider,
    Transcriber,
    NullTranscriber,
)
from .verification_surface import (
    ConfidenceBand,
    ReviewDecision,
    ReviewItem,
    ReviewQueue,
    ReviewVerdict,
    band_for_confidence,
)

__all__ = [
    # repository
    "ApprovalState",
    "ContentKind",
    "ContentRecord",
    "ContentRepository",
    "ContentVersion",
    "InMemoryContentRepository",
    "LicenceMetadata",
    "SemanticSearchHit",
    "SemanticSearchIndex",
    # generate
    "ContentGenerator",
    "GeneratedMaterial",
    "GenerationOutcome",
    "MaterialKind",
    "MaterialRequest",
    "WorksheetItem",
    "WorksheetOutcome",
    # hyperlocalization
    "Hyperlocalizer",
    "HyperlocalizationOutcome",
    "LocaleContext",
    "LocalizationProvider",
    "GeminiLocalizationProvider",
    "make_localization_provider",
    "GEMINI_KEY_ENV_VAR",
    "GEMINI_KEY_SECRET_NAME",
    # ingest
    "DocumentUnderstanding",
    "IngestInterface",
    "IngestOutcome",
    "IngestRequest",
    "NullDocumentUnderstanding",
    "OcrProvider",
    "NullOcrProvider",
    "Transcriber",
    "NullTranscriber",
    # verification surface
    "ConfidenceBand",
    "ReviewDecision",
    "ReviewItem",
    "ReviewQueue",
    "ReviewVerdict",
    "band_for_confidence",
]
