# Workflow Engine (spine A5)

The proactive loop and the permission-ladder runtime that every module's
proactive behaviour runs on. This package owns the cycle; capability modules
(scheduling, teaching, parent comms, support, ...) plug in their own
interpreters and recommendation builders.

## The seven-step loop

```
observe(events) -> interpret(signals) -> recommend()
    -> approve() -> execute() -> outcome() -> learn()
```

1. **observe(events)** — gather attributed behavioural events into the working
   set. Guards INVARIANT 1/2: the loop reasons over the opaque `canonical_uuid`
   only and refuses any event payload carrying PII keys.
2. **interpret(signals)** — run pluggable interpreters that turn evidence into
   `InterpretedSignal`s. CORE correctness: a learner judgment is never confirmed
   from a single bad score — single-evidence signals are dropped unless
   corroborated (`require_corroboration`).
3. **recommend()** — dispatch each signal to its registered builder, producing
   `Recommendation` objects with FULL provenance: evidence summary, linked
   evidence refs (never an opaque claim), confidence band, owner (role + opaque
   ref), due date, consequence of ignoring, the plain-language
   `why_am_i_seeing_this`, the suggested action, and a ladder stage derived from
   the action's effect.
4. **approve()** — the human gate. The recommendation is opened as `PENDING` in
   the approval ledger; a human decision (`approve` / `adjust` / `decline`) is
   recorded with who and when. Agents hold no credentials and cannot
   self-approve.
5. **execute()** — the permission gate. Returns an `ExecutionResult`
   (a *clearance*), never a side effect. A consequential action is cleared only
   after a recorded human approval, and even then the actual
   send/submit/publish/delete/charge/grade is delegated to a governed,
   credentialled capability behind the gateway. A `safe_automatic`,
   non-consequential action may be cleared and performed unattended.
6. **outcome()** — capture what actually happened, linking the follow-on
   evidence that feeds the next cycle.
7. **learn()** — turn the outcome into an advisory `LearningNote`. It nudges
   confidence as data; it never silently re-rungs an action — changing what may
   auto-fire is a policy decision a human owns.

`WorkflowCycle` composes steps 1-3 into a single safe `run`; approval,
execution, outcome and learning are driven explicitly so the human gate is never
bypassed by a convenience call.

## The permission ladder (INVARIANT 8)

```
recommend -> prepare -> execute_with_permission -> safe_automatic
```

- **recommend** — surface it; the human decides everything.
- **prepare** — draft/stage the action without performing it.
- **execute_with_permission** — prepared and ready, but proceeds ONLY after an
  explicit human approval. Consequential actions live here and never auto-fire.
- **safe_automatic** — low-risk, in-policy actions that may proceed unattended
  with a full audit trail.

`permission.classify_action` returns a `LadderDecision` — a decision object, not
a side effect. The keystone rule: any effect that **sends, submits, publishes,
deletes, charges, or grades** is *consequential*; it is pinned to
`execute_with_permission`, can never be `safe_automatic`, and
`may_autofire` is always `False`. Non-consequential actions are
`safe_automatic` only when on an explicit policy allow-list (and not leaving the
platform boundary under a conservative policy); everything else **fails closed**
to `recommend`. The `Recommendation` model itself also refuses a consequential
`safe_automatic`, so the guarantee holds even if a builder is misused.

## Modules

| file | responsibility |
| --- | --- |
| `app/models.py` | Pydantic mirrors of `contracts/src/recommendations/*` — LadderStage, Recommendation, ApprovalDecision, plus the rung <-> event-PermissionRung mapping. |
| `app/permission.py` | Ladder classification and enforcement; returns decisions, never acts. |
| `app/recommendations.py` | Builders that turn interpreted signals into fully-provenanced Recommendation objects. |
| `app/approvals.py` | The approval state machine (`pending -> approved \| adjusted \| declined`) with an append-only trail recording who/when. |
| `app/loop.py` | The seven composable steps and the `WorkflowCycle` orchestrator. |
| `app/config.py` | Settings; degrades gracefully and names (only) the env vars it needs. |
| `tests/` | pytest: consequential actions never auto-fire; recommendations carry full provenance; approval transitions are correct. Import-safe. |

## Degraded operation

No live LLM keys or Supabase are required. Every deterministic path (ladder
classification, the approval state machine, the gated execute) works with no
provider. The optional second-model cross-check on interpretation is reached
through the gateway by route name; absent it, deterministic interpreters still
run. `WorkflowSettings.degraded_reasons()` lists the env-var names whose absence
keeps the engine on its deterministic-only path — names only, never values.

## Environment variables (names only)

Secrets are environment-only, read by name, never hardcoded (INVARIANT 4). The
engine holds no outward credentials — agents hold none (INVARIANT 8); it only
references governed services it calls through the gateway (INVARIANT 3).

| contract name | env var | purpose |
| --- | --- | --- |
| `clss.workflow.dev.gateway_base_url` | `CLSS_WORKFLOW_DEV_GATEWAY_BASE_URL` | the gateway every cross-service call passes through |
| `clss.workflow.dev.event_store_url` | `CLSS_WORKFLOW_DEV_EVENT_STORE_URL` | read evidence; append loop events |
| `clss.workflow.dev.jwt_public_key` | `CLSS_WORKFLOW_DEV_JWT_PUBLIC_KEY` | verify the identity token (PUBLIC key only; defence in depth) |
| `clss.workflow.dev.ai_fabric_route` | `CLSS_WORKFLOW_DEV_AI_FABRIC_ROUTE` | route NAME for the optional second-model cross-check (the provider key lives in the gateway, never here) |

## Running the tests

```
pip install -r requirements.txt
python -m pytest tests/ -q
```
