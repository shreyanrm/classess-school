"""The REAL Gemini document-understanding path is invoked by NAME, degrades
without a key, maps extracted nodes onto ontology types, and surfaces proposed
prerequisite edges UNCONFIRMED. Fully OFFLINE — no live call: a key-absent path
needs no network, and the with-key path uses an httpx MockTransport so no
request ever leaves the process. No board lock-in."""

from __future__ import annotations

import json

import httpx

from app._ontology import PrerequisiteKind
from app.config import ENV_GEMINI_API_KEY, OntologySettings
from app.gemini import (
    GEMINI_API_BASE,
    GeminiDocumentUnderstanding,
    build_prompt,
    extract_text_from_response,
    parse_extraction,
)
from app.ingest import CurriculumIngester, GeminiUnderstandingAdapter, SourceDocument


# A realistic Gemini generateContent JSON body wrapping the model's text part.
def _gemini_response_body(model_json: dict) -> dict:
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(model_json)}]}}
        ]
    }


_MODEL_JSON = {
    "outline": [
        {
            "kind": "grade",
            "title": "Class 8",
            "confidence": 0.9,
            "children": [
                {
                    "kind": "subject",
                    "title": "Science",
                    "confidence": 0.88,
                    "children": [
                        {
                            "kind": "unit",
                            "title": "Force and Pressure",
                            "children": [
                                {
                                    "kind": "chapter",
                                    "title": "Force",
                                    "children": [
                                        {"kind": "topic", "title": "Contact and Non-contact Forces", "confidence": 0.8},
                                        {"kind": "topic", "title": "Pressure Exerted by Forces", "confidence": 0.8},
                                        {
                                            "kind": "topic",
                                            "title": "Friction",
                                            "confidence": 0.8,
                                            "children": [
                                                {"kind": "outcome", "title": "explain-friction",
                                                 "statement": "Explains friction as a force opposing relative motion."},
                                            ],
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ],
    "proposed_prerequisites": [
        {
            "from_title": "Contact and Non-contact Forces",
            "to_title": "Pressure Exerted by Forces",
            "kind": "soft",
            "rationale": "Understanding forces supports reasoning about pressure.",
            "confidence": 0.7,
        },
        # A hint whose titles do NOT resolve — must be dropped, never invented.
        {"from_title": "Nonexistent Topic", "to_title": "Friction", "kind": "hard", "confidence": 0.9},
    ],
}


def _settings_with_key() -> OntologySettings:
    return OntologySettings(gemini_api_key="test-key-value-never-asserted")


def _mock_transport_capturing(captured: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["params_key"] = request.url.params.get("key")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=_gemini_response_body(_MODEL_JSON))

    return httpx.MockTransport(handler)


# -- degradation (no key) ---------------------------------------------------


def test_gemini_degrades_cleanly_without_a_key():
    client = GeminiDocumentUnderstanding(settings=OntologySettings())  # no key.
    assert client.available is False
    result = client.extract("Some curriculum text", board_name="Any Board")
    assert result.available is False
    assert result.outline == []
    assert result.edge_hints == []
    # The reason NAMES the env var (by NAME) the live path reads — never a value.
    assert ENV_GEMINI_API_KEY in (result.detail or "")


def test_default_understanding_uses_gemini_when_key_present():
    from app.ingest import GeminiUnderstandingAdapter, default_document_understanding

    provider = default_document_understanding(_settings_with_key())
    assert isinstance(provider, GeminiUnderstandingAdapter)


def test_no_board_lock_in_prompt_uses_source_board_label():
    prompt = build_prompt("doc text", board_name="Some Regional Board")
    assert "Some Regional Board" in prompt
    # No baked-in board name leaks into the prompt construction.
    assert "CBSE" not in prompt and "ICSE" not in prompt


# -- invoked by NAME, offline via MockTransport -----------------------------


def test_gemini_invoked_by_name_offline_and_reads_key_at_egress():
    captured: dict = {}
    client = GeminiDocumentUnderstanding(
        settings=_settings_with_key(),
        transport=_mock_transport_capturing(captured),
    )
    assert client.available is True  # availability is by NAME (key present).
    result = client.extract("Force and Pressure curriculum...", board_name="Example Board")

    # The call hit the Gemini REST surface; the key was read at egress by NAME
    # and placed only on the request (never returned in the result object).
    assert captured["url"].startswith(GEMINI_API_BASE)
    assert captured["params_key"] == "test-key-value-never-asserted"
    assert "test-key-value-never-asserted" not in json.dumps(
        {"detail": result.detail, "provider": result.provider}
    )
    assert result.available is True
    assert result.provider == "gemini-document-understanding"


def test_extracted_nodes_map_to_ontology_types_via_ingester():
    client = GeminiDocumentUnderstanding(
        settings=_settings_with_key(), transport=_mock_transport_capturing({})
    )
    ingester = CurriculumIngester(understanding=GeminiUnderstandingAdapter(client), settings=_settings_with_key())
    doc = SourceDocument(
        source_ref="gemini-doc-1",
        board_code="example-board",
        board_name="Example Board",
        document_text="A force-and-pressure chapter to extract.",
    )
    result = ingester.ingest(doc)

    # Each extracted level mapped onto its typed ontology table.
    assert {g.level for g in result.snapshot.grades} == {8}
    assert any(s.name == "Science" for s in result.snapshot.subjects)
    assert any(u.name == "Force and Pressure" for u in result.snapshot.units)
    assert any(c.name == "Force" for c in result.snapshot.chapters)
    topic_names = {t.name for t in result.snapshot.topics}
    assert "Friction" in topic_names
    # The outcome carries its can-do statement.
    assert any("friction" in o.statement.lower() for o in result.snapshot.outcomes)
    assert result.available is True
    assert result.provider == "gemini-document-understanding"


def test_proposed_edges_start_unconfirmed_and_unresolved_hints_dropped():
    client = GeminiDocumentUnderstanding(
        settings=_settings_with_key(), transport=_mock_transport_capturing({})
    )
    ingester = CurriculumIngester(understanding=GeminiUnderstandingAdapter(client), settings=_settings_with_key())
    doc = SourceDocument(
        source_ref="gemini-doc-2",
        board_code="example-board",
        board_name="Example Board",
        document_text="A force-and-pressure chapter to extract.",
    )
    result = ingester.ingest(doc)

    # Exactly one of the two hints resolves to real topics; the other is dropped
    # (no invented topic to satisfy an edge).
    assert len(result.proposed_edges) == 1
    edge = result.proposed_edges[0]
    # LAW: a proposed edge is NEVER auto-trusted.
    assert edge.confirmed is False
    assert result.has_unconfirmed_edges is True
    # It connects two topics that actually exist in the snapshot.
    ids = result.snapshot.topic_ids()
    assert edge.from_topic_id in ids and edge.to_topic_id in ids


def test_proposed_edges_held_unconfirmed_by_the_steward():
    from app.steward import PrerequisiteSteward

    client = GeminiDocumentUnderstanding(
        settings=_settings_with_key(), transport=_mock_transport_capturing({})
    )
    ingester = CurriculumIngester(understanding=GeminiUnderstandingAdapter(client), settings=_settings_with_key())
    doc = SourceDocument(
        source_ref="gemini-doc-3",
        board_code="example-board",
        board_name="Example Board",
        document_text="text",
    )
    result = ingester.ingest(doc)

    steward = PrerequisiteSteward(result.snapshot)
    # The Gemini-proposed edge is in the pending (review) queue and NOT trusted.
    assert any(not p.confirmed for p in steward.pending())
    assert steward.trusted_edges() == []


# -- parsing is defensive (degrades, never fabricates) ----------------------


def test_parse_extraction_drops_unknown_kinds_and_bad_json():
    # Unknown node kind is dropped — never coins a kind the ontology lacks.
    outline, hints = parse_extraction(json.dumps({
        "outline": [{"kind": "module", "title": "X"}, {"kind": "topic", "title": "Y"}],
        "proposed_prerequisites": [],
    }))
    kinds = {n["kind"] for n in outline}
    assert kinds == {"topic"}
    # Garbage in -> empty out (no fabrication).
    assert parse_extraction("not json at all") == ([], [])
    assert parse_extraction("") == ([], [])


def test_extract_text_handles_blocked_or_empty_response():
    assert extract_text_from_response({}) == ""
    assert extract_text_from_response({"candidates": []}) == ""


def test_edge_hint_confidence_capped_below_certainty():
    _, hints = parse_extraction(json.dumps({
        "outline": [],
        "proposed_prerequisites": [
            {"from_title": "A", "to_title": "B", "kind": "hard", "confidence": 1.0},
        ],
    }))
    assert len(hints) == 1
    # A model proposal can never present itself as certain.
    assert hints[0].confidence < 1.0
    assert hints[0].kind is PrerequisiteKind.HARD


def test_empty_document_with_key_returns_unavailable_no_call():
    # A key is present but the document is empty: no fabrication, no call needed.
    captured: dict = {}
    client = GeminiDocumentUnderstanding(
        settings=_settings_with_key(), transport=_mock_transport_capturing(captured)
    )
    result = client.extract("   ", board_name="Example Board")
    assert result.available is False
    assert captured == {}  # transport never invoked.
