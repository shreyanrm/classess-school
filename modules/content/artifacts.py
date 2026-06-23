"""Topic artifacts: mind-maps and presentation outlines.

Generates two structured study artifacts from a topic, both through the
ai-fabric *generate-and-verify* path so that only VERIFIED artifacts are ever
served:

  * MIND_MAP        - a rooted tree of concept nodes (root -> branches -> leaves).
  * PRESENTATION    - an ordered outline of slides, each with a title and a
                      small set of bullet points.

Invariant notes (02-laws-altitude-principles-security.md):

  * Generate-and-verify + confidence gate: every artifact is generated, then
    independently verified for structural integrity, topic coverage and
    child-safety. Below the confidence floor, or on a failed verify, the
    artifact is NOT served (status REJECTED / HELD). Nothing unverified leaves
    this module.
  * Gateway: generation routes through a caller-injected ai-fabric client; with
    no client / no live key the module degrades to a deterministic offline
    generator so the feature still works in dev. Secrets are ENV-ONLY
    (clss.content.<env>.fabric_key), read by the gateway, never here.
  * Child-safety on every free-text surface: titles, nodes and bullets are all
    screened; any unsafe artifact is rejected.
  * PII-free: a topic is content, not identity; this module accepts no learner
    identifier at all.

Import-safe, standard-library only, no network/DB/keys required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Mapping, Optional, Sequence

# ---------------------------------------------------------------------------
# Confidence gate (non-secret config)
# ---------------------------------------------------------------------------

DEFAULT_CONFIDENCE_FLOOR = 0.6


# ---------------------------------------------------------------------------
# Child-safety screen
# ---------------------------------------------------------------------------

_UNSAFE_TERMS = (
    "kill", "suicide", "self-harm", "self harm", "weapon", "drug", "porn",
    "sex", "gun", "blood", "abuse",
)


def default_safety_screen(text: str) -> bool:
    low = (text or "").lower()
    return not any(t in low for t in _UNSAFE_TERMS)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class ArtifactKind(str, Enum):
    MIND_MAP = "mind_map"
    PRESENTATION = "presentation"


class ArtifactStatus(str, Enum):
    SERVED = "served"      # verified; safe to serve
    HELD = "held"          # confidence below floor
    REJECTED = "rejected"  # failed structural / safety verification


@dataclass(frozen=True)
class MindMapNode:
    label: str
    children: tuple = ()

    def node_count(self) -> int:
        return 1 + sum(c.node_count() for c in self.children)

    def depth(self) -> int:
        return 1 + (max((c.depth() for c in self.children), default=0))


@dataclass(frozen=True)
class Slide:
    title: str
    bullets: tuple = ()


@dataclass(frozen=True)
class Artifact:
    kind: ArtifactKind
    topic: str
    status: ArtifactStatus
    confidence: float = 0.0
    mind_map: Optional[MindMapNode] = None
    slides: tuple = ()
    note: str = ""

    @property
    def served(self) -> bool:
        return self.status is ArtifactStatus.SERVED


# ---------------------------------------------------------------------------
# Gateway client contract
# ---------------------------------------------------------------------------

# A generator client takes a structured request and returns a raw artifact
# spec mapping. Production routes through the ai-fabric gateway; secrets in ENV.
GeneratorClient = Callable[[Mapping[str, object]], Mapping[str, object]]


# ---------------------------------------------------------------------------
# Offline deterministic generators (degrade-gracefully fallback)
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-]+")


def _keywords(topic: str, limit: int = 5) -> List[str]:
    seen: List[str] = []
    for w in _WORD_RE.findall(topic):
        lw = w.lower()
        if lw not in {x.lower() for x in seen} and len(lw) > 2:
            seen.append(w)
        if len(seen) >= limit:
            break
    if not seen:
        seen = [topic.strip() or "topic"]
    return seen


def _offline_mind_map(topic: str) -> MindMapNode:
    branches = []
    aspects = ["definition", "key ideas", "examples", "common pitfalls", "why it matters"]
    kws = _keywords(topic)
    for aspect in aspects:
        leaves = tuple(
            MindMapNode(label=f"{kw} - {aspect}") for kw in kws[:2]
        )
        branches.append(MindMapNode(label=aspect, children=leaves))
    return MindMapNode(label=topic.strip() or "topic", children=tuple(branches))


def _offline_presentation(topic: str) -> List[Slide]:
    t = topic.strip() or "topic"
    kws = _keywords(topic)
    return [
        Slide(title=f"Introduction to {t}", bullets=("what we will cover", "why it matters")),
        Slide(title="Core concepts", bullets=tuple(kws[:3]) or ("concept",)),
        Slide(title="Worked example", bullets=("a step-by-step example", "what to notice")),
        Slide(title="Common pitfalls", bullets=("a frequent error", "how to avoid it")),
        Slide(title="Summary", bullets=("key takeaways", "where to go next")),
    ]


# ---------------------------------------------------------------------------
# Parse a gateway response into typed structures
# ---------------------------------------------------------------------------


def _parse_mind_map(spec: Mapping[str, object]) -> MindMapNode:
    def build(node: Mapping[str, object]) -> MindMapNode:
        children = node.get("children") or []
        return MindMapNode(
            label=str(node.get("label", "")),
            children=tuple(build(c) for c in children),  # type: ignore[arg-type]
        )

    root = spec.get("root") or spec
    return build(root)  # type: ignore[arg-type]


def _parse_presentation(spec: Mapping[str, object]) -> List[Slide]:
    slides_raw = spec.get("slides") or []
    out: List[Slide] = []
    for s in slides_raw:  # type: ignore[union-attr]
        out.append(
            Slide(
                title=str(s.get("title", "")),
                bullets=tuple(str(b) for b in (s.get("bullets") or [])),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Verification (generate-and-verify)
# ---------------------------------------------------------------------------


def _topic_tokens(topic: str) -> set:
    return {w.lower() for w in _WORD_RE.findall(topic)}


def verify_mind_map(
    root: Optional[MindMapNode],
    topic: str,
    *,
    safety_screen: Callable[[str], bool] = default_safety_screen,
) -> bool:
    """A mind-map is valid only if it is a non-trivial, safe, on-topic tree."""

    if root is None or not root.label.strip():
        return False
    if not root.children:                 # must branch
        return False
    if root.depth() < 2:                  # at least root -> branch
        return False
    if root.node_count() < 4:             # non-trivial
        return False

    labels: List[str] = []

    def walk(n: MindMapNode) -> None:
        labels.append(n.label)
        for c in n.children:
            walk(c)

    walk(root)
    if any(not lbl.strip() for lbl in labels):
        return False
    if not all(safety_screen(lbl) for lbl in labels):
        return False
    # topic coverage: the root must reflect the topic.
    tt = _topic_tokens(topic)
    if tt and not (tt & _topic_tokens(root.label)):
        return False
    return True


def verify_presentation(
    slides: Sequence[Slide],
    topic: str,
    *,
    safety_screen: Callable[[str], bool] = default_safety_screen,
) -> bool:
    """A presentation is valid only if ordered, substantive, safe, on-topic."""

    if len(slides) < 3:
        return False
    for s in slides:
        if not s.title.strip():
            return False
        if not s.bullets:
            return False
        if not safety_screen(s.title):
            return False
        if not all(b.strip() and safety_screen(b) for b in s.bullets):
            return False
    tt = _topic_tokens(topic)
    if tt:
        joined = " ".join(s.title for s in slides).lower()
        if not (tt & set(re.findall(r"[a-z\-]+", joined))):
            return False
    return True


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def _confidence_from(spec: Mapping[str, object], default: float) -> float:
    try:
        return float(spec.get("confidence", default))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def generate_mind_map(
    topic: str,
    *,
    gateway: Optional[GeneratorClient] = None,
    safety_screen: Callable[[str], bool] = default_safety_screen,
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
) -> Artifact:
    """Generate and verify a mind-map; serve only if verified.

    Gateway first (if supplied); falls back to the offline generator on any
    gateway error so the feature degrades gracefully without live keys.
    """

    root: Optional[MindMapNode]
    confidence: float
    if gateway is not None:
        try:
            spec = gateway({"task": "mind_map", "topic": topic})
            root = _parse_mind_map(spec)
            confidence = _confidence_from(spec, 0.75)
        except Exception:
            root = _offline_mind_map(topic)
            confidence = 0.7
    else:
        root = _offline_mind_map(topic)
        confidence = 0.7

    if confidence < confidence_floor:
        return Artifact(
            kind=ArtifactKind.MIND_MAP, topic=topic,
            status=ArtifactStatus.HELD, confidence=confidence,
            note="confidence below floor; not served",
        )
    if not verify_mind_map(root, topic, safety_screen=safety_screen):
        return Artifact(
            kind=ArtifactKind.MIND_MAP, topic=topic,
            status=ArtifactStatus.REJECTED, confidence=confidence,
            note="failed structural/safety verification; not served",
        )
    return Artifact(
        kind=ArtifactKind.MIND_MAP, topic=topic,
        status=ArtifactStatus.SERVED, confidence=confidence,
        mind_map=root, note="verified",
    )


def generate_presentation(
    topic: str,
    *,
    gateway: Optional[GeneratorClient] = None,
    safety_screen: Callable[[str], bool] = default_safety_screen,
    confidence_floor: float = DEFAULT_CONFIDENCE_FLOOR,
) -> Artifact:
    """Generate and verify a presentation outline; serve only if verified."""

    slides: List[Slide]
    confidence: float
    if gateway is not None:
        try:
            spec = gateway({"task": "presentation", "topic": topic})
            slides = _parse_presentation(spec)
            confidence = _confidence_from(spec, 0.75)
        except Exception:
            slides = _offline_presentation(topic)
            confidence = 0.7
    else:
        slides = _offline_presentation(topic)
        confidence = 0.7

    if confidence < confidence_floor:
        return Artifact(
            kind=ArtifactKind.PRESENTATION, topic=topic,
            status=ArtifactStatus.HELD, confidence=confidence,
            note="confidence below floor; not served",
        )
    if not verify_presentation(slides, topic, safety_screen=safety_screen):
        return Artifact(
            kind=ArtifactKind.PRESENTATION, topic=topic,
            status=ArtifactStatus.REJECTED, confidence=confidence,
            note="failed structural/safety verification; not served",
        )
    return Artifact(
        kind=ArtifactKind.PRESENTATION, topic=topic,
        status=ArtifactStatus.SERVED, confidence=confidence,
        slides=tuple(slides), note="verified",
    )
