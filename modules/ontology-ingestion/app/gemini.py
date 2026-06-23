"""Real Gemini-backed curriculum document understanding (A2, Ring 1).

This is the LIVE document-understanding path — not an interface stub. Given a
curriculum document (plain text, markdown, or extracted PDF text), it calls the
Gemini ``generateContent`` REST endpoint over HTTPS via :mod:`httpx`, asking the
model to return a STRICT JSON curriculum tree
(board → grade → subject → unit → chapter → topic → outcome) plus PROPOSED
prerequisite edges between topics. The structured JSON is then mapped onto the
board-agnostic :class:`~app.ingest.OutlineNode` shape and a set of
:class:`ProposedEdgeHint` records the steward holds UNCONFIRMED.

LAWS honoured here:
  - SECRETS ARE ENV-ONLY, READ BY NAME. The provider key is read for a VALUE
    only inside :meth:`GeminiDocumentUnderstanding._raw_key`, from the env var
    NAMED by ``ENV_GEMINI_API_KEY`` (``CLSS_AIFABRIC_DEV_GEMINI_API_KEY``). It is
    never hardcoded, never logged, never placed in a returned object, and never
    sent anywhere but the provider over HTTPS.
  - DEGRADE CLEANLY. With no key (or httpx absent), every entrypoint returns a
    clearly-marked ``available = False`` result with an empty outline — it NEVER
    fabricates structure. Ingestion then falls back to the deterministic parser.
  - GENERATE-AND-VERIFY. Extracted nodes carry a confidence and remain DRAFTS;
    proposed prerequisite edges start UNCONFIRMED and are only trusted after a
    human steward confirms them. The model never self-confirms an edge.
  - BOARD-AGNOSTIC. The board label is read from the source, never baked in. The
    prompt asks the model to honour whatever board the document describes.

Import-safe: importing this module performs no I/O, reads no secret value, makes
no live call, and does not require httpx to be importable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .config import ENV_GEMINI_API_KEY, OntologySettings, get_settings
from ._ontology import NodeKind, PrerequisiteKind


# The Gemini REST surface. A label/URL only — never a key. The key travels as a
# query parameter (``?key=``) the provider expects; it is read by NAME at egress.
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"

# Network budget for the single extraction call. Kept modest; the call is made
# only when a key is present and tests never reach it (offline, no key).
DEFAULT_TIMEOUT_SECONDS = 30.0

# The provider label recorded on results from this path.
PROVIDER_LABEL = "gemini-document-understanding"

# Kinds the model is allowed to emit, mapped to ontology NodeKinds. The model
# returns a string ``kind``; anything outside this map is dropped (we never coin
# a node kind the ontology does not define).
_KIND_BY_NAME: dict[str, NodeKind] = {
    "grade": NodeKind.GRADE,
    "subject": NodeKind.SUBJECT,
    "unit": NodeKind.UNIT,
    "chapter": NodeKind.CHAPTER,
    "topic": NodeKind.TOPIC,
    "outcome": NodeKind.OUTCOME,
    "competency": NodeKind.COMPETENCY,
}


@dataclass(frozen=True)
class ProposedEdgeHint:
    """A model-proposed prerequisite hint between two topics, by TITLE.

    The model knows topics by their text, not by our opaque ids, so a hint names
    the prerequisite and dependent topic TITLES plus a rationale and a confidence.
    Ingestion resolves the titles to topic ids after the outline is mapped, and
    the steward holds the resulting edge UNCONFIRMED until a human confirms it.
    """

    from_title: str
    to_title: str
    kind: PrerequisiteKind
    rationale: str
    confidence: float


@dataclass
class GeminiExtraction:
    """The parsed result of a Gemini extraction call (provider-shaped, pre-map).

    ``outline`` is a list of nested ``dict`` nodes (each ``{kind,title,...}``);
    the ingest layer turns these into :class:`OutlineNode` trees. ``edge_hints``
    are proposed prerequisites the steward will hold unconfirmed.
    """

    outline: list[dict[str, Any]] = field(default_factory=list)
    edge_hints: list[ProposedEdgeHint] = field(default_factory=list)
    available: bool = False
    provider: str = "none"
    detail: str | None = None


# ---------------------------------------------------------------------------
# Prompt construction (board-agnostic, JSON-strict)
# ---------------------------------------------------------------------------


_SYSTEM_INSTRUCTION = (
    "You are a curriculum-structuring assistant for a board-agnostic learning "
    "ontology. You read a curriculum document and return STRICT JSON only — no "
    "prose, no markdown fences. You never invent a board: use exactly the board "
    "the document describes. You never assert a prerequisite as fact; you only "
    "PROPOSE prerequisite edges for human review."
)


def build_prompt(document_text: str, *, board_name: str) -> str:
    """Build the extraction instruction. Board name is a LABEL from the source.

    The model is asked for a tree of nodes whose ``kind`` is one of the ontology
    levels, plus a list of proposed prerequisite edges referencing topic titles.
    """
    schema_hint = {
        "outline": [
            {
                "kind": "grade|subject|unit|chapter|topic|outcome|competency",
                "title": "string",
                "statement": "string (outcomes/competencies only — the can-do text)",
                "confidence": "number in [0,1] — your confidence in this node",
                "children": ["...recursively the same shape..."],
            }
        ],
        "proposed_prerequisites": [
            {
                "from_title": "prerequisite topic title",
                "to_title": "dependent topic title",
                "kind": "hard|soft",
                "rationale": "why one likely precedes the other",
                "confidence": "number in [0,1]",
            }
        ],
    }
    return (
        f"Board (label, from the source): {board_name}\n"
        "Extract the curriculum structure from the document below into the JSON "
        "shape that follows. Nest nodes from coarse to fine "
        "(grade > subject > unit > chapter > topic > outcome). Outcomes carry an "
        "observable can-do statement. Propose prerequisite edges between TOPICS "
        "only; they are candidates for human review, never facts.\n\n"
        f"JSON shape:\n{json.dumps(schema_hint, indent=2)}\n\n"
        "Return ONLY the JSON object. Document:\n"
        "-----\n"
        f"{document_text}\n"
        "-----\n"
    )


# ---------------------------------------------------------------------------
# Response parsing (defensive — never trusts the model's framing)
# ---------------------------------------------------------------------------


def _strip_json_fence(text: str) -> str:
    """Strip an optional ```json ... ``` fence the model sometimes adds."""
    t = text.strip()
    if t.startswith("```"):
        # drop the first fence line and a trailing fence if present.
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def extract_text_from_response(payload: dict[str, Any]) -> str:
    """Pull the concatenated text out of a Gemini ``generateContent`` response.

    Defensive: returns ``""`` for any shape that lacks text, so a malformed or
    blocked response degrades to "no structure" rather than raising.
    """
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    if not isinstance(parts, list):
        return ""
    chunks = [p.get("text", "") for p in parts if isinstance(p, dict)]
    return "".join(chunks)


def _coerce_confidence(value: Any, default: float = 1.0) -> float:
    try:
        c = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, c))


def _clean_outline(nodes: Any) -> list[dict[str, Any]]:
    """Keep only well-formed nodes whose kind is an ontology level.

    Drops anything the ontology does not define (never coins a node kind) and
    recurses into children. Pure and total — never raises on bad input.
    """
    out: list[dict[str, Any]] = []
    if not isinstance(nodes, list):
        return out
    for node in nodes:
        if not isinstance(node, dict):
            continue
        kind_name = str(node.get("kind", "")).strip().lower()
        if kind_name not in _KIND_BY_NAME:
            continue
        title = node.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        cleaned: dict[str, Any] = {
            "kind": kind_name,
            "title": title.strip(),
            "confidence": _coerce_confidence(node.get("confidence", 1.0)),
        }
        statement = node.get("statement")
        if isinstance(statement, str) and statement.strip():
            cleaned["statement"] = statement.strip()
        cleaned["children"] = _clean_outline(node.get("children", []))
        out.append(cleaned)
    return out


def _clean_edge_hints(raw: Any) -> list[ProposedEdgeHint]:
    """Parse proposed prerequisite hints. Every confidence is capped < 1.0 so a
    model proposal can never present itself as certain — confirmation is human."""
    hints: list[ProposedEdgeHint] = []
    if not isinstance(raw, list):
        return hints
    for item in raw:
        if not isinstance(item, dict):
            continue
        frm = item.get("from_title")
        to = item.get("to_title")
        if not isinstance(frm, str) or not isinstance(to, str):
            continue
        frm, to = frm.strip(), to.strip()
        if not frm or not to or frm == to:
            continue
        kind = PrerequisiteKind.HARD if str(item.get("kind", "soft")).strip().lower() == "hard" \
            else PrerequisiteKind.SOFT
        # Cap below 1.0: a proposal is a candidate, never a certainty.
        confidence = min(0.95, _coerce_confidence(item.get("confidence", 0.5), default=0.5))
        rationale = item.get("rationale")
        rationale = rationale.strip() if isinstance(rationale, str) and rationale.strip() else (
            f"Model-proposed prerequisite: '{frm}' may precede '{to}'."
        )
        hints.append(
            ProposedEdgeHint(
                from_title=frm,
                to_title=to,
                kind=kind,
                rationale=rationale + " Awaiting steward confirmation before it is trusted.",
                confidence=confidence,
            )
        )
    return hints


def parse_extraction(text: str) -> tuple[list[dict[str, Any]], list[ProposedEdgeHint]]:
    """Parse the model's JSON text into a cleaned outline + edge hints.

    Total: any parse failure yields ``([], [])`` so a malformed response
    degrades to "no structure" (the caller then records pending extraction or
    falls back to the deterministic parser) — it NEVER fabricates a tree.
    """
    cleaned = _strip_json_fence(text)
    if not cleaned:
        return [], []
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return [], []
    if not isinstance(data, dict):
        return [], []
    outline = _clean_outline(data.get("outline", []))
    hints = _clean_edge_hints(data.get("proposed_prerequisites", []))
    return outline, hints


# ---------------------------------------------------------------------------
# The live client
# ---------------------------------------------------------------------------


class GeminiDocumentUnderstanding:
    """Real Gemini-backed document understanding (the live extraction path).

    Reads the provider key by NAME at egress and calls Gemini over HTTPS via
    httpx. Degrades cleanly: with no key (or httpx unavailable) it returns an
    empty, clearly-marked unavailable extraction and never fabricates structure.

    The ``transport`` seam lets a test inject an httpx transport WITHOUT a
    network or a key — tests stay offline; the production path opens a real
    connection only when a key is present.
    """

    provider = PROVIDER_LABEL

    def __init__(
        self,
        *,
        settings: OntologySettings | None = None,
        model: str = DEFAULT_GEMINI_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._model = model
        self._timeout = timeout_seconds
        # Optional injected httpx transport (tests). Never carries a key.
        self._transport = transport

    @property
    def available(self) -> bool:
        """True only when a Gemini key is present (read by NAME, value never
        exposed). Absence -> the deterministic parser path downstream."""
        return self._settings.has_gemini

    def _raw_key(self) -> str | None:
        """The raw provider key, or ``None``. PRIVATE — never returned/logged."""
        key = self._settings.gemini_api_key
        if key is None or not str(key).strip():
            return None
        return str(key)

    def _unavailable(self, detail: str) -> GeminiExtraction:
        return GeminiExtraction(
            outline=[],
            edge_hints=[],
            available=False,
            provider=self.provider,
            detail=detail,
        )

    def extract(self, document_text: str, *, board_name: str) -> GeminiExtraction:
        """Call Gemini to extract a curriculum tree + proposed prerequisites.

        Returns an unavailable extraction (empty, no invention) when the key is
        absent, httpx is missing, the call fails, or the response is unparseable.
        """
        raw_key = self._raw_key()
        if raw_key is None:
            return self._unavailable(
                "Gemini provider key is not set. Provide the secret "
                f"'{ENV_GEMINI_API_KEY}' (OS env "
                f"'{ENV_GEMINI_API_KEY.replace('.', '_').upper()}'). Returning "
                "unavailable rather than fabricating curriculum structure; "
                "ingestion will fall back to the deterministic parser."
            )

        try:  # httpx is in requirements; guard anyway so import/use is safe.
            import httpx  # type: ignore
        except Exception:  # pragma: no cover - httpx is present in this env.
            return self._unavailable(
                "httpx is unavailable; cannot reach the Gemini endpoint. "
                "Returning unavailable (no fabrication)."
            )

        if not document_text or not document_text.strip():
            return self._unavailable("Empty document; nothing to extract.")

        prompt = build_prompt(document_text, board_name=board_name)
        request_body = {
            "system_instruction": {"parts": [{"text": _SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        url = f"{GEMINI_API_BASE}/models/{self._model}:generateContent"

        try:
            client_kwargs: dict[str, Any] = {"timeout": self._timeout}
            if self._transport is not None:
                client_kwargs["transport"] = self._transport
            with httpx.Client(**client_kwargs) as client:
                response = client.post(
                    url,
                    params={"key": raw_key},  # key by NAME at egress; never logged.
                    json=request_body,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # network / status / decode — degrade cleanly.
            # Never include the key or raw body in the detail.
            return self._unavailable(
                f"Gemini call failed ({type(exc).__name__}); returning unavailable "
                "without fabricating structure."
            )

        text = extract_text_from_response(payload)
        outline, hints = parse_extraction(text)
        if not outline:
            return self._unavailable(
                "Gemini returned no usable curriculum structure; returning "
                "unavailable (no fabrication)."
            )
        return GeminiExtraction(
            outline=outline,
            edge_hints=hints,
            available=True,
            provider=self.provider,
            detail=f"Extracted via {self.provider} (model={self._model}).",
        )
