"""QTI (Question & Test Interoperability) adapter (spine A6).

Parses QTI 2.x / 3.0 assessment items into the internal ``QTIItem`` shape and
serialises internal items back to QTI XML. Supports choice, text-entry,
extended-text and match interactions. Uses the stdlib XML parser with namespace
stripping so both 2.x and 3.0 namespaces parse.

QTI carries assessment CONTENT, not learner PII; no identity mapping is needed.
No live endpoint required.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any
from xml.sax.saxutils import escape

from ..connector import Capability, Connector, Direction
from ..models import QTIChoice, QTIInteraction, QTIItem, Standard


class QTIParseError(ValueError):
    """Raised when a QTI document cannot be parsed into an item."""


_INTERACTION_TAGS = {
    "choiceinteraction": QTIInteraction.CHOICE,
    "textentryinteraction": QTIInteraction.TEXT_ENTRY,
    "extendedtextinteraction": QTIInteraction.EXTENDED_TEXT,
    "matchinteraction": QTIInteraction.MATCH,
}


class QTIAdapter(Connector):
    standard = Standard.QTI

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "item.parse", Direction.INBOUND,
                "Parse a QTI assessment item (2.x/3.0) into the internal item shape.",
            ),
            Capability(
                "item.serialize", Direction.OUTBOUND,
                "Serialise an internal item to QTI 2.x assessmentItem XML.",
            ),
        ]

    # -- parse --------------------------------------------------------------
    def parse_item(self, xml_text: str) -> QTIItem:
        if not xml_text or not xml_text.strip():
            raise QTIParseError("empty QTI document.")
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:  # pragma: no cover - exercised via tests
            raise QTIParseError(f"malformed QTI XML: {exc}") from exc

        if _local(root.tag) != "assessmentitem":
            # Accept a wrapper whose first assessmentItem child is the item.
            found = _find(root, "assessmentitem")
            if found is None:
                raise QTIParseError("no <assessmentItem> element found.")
            root = found

        identifier = root.get("identifier") or "item"
        title = root.get("title") or identifier

        # correct responses live in responseDeclaration/correctResponse/value
        correct_responses = [
            (v.text or "").strip()
            for v in _findall_path(root, ["responsedeclaration", "correctresponse", "value"])
            if (v.text or "").strip()
        ]

        interaction_el = None
        interaction_kind = QTIInteraction.UNKNOWN
        for el in root.iter():
            kind = _INTERACTION_TAGS.get(_local(el.tag))
            if kind is not None:
                interaction_el = el
                interaction_kind = kind
                break

        prompt = ""
        choices: list[QTIChoice] = []
        max_score = None

        if interaction_el is not None:
            prompt_el = _find(interaction_el, "prompt")
            if prompt_el is not None:
                prompt = "".join(prompt_el.itertext()).strip()
            for choice_el in _iter_local(interaction_el, "simplechoice"):
                cid = choice_el.get("identifier") or ""
                text = "".join(choice_el.itertext()).strip()
                choices.append(
                    QTIChoice(identifier=cid, text=text, correct=cid in correct_responses)
                )

        # max score from outcomeDeclaration default value if present
        for outcome in _iter_local(root, "outcomedeclaration"):
            if (outcome.get("identifier") or "").upper() == "SCORE" or outcome.get("identifier") == "MAXSCORE":
                dv = _find(outcome, "value")
                if dv is not None and (dv.text or "").strip():
                    try:
                        max_score = float(dv.text.strip())
                    except ValueError:
                        pass

        item = QTIItem(
            identifier=identifier,
            title=title,
            interaction=interaction_kind,
            prompt=prompt,
            choices=choices,
            correct_responses=correct_responses,
            max_score=max_score,
        )
        return item

    # -- serialize ----------------------------------------------------------
    def serialize_item(self, item: QTIItem) -> str:
        lines: list[str] = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append(
            '<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p2" '
            f'identifier="{escape(item.identifier)}" title="{escape(item.title)}" '
            'adaptive="false" timeDependent="false">'
        )
        if item.correct_responses:
            lines.append('  <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="identifier">')
            lines.append("    <correctResponse>")
            for cr in item.correct_responses:
                lines.append(f"      <value>{escape(cr)}</value>")
            lines.append("    </correctResponse>")
            lines.append("  </responseDeclaration>")
        if item.max_score is not None:
            lines.append('  <outcomeDeclaration identifier="MAXSCORE" cardinality="single" baseType="float">')
            lines.append(f"    <defaultValue><value>{item.max_score}</value></defaultValue>")
            lines.append("  </outcomeDeclaration>")
        lines.append("  <itemBody>")
        if item.interaction is QTIInteraction.CHOICE:
            lines.append('    <choiceInteraction responseIdentifier="RESPONSE" maxChoices="1">')
            if item.prompt:
                lines.append(f"      <prompt>{escape(item.prompt)}</prompt>")
            for ch in item.choices:
                lines.append(
                    f'      <simpleChoice identifier="{escape(ch.identifier)}">{escape(ch.text)}</simpleChoice>'
                )
            lines.append("    </choiceInteraction>")
        elif item.interaction is QTIInteraction.TEXT_ENTRY:
            if item.prompt:
                lines.append(f"    <p>{escape(item.prompt)}</p>")
            lines.append('    <textEntryInteraction responseIdentifier="RESPONSE"/>')
        elif item.interaction is QTIInteraction.EXTENDED_TEXT:
            lines.append('    <extendedTextInteraction responseIdentifier="RESPONSE">')
            if item.prompt:
                lines.append(f"      <prompt>{escape(item.prompt)}</prompt>")
            lines.append("    </extendedTextInteraction>")
        else:
            if item.prompt:
                lines.append(f"    <p>{escape(item.prompt)}</p>")
        lines.append("  </itemBody>")
        lines.append("</assessmentItem>")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Namespace-agnostic XML helpers.
# ---------------------------------------------------------------------------
_NS = re.compile(r"^\{.*\}")


def _local(tag: str) -> str:
    return _NS.sub("", tag).lower()


def _find(el: ET.Element, local: str) -> ET.Element | None:
    for child in el.iter():
        if _local(child.tag) == local:
            return child
    return None


def _iter_local(el: ET.Element, local: str):
    for child in el.iter():
        if _local(child.tag) == local:
            yield child


def _findall_path(el: ET.Element, path: list[str]) -> list[ET.Element]:
    """Find all elements matching a chain of local names (namespace-agnostic)."""

    frontier = [el]
    for name in path:
        nxt: list[ET.Element] = []
        for node in frontier:
            for child in list(node):
                if _local(child.tag) == name:
                    nxt.append(child)
        frontier = nxt
    return frontier
