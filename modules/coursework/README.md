# Coursework & Assessment (B6)

A capability module over the secure core. The **evaluation engine is CORE-grade**
— correctness is existential. The module creates coursework, generates
blueprint-driven papers through generate-and-verify, evaluates submissions in
three modes, and emits submission / score / evidence events with the
independent-vs-supported flag.

It **consumes** the ontology contract, the AI fabric's generate-and-verify
substrate, and (through the evidence trail it emits) the intelligence
mastery/gap engines. It **never modifies** the spine.

## Package layout

| Module | Responsibility |
| --- | --- |
| `app/assignments.py` | Create assignments / quick-checks / projects, mapped to ontology topics/outcomes. AI-generated items must carry a passing verification block. |
| `app/papers.py` | Blueprint-driven paper generation. A blueprint is coverage by topic × difficulty band × cognitive level. Items go through the fabric's generate-and-verify; only verified items are included; withheld cells are flagged for human review. Multi-set (A/B/C…). |
| `app/evaluation.py` | The three-mode evaluation engine: `post_submission`, `scanned_handwriting`, `preventive_before_submission`. Per-response `answer_state` + `rubric_score` + `confidence_band`; submission-level human-final marking gate. |
| `app/rubric.py` | The rubric library + deterministic scoring. |
| `app/originality.py` | Originality / similarity check interface, with a deterministic in-process fallback. A signal to a human (RECOMMEND rung), never an accusation. |
| `app/events.py` | Build + emit `assignment.created` / `submission.created` / `score.recorded` / `attempt.recorded` on the exact contract shapes. Degrades to returning the event object when no store is wired. |
| `app/contracts.py` | Pydantic mirrors of the evaluation contract (`contracts/src/evaluation/index.ts`). |
| `app/config.py` | Settings — secret NAMES only (read by name, never hardcoded). |

## The non-negotiables (encoded structurally)

- **Permission ladder — grading is human-final.** A consequential mark is `final`
  only after an explicit human confirmation (`confirm_mark`). A HIGH-confidence
  engine result may stand as *provisional-auto* (`is_provisional_auto`); MIDDLE
  and LOW always route to human review. The engine holds no authority to
  finalise and no credentials.
- **Never penalise handwriting/scan.** In `scanned_handwriting` mode, poor scan
  or illegible handwriting **never reduces a mark** — it sets
  `needs_human_review` and lowers confidence; the score is untouched.
  `never_penalize_handwriting` is carried literally on every response result.
- **Preventive mode is helping, not grading.** It produces feedback before
  submission and can never become a consequential mark of record.
- **Generate-and-verify (INVARIANT 7).** No generated content is served
  unverified. The confidence gate refuses what fails deterministic checks or the
  second-model cross-check. With no second-model provider the gate stays closed
  and content is withheld — it degrades safely, never fabricates.
- **Never confirm a judgment from a single bad score.** The engine emits the
  per-response signal banded by confidence; the learner judgment is the evidence
  engine's job. A lone weak result surfaces for review, never as a verdict.
- **Behavioural data carries only the opaque `canonical_uuid`** — never PII.
  Events are immutable + append-only; this module only ever appends, stamps
  `consent_ref` and `purpose` on every event.

## Degraded operation (no live providers yet)

The module runs end-to-end with **no LLM key and no Supabase**:

- **Deterministic math/physics items** verify with no LLM (the fabric's
  symbolic/numeric verifier). They are served when a second model agrees and the
  confidence gate passes; otherwise withheld and flagged.
- **Free-text generation/evaluation** routes through the fabric, which returns a
  clean refusal with no provider — the relevant cells/responses are flagged for
  human authoring/review, never fabricated.
- **Event emission** with no store wired validates the event and returns the
  envelope object (`EmittedEvent.persisted is False`).
- **Originality** falls back to a deterministic in-process near-duplicate check.

## Environment variables (names only — never commit values)

Convention: `clss.<app>.<env>.<purpose>`, mapped to an OS env key by
`config.env_var_name` (e.g. `CLSS_COURSEWORK_DEV_EVENT_STORE_URL`). All are
optional; absent ones are reported by name via `CourseworkSettings.degraded_reasons()`.

| Dotted name | OS env var | Purpose |
| --- | --- | --- |
| `clss.coursework.dev.event_store_url` | `CLSS_COURSEWORK_DEV_EVENT_STORE_URL` | Event store endpoint (emit via its interface). |
| `clss.coursework.dev.gateway_url` | `CLSS_COURSEWORK_DEV_GATEWAY_URL` | Gateway base URL — every cross-service call passes the gateway. |
| `clss.coursework.dev.gateway_token` | `CLSS_COURSEWORK_DEV_GATEWAY_TOKEN` | Bearer issued by identity; never hardcoded. |
| `clss.coursework.dev.ai_fabric_url` | `CLSS_COURSEWORK_DEV_AI_FABRIC_URL` | AI fabric endpoint for generate-and-verify. |
| `clss.coursework.dev.ocr_provider_key` | `CLSS_COURSEWORK_DEV_OCR_PROVIDER_KEY` | OCR provider for scanned-handwriting mode. |
| `clss.coursework.dev.originality_provider_key` | `CLSS_COURSEWORK_DEV_ORIGINALITY_PROVIDER_KEY` | External similarity provider. |

## Tests

`tests/` covers the structural rules (human-final marking, never-penalise-scan,
preventive-never-final, non-high-band review), blueprint generate-and-verify
(served vs withheld, multi-set), originality banding, and event shapes validated
against the spine's event-contract mirror when importable.

```
python -m pytest
```

Tests require `pydantic` / `pydantic-settings` (same as the spine modules).
