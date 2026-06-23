"""Observability — REAL tracing for cost / latency / quality (A4).

A span interface plus pluggable trace sinks. Spans carry the signals we care
about: capability, model, tokens (when the provider reports them), latency,
served/withheld, and confidence. Sinks are pluggable:

  - :class:`NullTraceSink`     — the no-op default (records nothing, never raises),
  - :class:`BufferingTraceSink` — in-memory, for tests / local inspection,
  - :class:`FileTraceSink`     — appends one JSON object per span to a JSONL file.
    Works with NO external service; the only configuration is a file path.
  - :class:`HttpTraceSink`     — POSTs spans to an OTEL/Langfuse-style HTTP
    endpoint over httpx. The endpoint URL and key are read by env var NAME,
    NEVER hardcoded (convention ``clss.<app>.<env>.<purpose>``):

      - tracing endpoint:  clss.aifabric.dev.tracing_url
      - tracing key:       clss.aifabric.dev.tracing_key

:func:`make_tracer` selects a backend from the environment by NAME: an HTTP sink
when the tracing endpoint env var is present, else a file sink when a tracing
file path env var is set, else the no-op sink — so the fabric runs fully without
any tracing provider. No secret is ever hardcoded and the tracing key is sent
only in the request header, never recorded in a span or returned.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Protocol


TRACING_URL_ENV = "clss.aifabric.dev.tracing_url"
TRACING_KEY_ENV = "clss.aifabric.dev.tracing_key"
# A plain file path (NOT a secret) for the local JSONL sink — no provider needed.
TRACING_FILE_ENV = "clss.aifabric.dev.tracing_file"


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

    # Convenience setters for the signals we care about.
    def record_cost(self, units: float, currency: str = "tokens") -> None:
        self.attributes["cost.units"] = units
        self.attributes["cost.currency"] = currency

    def record_model(self, model: str | None) -> None:
        """Record the model label that served (or was selected for) the span."""
        if model is not None:
            self.attributes["model"] = model

    def record_tokens(
        self,
        *,
        prompt: int | None = None,
        completion: int | None = None,
        total: int | None = None,
    ) -> None:
        """Record token usage when (and only when) the provider reports it."""
        if prompt is not None:
            self.attributes["tokens.prompt"] = int(prompt)
        if completion is not None:
            self.attributes["tokens.completion"] = int(completion)
        if total is None and (prompt is not None or completion is not None):
            total = (prompt or 0) + (completion or 0)
        if total is not None:
            self.attributes["tokens.total"] = int(total)

    def record_quality(self, *, served: bool, confidence: float) -> None:
        self.attributes["quality.served"] = served
        self.attributes["quality.confidence"] = confidence

    @property
    def latency_ms(self) -> float | None:
        if self.end_ns is None:
            return None
        return (self.end_ns - self.start_ns) / 1_000_000

    def as_record(self) -> dict[str, object]:
        """A JSON-serialisable record of the finished span.

        Only span data is included — never any secret. Attribute values are
        coerced to JSON-safe primitives; anything exotic falls back to ``str``.
        """
        def _safe(value: object) -> object:
            if value is None or isinstance(value, (bool, int, float, str)):
                return value
            return str(value)

        return {
            "name": self.name,
            "latency_ms": self.latency_ms,
            "attributes": {k: _safe(v) for k, v in self.attributes.items()},
        }


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


@dataclass
class FileTraceSink:
    """A real local sink: append one JSON object per span to a JSONL file.

    Works with NO external service — the only configuration is a file path. Each
    finished span is written as a single line via :meth:`Span.as_record`, so the
    file is a standard newline-delimited JSON trace log. Never raises into the
    caller: an I/O error is swallowed (observability must never break a served
    response), and no secret is ever written (records carry span data only).
    """

    path: str | os.PathLike[str]

    def __post_init__(self) -> None:
        # Best-effort: ensure the parent directory exists so first write lands.
        try:
            Path(self.path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def emit(self, span: Span) -> None:
        try:
            line = json.dumps(span.as_record(), separators=(",", ":"))
        except (TypeError, ValueError):
            return
        try:
            with open(Path(self.path).expanduser(), "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            # Tracing is best-effort; never break the served response on I/O.
            return


class SpanPoster(Protocol):
    """The HTTP seam an :class:`HttpTraceSink` uses to POST a span record.

    A real implementation wraps httpx; injected in tests so the sink can be
    exercised entirely offline (no live calls in tests).
    """

    def post(self, *, url: str, headers: dict[str, str], json_body: dict) -> None:
        ...


@dataclass
class HttpxSpanPoster:
    """A real httpx-backed poster for an OTEL/Langfuse-style trace endpoint.

    Constructs the request lazily so the module stays import-safe even if httpx
    were unavailable. The endpoint URL and bearer key are passed in by the sink
    (read by NAME from the environment); this poster never reads or stores a
    secret of its own and never logs the header.
    """

    timeout_seconds: float = 5.0

    def post(self, *, url: str, headers: dict[str, str], json_body: dict) -> None:
        import httpx  # local import: keeps the module import-safe / offline tests

        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(url, headers=headers, json=json_body)
            resp.raise_for_status()


@dataclass
class HttpTraceSink:
    """A real HTTP sink: POST each span to an OTEL/Langfuse-style endpoint.

    INVARIANT 4 — the endpoint URL and key are read by env var NAME, never
    hardcoded. The key is sent ONLY in the ``Authorization`` header at POST time;
    it is never written to a span, never returned, and never logged. With no
    endpoint configured the sink is inert (emits nothing). A network error is
    swallowed — observability must never break a served response.
    """

    url: str
    api_key: str | None = None
    poster: SpanPoster = field(default_factory=HttpxSpanPoster)

    def emit(self, span: Span) -> None:
        if not self.url or not self.url.strip():
            return
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            # Header only — the key never enters the span record or a log line.
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            self.poster.post(url=self.url, headers=headers, json_body=span.as_record())
        except Exception:
            # Best-effort delivery; never propagate a tracing failure to caller.
            return


def make_tracer(
    env: dict[str, str] | None = None,
    *,
    poster: SpanPoster | None = None,
) -> "Tracer":
    """Build a tracer with a backend selected from the environment BY NAME.

    Selection order (all by env var NAME — no secret hardcoded):
      1. HTTP sink when the tracing endpoint env var is present (OTEL/Langfuse
         style); the tracing key, if set, rides only in the request header.
      2. File JSONL sink when a tracing file path env var is set (no service).
      3. The no-op sink otherwise — the fabric runs fully without any backend.

    ``poster`` may be injected so the HTTP path is exercised offline in tests.
    """
    source = env if env is not None else dict(os.environ)
    url = source.get(_env_key(TRACING_URL_ENV))
    if url and url.strip():
        key = source.get(_env_key(TRACING_KEY_ENV))
        key = key if (key and key.strip()) else None
        sink = HttpTraceSink(
            url=url.strip(),
            api_key=key,
            poster=poster if poster is not None else HttpxSpanPoster(),
        )
        return Tracer(sink=sink, env=source)

    file_path = source.get(_env_key(TRACING_FILE_ENV))
    if file_path and file_path.strip():
        return Tracer(sink=FileTraceSink(path=file_path.strip()), env=source)

    return Tracer(env=source)


class Tracer:
    """Issues spans to a sink. Defaults to the no-op sink (no backend)."""

    def __init__(self, sink: TraceSink | None = None, env: dict[str, str] | None = None) -> None:
        self._env = env if env is not None else dict(os.environ)
        self._sink = sink if sink is not None else NullTraceSink()

    @property
    def backend_configured(self) -> bool:
        """True when a real backend (HTTP endpoint or file path) is configured."""
        url = self._env.get(_env_key(TRACING_URL_ENV))
        if url and url.strip():
            return True
        file_path = self._env.get(_env_key(TRACING_FILE_ENV))
        return bool(file_path and file_path.strip())

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
