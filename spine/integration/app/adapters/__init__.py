"""Standards adapters for the FLUID bridge (spine A6).

Each adapter is interface-complete and degrades gracefully without a live
endpoint: it parses/maps against in-process data and reports health. None hold
credentials — outbound calls are described and handed to a governed capability
behind the gateway.
"""

from __future__ import annotations

from .caliper import CaliperAdapter
from .case import CASEAdapter
from .clever import ClassLinkAdapter, CleverAdapter
from .edfi import EdFiAdapter
from .lti import LTIAdapter, LTIMessageError
from .mcp import MCPServerSurface, MCPTool
from .oneroster import OneRosterAdapter
from .qti import QTIAdapter, QTIParseError
from .scorm import SCORMAdapter, SCORMParseError
from .xapi import XAPIAdapter

__all__ = [
    "CaliperAdapter",
    "CASEAdapter",
    "CleverAdapter",
    "ClassLinkAdapter",
    "EdFiAdapter",
    "LTIAdapter",
    "LTIMessageError",
    "MCPServerSurface",
    "MCPTool",
    "OneRosterAdapter",
    "QTIAdapter",
    "QTIParseError",
    "SCORMAdapter",
    "SCORMParseError",
    "XAPIAdapter",
]
