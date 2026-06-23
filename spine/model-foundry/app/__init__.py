"""Classess model foundry (spine A4 — Track 2 BASE).

The continuously-learning pipeline that turns everything happening in the
application into LEARNING SIGNALS and, eventually, a small proprietary edge
student model that fills the reserved Track 2 slot in the AI fabric.

This package is production-grade SCAFFOLDING: real, tested code for the whole
closed loop EXCEPT the actual GPU training, which is an injected backend that
degrades to a clearly-marked ``no-compute`` plan when no training endpoint is
configured (INVARIANT 4 — secrets ENV-ONLY). It never fabricates a model.

The twelve invariants are load-bearing here:

* INVARIANT 1/2 — behavioural data carries ONLY the opaque ``canonical_uuid``;
  PII NEVER enters a signal or a dataset (capture + dataset scrub enforce this).
* INVARIANT 6 — CONSENT + AGE-TIER (DPDP) gate what may be captured/used for
  training; minors are far more restricted; revocation removes a learner's
  contributed signals; provenance is transparent (consent_gate, deny-by-default).
* INVARIANT 7 — generate-and-verify + safety filtering before any example enters
  a dataset; only verify-passing outputs become positive targets (curate).
* INVARIANT 8 — the permission ladder: promoting a model to SERVE learners is
  consequential and requires explicit human approval; it never auto-promotes
  (registry).
* INVARIANT 11 — Track 1 (external) and Track 2 (proprietary / edge) stay
  separate; the foundry only ever produces Track 2 students.
"""

from __future__ import annotations

__all__ = [
    "config",
    "capture",
    "consent_gate",
    "dataset",
    "curate",
    "eval",
    "finetune",
    "registry",
    "loop",
    "events",
]

__version__ = "0.1.0"
