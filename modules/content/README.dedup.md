# content.dedup -- content deduplication (semantic + hash)

> Supplementary doc for `dedup.py`. The primary module `README.md` is owned by
> a prior wave and is append-only on disk; this file documents the addition.

Keeps the catalog free of duplicates by detecting three classes of overlap:

| Kind            | How it is detected                                              |
| --------------- | -------------------------------------------------------------- |
| `EXACT`         | SHA-256 over normalised text (case/punctuation/whitespace fold) |
| `NEAR_HASH`     | Jaccard over word 3-shingles (small edits, reorderings)         |
| `NEAR_SEMANTIC` | Cosine over an ai-fabric embedding (paraphrases) -- lexical cosine fallback offline |

## Usage

```python
from dedup import ContentItem, find_duplicates, DedupIndex

corpus = [ContentItem("a", "The sun is a star at the centre of the solar system")]
cand = ContentItem("c", "the SUN is a star, at the centre of the solar system.")
verdicts = find_duplicates(cand, corpus)        # advisory only
# verdicts[0].requires_human_approval is True    # removal is consequential

idx = DedupIndex(embedder=my_fabric_embedder)    # embedder optional
idx.add(ContentItem("1", "..."))                 # stores only if unique
```

## Invariants honoured

- **PII-free**: items referenced by opaque `content_id`; no names/e-mails.
- **Gateway / ENV-only secrets**: the optional `embedder` routes through the
  ai-fabric gateway; the gateway reads `clss.content.<env>.fabric_key` from the
  environment. This module never reads a secret and never hardcodes one.
- **Permission ladder**: dedup only *flags* (`DuplicateVerdict.requires_human_approval = True`).
  Removing or merging catalog content is consequential and is never auto-fired.
- **Degrades gracefully**: with no embedder (no live key) it uses lexical
  similarity; an embedder that raises falls back rather than failing.

## Tuning (non-secret)

`DEFAULT_NEAR_HASH_THRESHOLD` (0.82), `DEFAULT_SEMANTIC_THRESHOLD` (0.86),
`SHINGLE_SIZE` (3) -- all overridable per call.

## Tests

`tests/test_dedup.py` -- exact / near-hash / near-semantic detection, self-skip,
advisory verdicts, graceful embedder-failure. No network, DB, or keys.
