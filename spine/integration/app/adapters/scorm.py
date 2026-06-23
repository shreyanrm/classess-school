"""SCORM adapter (spine A6).

Parses a SCORM ``imsmanifest.xml`` (1.2 / 2004) into the internal
``SCORMManifest`` shape: package identifier, version, default organisation
title, the launch resource, and the resource list. Detects cmi5/xAPI-launchable
packages too.

SCORM packages carry CONTENT, not learner PII. Runtime SCORM tracking (cmi.*)
that DOES describe a learner is relayed via the xAPI/Caliper -> event seam with
an opaque actor, not stored here. No live endpoint required.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..connector import Capability, Connector, Direction
from ..models import SCORMManifest, SCORMResource, Standard


class SCORMParseError(ValueError):
    """Raised when a SCORM manifest cannot be parsed."""


class SCORMAdapter(Connector):
    standard = Standard.SCORM

    def capabilities(self) -> list[Capability]:
        return [
            Capability(
                "manifest.parse", Direction.INBOUND,
                "Parse a SCORM imsmanifest.xml into the internal manifest shape.",
            ),
            Capability(
                "runtime.relay", Direction.INBOUND,
                "Relay SCORM/cmi5 runtime tracking via the xAPI event seam (opaque actor).",
            ),
        ]

    def parse_manifest(self, xml_text: str) -> SCORMManifest:
        if not xml_text or not xml_text.strip():
            raise SCORMParseError("empty manifest.")
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:  # pragma: no cover - exercised via tests
            raise SCORMParseError(f"malformed manifest XML: {exc}") from exc

        if _local(root.tag) != "manifest":
            raise SCORMParseError("root element is not <manifest>.")

        identifier = root.get("identifier") or "manifest"
        version = _detect_version(root)

        # default organisation
        organizations = _find(root, "organizations")
        default_org_id = organizations.get("default") if organizations is not None else None
        title = identifier
        launch_item_ref: str | None = None
        if organizations is not None:
            org = None
            for o in _iter_local(organizations, "organization"):
                if default_org_id is None or o.get("identifier") == default_org_id:
                    org = o
                    break
            if org is not None:
                t = _find(org, "title")
                if t is not None and (t.text or "").strip():
                    title = t.text.strip()
                first_item = _first_local(org, "item")
                if first_item is not None:
                    launch_item_ref = first_item.get("identifierref")

        # resources
        resources: list[SCORMResource] = []
        resources_el = _find(root, "resources")
        launch_href: str | None = None
        if resources_el is not None:
            for res in _iter_local(resources_el, "resource"):
                rid = res.get("identifier") or ""
                href = res.get("href") or ""
                scorm_type = _scorm_type(res)
                resources.append(SCORMResource(identifier=rid, href=href, scorm_type=scorm_type))
                if launch_item_ref and rid == launch_item_ref and href:
                    launch_href = href
            if launch_href is None:
                # fall back to the first SCO resource with an href
                for r in resources:
                    if r.scorm_type == "sco" and r.href:
                        launch_href = r.href
                        break

        return SCORMManifest(
            identifier=identifier,
            version=version,
            title=title,
            launch_href=launch_href,
            resources=resources,
        )


def _detect_version(root: ET.Element) -> str:
    # cmi5/xAPI packages carry a courseStructure / cmi5 namespace hint.
    blob = ET.tostring(root, encoding="unicode").lower()
    if "cmi5" in blob or "cmi.xsd" in blob and "xapi" in blob:
        return "cmi5/xapi"
    metadata = _find(root, "schemaversion")
    if metadata is not None and (metadata.text or "").strip():
        sv = metadata.text.strip()
        if sv.startswith("1.2"):
            return "1.2"
        if "2004" in sv or sv.startswith("CAM"):
            return "2004"
        return sv
    if "2004" in blob:
        return "2004"
    return "1.2"


def _scorm_type(res: ET.Element) -> str:
    for key, value in res.attrib.items():
        if _local_attr(key) == "scormtype":
            return (value or "sco").lower()
    return "sco"


# ---------------------------------------------------------------------------
# Namespace-agnostic helpers.
# ---------------------------------------------------------------------------
_NS = re.compile(r"^\{.*\}")


def _local(tag: str) -> str:
    return _NS.sub("", tag).lower()


def _local_attr(key: str) -> str:
    return _NS.sub("", key).lower()


def _find(el: ET.Element, local: str) -> ET.Element | None:
    for child in el.iter():
        if _local(child.tag) == local:
            return child
    return None


def _first_local(el: ET.Element, local: str) -> ET.Element | None:
    for child in el.iter():
        if _local(child.tag) == local:
            return child
    return None


def _iter_local(el: ET.Element, local: str):
    for child in el.iter():
        if _local(child.tag) == local:
            yield child
