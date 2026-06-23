# content.artifacts -- mind-maps & presentation outlines (verified-only)

> Supplementary doc for `artifacts.py`. The primary module `README.md` is owned
> by a prior wave and is append-only on disk; this file documents the addition.

Generates two structured study artifacts from a topic, each through the
ai-fabric **generate-and-verify** path. Only VERIFIED artifacts are served.

| Artifact       | Shape                                                      |
| -------------- | --------------------------------------------------------- |
| `MIND_MAP`     | rooted tree of `MindMapNode` (root -> branches -> leaves) |
| `PRESENTATION` | ordered list of `Slide` (title + bullet points)           |

## Usage

```python
from artifacts import generate_mind_map, generate_presentation, ArtifactStatus

art = generate_mind_map("Photosynthesis", gateway=my_fabric_client)
if art.status is ArtifactStatus.SERVED:
    tree = art.mind_map            # structured, verified
# else HELD (low confidence) or REJECTED (failed structure/safety) -- no content
```

## Generate-and-verify

1. **Generate** via the injected `gateway` client (ai-fabric); offline
   deterministic fallback when no client/key is wired.
2. **Confidence gate** -- below `DEFAULT_CONFIDENCE_FLOOR` (0.6) -> `HELD`.
3. **Verify** -- structural integrity (non-trivial tree / >=3 slides with
   bullets), topic coverage, and child-safety on every free-text label/bullet.
   Any failure -> `REJECTED`. Nothing unverified is ever exposed.

## Invariants honoured

- **Generate-and-verify + confidence gate**: enforced as above.
- **Child-safety on every free-text surface**: titles, nodes, bullets screened.
- **Gateway / ENV-only secrets**: generation routes through the gateway, which
  reads `clss.content.<env>.fabric_key` from the environment. Never read or
  hardcoded here.
- **PII-free**: a topic is content; no learner identifier is accepted.
- **Degrades gracefully**: gateway error -> offline generator (still verified).

## Tests

`tests/test_artifacts.py` -- structured/served artifacts, only-if-verified
(held below floor, rejected on bad structure/unsafe text), graceful gateway
fallback. No network, DB, or keys.
