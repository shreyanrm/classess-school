"""Tests for the REAL trace sinks (file JSONL + HTTP) and the tracer factory.

Spans must record the signals we care about — capability, model, tokens,
latency, served/withheld, confidence — to a pluggable backend:

  - the FILE sink writes one JSON object per span, with NO external service,
  - the HTTP sink POSTs spans to an OTEL/Langfuse-style endpoint (exercised
    OFFLINE via an injected poster — no live call), with the tracing key riding
    ONLY in the Authorization header,
  - the factory selects a backend from the environment BY NAME,
  - no secret ever lands in a span record.

Import-safe, no network.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.observability import (
    TRACING_FILE_ENV,
    TRACING_KEY_ENV,
    TRACING_URL_ENV,
    FileTraceSink,
    HttpTraceSink,
    NullTraceSink,
    Span,
    Tracer,
    make_tracer,
)


def _env_key(dotted: str) -> str:
    return dotted.replace(".", "_").replace("-", "_").upper()


def _record_a_span(tracer: Tracer) -> None:
    with tracer.span("orchestrator.handle", capability="content.generate-practice-item") as sp:
        sp.set("router.tier", "mid")
        sp.record_model("mid-external")
        sp.record_tokens(prompt=12, completion=8)
        sp.record_quality(served=True, confidence=0.9)


# ---------------------------------------------------------------------------
# Span serialisation
# ---------------------------------------------------------------------------

def test_span_as_record_carries_all_signals():
    sp = Span(name="orchestrator.handle")
    sp.set("capability", "content.generate-practice-item")
    sp.record_model("mid-external")
    sp.record_tokens(prompt=10, completion=5)
    sp.record_quality(served=False, confidence=0.4)
    sp.end_ns = sp.start_ns + 2_000_000  # 2 ms
    rec = sp.as_record()
    attrs = rec["attributes"]
    assert rec["name"] == "orchestrator.handle"
    assert rec["latency_ms"] is not None
    assert attrs["capability"] == "content.generate-practice-item"
    assert attrs["model"] == "mid-external"
    assert attrs["tokens.prompt"] == 10
    assert attrs["tokens.completion"] == 5
    assert attrs["tokens.total"] == 15
    assert attrs["quality.served"] is False
    assert attrs["quality.confidence"] == 0.4


# ---------------------------------------------------------------------------
# The FILE sink — JSONL, no external service
# ---------------------------------------------------------------------------

def test_file_sink_writes_jsonl(tmp_path):
    path = tmp_path / "traces" / "spans.jsonl"
    tracer = Tracer(sink=FileTraceSink(path=str(path)))
    _record_a_span(tracer)
    _record_a_span(tracer)

    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    attrs = first["attributes"]
    assert first["name"] == "orchestrator.handle"
    assert attrs["capability"] == "content.generate-practice-item"
    assert attrs["model"] == "mid-external"
    assert attrs["tokens.total"] == 20
    assert attrs["quality.served"] is True
    assert attrs["quality.confidence"] == 0.9
    assert first["latency_ms"] is not None


def test_file_sink_never_raises_on_bad_path(tmp_path):
    # A directory path (not a file) makes the open() fail; the sink must swallow.
    sink = FileTraceSink(path=str(tmp_path))
    sink.emit(Span(name="x"))  # no exception


# ---------------------------------------------------------------------------
# The HTTP sink — OTEL/Langfuse-style endpoint, offline via injected poster
# ---------------------------------------------------------------------------

@dataclass
class FakePoster:
    posted: list = field(default_factory=list)

    def post(self, *, url, headers, json_body):
        self.posted.append((url, dict(headers), json_body))


def test_http_sink_posts_span_record():
    poster = FakePoster()
    sink = HttpTraceSink(url="https://trace.example/api", api_key="trace-key-DO-NOT-LEAK", poster=poster)
    tracer = Tracer(sink=sink)
    _record_a_span(tracer)
    assert len(poster.posted) == 1
    url, headers, body = poster.posted[0]
    assert url == "https://trace.example/api"
    assert headers["Authorization"] == "Bearer trace-key-DO-NOT-LEAK"
    assert body["attributes"]["model"] == "mid-external"
    assert body["attributes"]["quality.served"] is True


def test_http_sink_key_never_in_span_record():
    poster = FakePoster()
    sink = HttpTraceSink(url="https://trace.example/api", api_key="trace-key-DO-NOT-LEAK", poster=poster)
    tracer = Tracer(sink=sink)
    _record_a_span(tracer)
    _, _, body = poster.posted[0]
    # The key rode only in the header — never inside the serialised span.
    assert "trace-key-DO-NOT-LEAK" not in json.dumps(body)


def test_http_sink_swallows_transport_errors():
    @dataclass
    class Exploding:
        def post(self, *, url, headers, json_body):
            raise RuntimeError("network down")

    sink = HttpTraceSink(url="https://trace.example/api", poster=Exploding())
    sink.emit(Span(name="x"))  # no exception propagates


# ---------------------------------------------------------------------------
# The factory — backend selection BY ENV NAME
# ---------------------------------------------------------------------------

def test_make_tracer_noop_with_empty_env():
    t = make_tracer(env={})
    assert isinstance(t._sink, NullTraceSink)
    assert t.backend_configured is False


def test_make_tracer_file_sink_from_env(tmp_path):
    path = str(tmp_path / "spans.jsonl")
    env = {_env_key(TRACING_FILE_ENV): path}
    t = make_tracer(env=env)
    assert isinstance(t._sink, FileTraceSink)
    assert t.backend_configured is True
    _record_a_span(t)
    assert json.loads(open(path).readline())["attributes"]["model"] == "mid-external"


def test_make_tracer_http_sink_from_env_with_key():
    poster = FakePoster()
    env = {
        _env_key(TRACING_URL_ENV): "https://trace.example/api",
        _env_key(TRACING_KEY_ENV): "tk-secret",
    }
    t = make_tracer(env=env, poster=poster)
    assert isinstance(t._sink, HttpTraceSink)
    assert t.backend_configured is True
    _record_a_span(t)
    _, headers, _ = poster.posted[0]
    assert headers["Authorization"] == "Bearer tk-secret"


def test_make_tracer_http_takes_priority_over_file():
    poster = FakePoster()
    env = {
        _env_key(TRACING_URL_ENV): "https://trace.example/api",
        _env_key(TRACING_FILE_ENV): "/tmp/should-not-be-used.jsonl",
    }
    t = make_tracer(env=env, poster=poster)
    assert isinstance(t._sink, HttpTraceSink)
