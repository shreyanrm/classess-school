"""Build VERSIONED, deduplicated, PII-scrubbed datasets (spine A4 — Track 2).

A dataset is the reproducible artifact a fine-tune consumes. This module turns
curated, admissible learning signals into a frozen ``Dataset`` with:

* DEDUPLICATION — identical (task_class, input, output) examples collapse to one.
* PII SCRUB — every example is re-scanned (INVARIANT 1/2); a leak ABORTS the
  build rather than shipping tainted data.
* CONSENT RE-CHECK — a dataset only ever contains admissible signals
  (INVARIANT 6). The builder refuses any inadmissible signal defensively.
* DETERMINISTIC SPLITS — train/val/test by a stable hash of the example id, so
  the same signals always land in the same split (reproducible).
* PROVENANCE + CONTENT HASH — the manifest records counts, per-class balance, the
  consent refs contributing (opaque), and a content hash over the canonical
  serialisation, so a build is fully reproducible and auditable.

No randomness, no clock-dependence in the content hash: same signals in -> same
hash + same splits out.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Iterable

from .capture import LearningSignal, assert_pii_free

DATASET_SCHEMA_VERSION = "v1"


@dataclass(frozen=True)
class DatasetExample:
    """A single frozen, PII-free training example."""

    example_id: str
    task_class: str
    input: str
    output: str
    reward: float
    verify_confidence: float | None = None

    def canonical(self) -> dict:
        """Stable dict for hashing (sorted, no volatile fields)."""
        return {
            "task_class": self.task_class,
            "input": self.input,
            "output": self.output,
            "reward": round(self.reward, 6),
        }


@dataclass(frozen=True)
class DatasetSplits:
    train: tuple[DatasetExample, ...]
    val: tuple[DatasetExample, ...]
    test: tuple[DatasetExample, ...]

    def counts(self) -> dict[str, int]:
        return {"train": len(self.train), "val": len(self.val), "test": len(self.test)}


@dataclass(frozen=True)
class DatasetManifest:
    """Full provenance for a built dataset — reproducible + auditable, PII-free."""

    dataset_id: str
    schema_version: str
    content_hash: str
    total_examples: int
    split_counts: dict[str, int]
    per_class_counts: dict[str, int]
    consent_refs: tuple[str, ...]
    split_ratios: tuple[float, float, float]
    split_seed: str
    deduplicated: int
    notes: str = ""


@dataclass(frozen=True)
class Dataset:
    manifest: DatasetManifest
    splits: DatasetSplits


class DatasetBuildError(ValueError):
    """Raised when a dataset cannot be built safely (PII leak / inadmissible)."""


def _example_id(sig: LearningSignal) -> str:
    """Deterministic example id from the content (so dedup + split are stable)."""
    basis = f"{sig.task_class}\x1f{sig.input}\x1f{sig.output}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def _split_bucket(example_id: str, seed: str, ratios: tuple[float, float, float]) -> str:
    """Stable split assignment by hashing (seed + example_id) into [0,1)."""
    h = hashlib.sha256(f"{seed}\x1f{example_id}".encode("utf-8")).hexdigest()
    # Use the first 8 hex digits as a fraction in [0,1).
    frac = int(h[:8], 16) / 0xFFFFFFFF
    train_r, val_r, _test_r = ratios
    if frac < train_r:
        return "train"
    if frac < train_r + val_r:
        return "val"
    return "test"


class DatasetBuilder:
    """Builds a reproducible :class:`Dataset` from curated learning signals."""

    def __init__(
        self,
        *,
        split_ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
        split_seed: str = "modelfoundry-v1",
    ) -> None:
        if abs(sum(split_ratios) - 1.0) > 1e-9:
            raise ValueError("split_ratios must sum to 1.0")
        self._ratios = split_ratios
        self._seed = split_seed

    def build(self, signals: Iterable[LearningSignal], *, notes: str = "") -> Dataset:
        signals = list(signals)

        # 1. Consent re-check (defence in depth — only admissible signals).
        for s in signals:
            if not s.admissible:
                raise DatasetBuildError(
                    f"inadmissible signal {s.signal_id} reached dataset builder"
                )

        # 2. PII scrub (INVARIANT 1/2) — abort on any leak.
        for s in signals:
            assert_pii_free(s.input, where="dataset.input")
            assert_pii_free(s.output, where="dataset.output")

        # 3. Deduplicate by deterministic example id.
        by_id: dict[str, DatasetExample] = {}
        dup_count = 0
        consent_refs: set[str] = set()
        for s in signals:
            eid = _example_id(s)
            consent_refs.add(str(s.consent_ref))
            if eid in by_id:
                dup_count += 1
                continue
            by_id[eid] = DatasetExample(
                example_id=eid,
                task_class=s.task_class,
                input=s.input,
                output=s.output,
                reward=s.reward,
                verify_confidence=s.verify_confidence,
            )

        examples = [by_id[k] for k in sorted(by_id)]  # deterministic order

        # 4. Deterministic splits.
        buckets: dict[str, list[DatasetExample]] = {"train": [], "val": [], "test": []}
        for ex in examples:
            buckets[_split_bucket(ex.example_id, self._seed, self._ratios)].append(ex)
        splits = DatasetSplits(
            train=tuple(buckets["train"]),
            val=tuple(buckets["val"]),
            test=tuple(buckets["test"]),
        )

        # 5. Per-class counts + content hash over the canonical serialisation.
        per_class: dict[str, int] = {}
        for ex in examples:
            per_class[ex.task_class] = per_class.get(ex.task_class, 0) + 1

        content_hash = self._content_hash(examples)
        dataset_id = f"ds-{content_hash[:16]}"

        manifest = DatasetManifest(
            dataset_id=dataset_id,
            schema_version=DATASET_SCHEMA_VERSION,
            content_hash=content_hash,
            total_examples=len(examples),
            split_counts=splits.counts(),
            per_class_counts=per_class,
            consent_refs=tuple(sorted(consent_refs)),
            split_ratios=self._ratios,
            split_seed=self._seed,
            deduplicated=dup_count,
            notes=notes,
        )
        return Dataset(manifest=manifest, splits=splits)

    @staticmethod
    def _content_hash(examples: list[DatasetExample]) -> str:
        """Hash over the sorted canonical examples — order-independent + stable."""
        canon = sorted(
            (json.dumps(ex.canonical(), sort_keys=True, separators=(",", ":")) for ex in examples)
        )
        h = hashlib.sha256()
        h.update(DATASET_SCHEMA_VERSION.encode("utf-8"))
        for line in canon:
            h.update(b"\x1e")
            h.update(line.encode("utf-8"))
        return h.hexdigest()


def manifest_dict(dataset: Dataset) -> dict:
    """Serialise a manifest to a plain dict (for events / persistence)."""
    return asdict(dataset.manifest)
