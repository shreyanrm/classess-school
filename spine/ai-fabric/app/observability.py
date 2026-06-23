"""Observability — tracing hooks for cost / latency / quality (A4).

A thin span interface. NO-OPS without a backend (degrades gracefully). When a
tracing backend is configured, an adapter implementing ``TraceSink`` forwards
spans to it. The provider URL is read by env var NAME, never hardcoded
(convention ``clss.<app>.<env>.<purpose>``):

  - tracing endpoint:  clss.aifabric.dev.tracing_url
  - tracing key:       clss.aifabric.dev.tracing_key

The default sink is ``NullTraceSink`` (records nothing, raises nothing) so the
fabric runs fully without a tracing provider.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Protocol


TRACING_URL_ENV = "clss.aifabric.dev.tracing_url"
TRACING_KEY_ENV = "clss.aifabric.dev.tracing_key"


def _env_key(dotted: str) -> str:
    return dotted.replace(".", "_").replace("-", "_").upper()


@dataclass
class Span:
    """A unit of traced work. Carries cost / latency / quality attributes."""

    name: str
    attributes: dict[str, object] = field(default_factory=dict)
    start_ns: int = field(default_factory=time.perf_counter_ns)
    end_ns: int | None = None

    def set(self, key: str, value: object) -> None:
        self.attributes[key] = value

    # Convenience setters for the three signals we care about.
    def record_cost(self, units: float, currency: str = "tokens") -> None:
        self.attributes["cost.units"] = units
        self.attributes["cost.currency"] = currency

    def record_quality(self, *, served: bool, confidence: float) -> None:
        self.attributes["quality.served"] = served
        self.attributes["quality.confidence"] = confidence

    @property
    def latency_ms(self) -> float | None:
        if self.end_ns is None:
            return None
        return (self.end_ns - self.start_ns) / 1_000_000


class TraceSink(Protocol):
    """A backend that receives finished spans."""

    def emit(self, span: Span) -> None:
        ...


@dataclass
class NullTraceSink:
    """The default no-op sink. Records nothing; never raises."""

    def emit(self, span: Span) -> None:  # noqa: D401 - intentional no-op
        return None


@dataclass
class BufferingTraceSink:
    """An in-memory sink — useful for tests and local inspection."""

    spans: list[Span] = field(default_factory=list)

    def emit(self, span: Span) -> None:
        self.spans.append(span)


class Tracer:
    """Issues spans to a sink. Defaults to the no-op sink (no backend)."""

    def __init__(self, sink: TraceSink | None = None, env: dict[str, str] | None = None) -> None:
        self._env = env if env is not None else dict(os.environ)
        self._sink = sink if sink is not None else NullTraceSink()

    @property
    def backend_configured(self) -> bool:
        """True only when a tracing endpoint env var is present."""
        url = self._env.get(_env_key(TRACING_URL_ENV))
        return bool(url and url.strip())

    @property
    def tracing_url_env(self) -> str:
        return TRACING_URL_ENV

    @contextmanager
    def span(self, name: str, **attributes: object) -> Iterator[Span]:
        sp = Span(name=name, attributes=dict(attributes))
        try:
            yield sp
        finally:
            sp.end_ns = time.perf_counter_ns()
            if sp.latency_ms is not None:
                sp.attributes.setdefault("latency.ms", sp.latency_ms)
            self._sink.emit(sp)
