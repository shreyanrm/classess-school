"""MCP (Model Context Protocol) server surface (spine A6).

Exposes the FLUID bridge as a set of MCP tools so an external agent can drive
integration capabilities through a uniform, governed surface. This is the
*surface*: it lists tools and validates/dispatches calls. It holds NO
credentials and performs NO outbound effect itself.

Permission-ladder discipline (INVARIANT 8): a tool flagged ``consequential`` (it
sends/submits/publishes to an external system) is NEVER auto-fired here. The
surface returns a PREPARED descriptor for the gateway + a human approval to
execute; only ``safe`` (read/parse/map) tools run inline.

CHILD-SAFETY (free text): any tool argument named as free text is screened by an
injected ``text_guard`` before dispatch; with no guard wired, free-text tools
refuse rather than pass unscreened input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from ..models import Standard


class TextGuard(Protocol):
    """Screens free-text input for child-safety before any processing.

    Returns True if the text is safe to proceed. The real implementation is the
    governance child-safety subsystem (A7), injected here.
    """

    def is_safe(self, text: str) -> bool: ...


@dataclass
class MCPTool:
    """A single MCP tool definition exposed by the bridge surface."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]
    consequential: bool = False
    free_text_fields: tuple[str, ...] = ()

    def to_descriptor(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "consequential": self.consequential,
                "readOnly": not self.consequential,
            },
        }


class MCPCallError(ValueError):
    """Raised when an MCP call is malformed or blocked by policy."""


@dataclass
class MCPServerSurface:
    """The MCP server surface over the integration bridge.

    Register parse/map/health tools (safe) plus passback/forward tools
    (consequential). ``call`` runs safe tools inline and returns a prepared,
    approval-gated descriptor for consequential ones.
    """

    server_name: str = "classess-fluid"
    protocol_version: str = "2025-06-18"
    text_guard: TextGuard | None = None
    _tools: dict[str, MCPTool] = field(default_factory=dict)

    def register(self, tool: MCPTool) -> MCPTool:
        if tool.name in self._tools:
            raise MCPCallError(f"duplicate MCP tool name: {tool.name}")
        self._tools[tool.name] = tool
        return tool

    def list_tools(self) -> list[dict[str, Any]]:
        return [t.to_descriptor() for t in self._tools.values()]

    def get(self, name: str) -> MCPTool | None:
        return self._tools.get(name)

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise MCPCallError(f"unknown MCP tool: {name}")
        args = arguments or {}

        # CHILD-SAFETY screen on every declared free-text field.
        for field_name in tool.free_text_fields:
            value = args.get(field_name)
            if value is None:
                continue
            if not isinstance(value, str):
                raise MCPCallError(f"field '{field_name}' must be text.")
            if self.text_guard is None:
                raise MCPCallError(
                    f"free-text field '{field_name}' cannot be processed: "
                    "no child-safety guard is wired (refusing to pass unscreened input)."
                )
            if not self.text_guard.is_safe(value):
                return {
                    "isError": True,
                    "blocked": True,
                    "reason": "child-safety",
                    "content": [
                        {"type": "text", "text": "This input was blocked by the safety check."}
                    ],
                }

        # CONSEQUENTIAL tools never auto-fire — return a prepared descriptor.
        if tool.consequential:
            return {
                "prepared": True,
                "requires_human_approval": True,
                "capability": tool.name,
                "arguments": args,
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"'{tool.name}' is a consequential action and was prepared, "
                            "not executed. It requires human approval before the gateway runs it."
                        ),
                    }
                ],
            }

        # Safe tool — run inline.
        result = tool.handler(args)
        return {"prepared": False, "content": [{"type": "text", "text": "ok"}], "result": result}

    def server_info(self) -> dict[str, Any]:
        return {
            "name": self.server_name,
            "protocolVersion": self.protocol_version,
            "capabilities": {"tools": {"listChanged": False}},
            "toolCount": len(self._tools),
        }


def default_surface(text_guard: TextGuard | None = None) -> MCPServerSurface:
    """Build an MCP surface pre-registered with the standard FLUID tools.

    Handlers are thin and side-effect-free here; in production they are bound to
    the connector framework and dispatch through the gateway.
    """

    surface = MCPServerSurface(text_guard=text_guard)

    surface.register(
        MCPTool(
            name="fluid.connectors.health",
            description="Report connector-health for all configured standards.",
            input_schema={"type": "object", "properties": {}},
            handler=lambda args: {"ok": True},
        )
    )
    surface.register(
        MCPTool(
            name="fluid.roster.import",
            description="Import a roster (OneRoster/Clever/ClassLink/Ed-Fi) into opaque refs.",
            input_schema={
                "type": "object",
                "properties": {"standard": {"type": "string"}},
                "required": ["standard"],
            },
            handler=lambda args: {"accepted": args.get("standard")},
        )
    )
    surface.register(
        MCPTool(
            name="fluid.qti.parse",
            description="Parse a QTI assessment item into the internal item shape.",
            input_schema={
                "type": "object",
                "properties": {"xml": {"type": "string"}},
                "required": ["xml"],
            },
            handler=lambda args: {"parsed": True},
        )
    )
    surface.register(
        MCPTool(
            name="fluid.lti.ags.scores",
            description="Post an AGS grade result to an external LMS (consequential).",
            input_schema={
                "type": "object",
                "properties": {
                    "line_item_url": {"type": "string"},
                    "score_given": {"type": "number"},
                },
                "required": ["line_item_url", "score_given"],
            },
            handler=lambda args: {"queued": True},
            consequential=True,
        )
    )
    return surface
