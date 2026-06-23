"""CASE (Competencies & Academic Standards Exchange) adapter (spine A6).

Parses a CASE CFDocument + CFItems (the IMS CASE JSON shape) into ontology
outcome candidates, preserving the item hierarchy via ``CFAssociations`` of type
``isChildOf``. The mapping is PROPOSED; the ontology steward confirms before the
edges are trusted (curriculum is mapped, never assumed).

CASE carries standards CONTENT (statement text, codes), not learner PII. No live
endpoint required; a live CASE registry pull would go through the gateway.
"""

from __future__ import annotations

from typing import Any

from ..connector import Capability, Connector, Direction
from ..mapping import OntologyResolver, map_outcome
from ..models import MappedOutcome, Standard


class CASEAdapter(Connector):
    standard = Standard.CASE

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "framework.parse", Direction.INBOUND,
                "Parse a CASE CFDocument/CFItems set into ontology outcome candidates.",
            ),
            Capability(
                "framework.pull", Direction.INBOUND,
                "Pull a framework from a CASE registry (via the gateway) and map it.",
            ),
        ]

    def parse_framework(
        self,
        package: dict[str, Any],
        *,
        ontology_resolver: OntologyResolver | None = None,
    ) -> list[MappedOutcome]:
        """Map a CASE package (``CFDocument`` + ``CFItems`` + ``CFAssociations``).

        Accepts either the full ``CFPackage`` envelope or a dict already
        containing ``CFItems``/``CFAssociations`` lists.
        """

        doc = package.get("CFDocument") or {}
        framework = doc.get("title") or doc.get("identifier")
        items = package.get("CFItems") or package.get("cfItems") or []
        associations = package.get("CFAssociations") or package.get("cfAssociations") or []

        # Map each item identifier to its external code first so a parent edge
        # can be expressed in the same external-code space the outcomes use.
        code_of: dict[str, str] = {}
        for item in items:
            identifier = item.get("identifier")
            if identifier:
                code_of[identifier] = item.get("humanCodingScheme") or identifier

        # Build child -> parent map from isChildOf associations (by identifier).
        parent_of: dict[str, str] = {}
        for assoc in associations:
            if (assoc.get("associationType") or "").lower() not in {"ischildof", "is child of"}:
                continue
            origin = (assoc.get("originNodeURI") or {})
            dest = (assoc.get("destinationNodeURI") or {})
            origin_id = origin.get("identifier") if isinstance(origin, dict) else None
            dest_id = dest.get("identifier") if isinstance(dest, dict) else None
            if origin_id and dest_id:
                parent_of[origin_id] = dest_id

        outcomes: list[MappedOutcome] = []
        for item in items:
            identifier = item.get("identifier")
            if not identifier:
                continue
            code = code_of[identifier]
            label = (
                item.get("fullStatement")
                or item.get("abbreviatedStatement")
                or item.get("humanCodingScheme")
                or identifier
            )
            parent_id = parent_of.get(identifier)
            parent_code = code_of.get(parent_id, parent_id) if parent_id else None
            outcomes.append(
                map_outcome(
                    self.standard,
                    code,
                    human_label=label,
                    framework=framework,
                    parent_external_code=parent_code,
                    resolver=ontology_resolver,
                )
            )
        return outcomes
