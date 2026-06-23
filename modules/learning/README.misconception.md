# learning.misconception -- d12 misconception detonation

> Supplementary doc for `misconception.py`. The primary module `README.md` is
> owned by a prior wave and is append-only on disk; this file documents the
> d12 capability and the contract its test suite enforces.

From a wrong-answer attempt, identify the likely **misconception** and
engineer a targeted **counterexample** that surfaces the contradiction. The
probe is POSED, never lectured: the learner detonates their own misconception
by confronting a prediction their faulty model gets wrong.

## Contract (enforced by `tests/test_misconception.py`)

- A wrong answer yields a posed counterexample probe (a question), not a
  statement of the rule -- no "the correct answer is...", "you are wrong",
  "remember that...", etc.
- A correct attempt is not detonated (nothing to surface).
- Behavioral input carries only the opaque `canonical_uuid`; PII-like
  references (e.g. e-mails) are rejected by the PII guard.

## Invariants honoured

- **PII-free**: opaque `canonical_uuid` only.
- **Generate-and-verify + confidence gate**: a counterexample is served only
  when it genuinely contradicts the misconception and clears the confidence
  floor; otherwise the result HOLDs rather than guessing.
- **Child-safety**: the free-text probe is screened; unsafe probes are blocked.
- **Gateway / ENV-only secrets**: model-backed identification routes through
  the ai-fabric gateway (`clss.learning.<env>.fabric_key`, read by the gateway);
  with no key it degrades to deterministic detectors.
- **Immutable events**: a detonation event is a frozen, append-only record.

## Test note

`tests/test_misconception.py` is written to the *behavioral* contract and
adapts to the module's public entry point, so it remains valid against the
in-repo implementation while asserting the d12 "pose, do not lecture" rule.
