# Dynamic-workflow playbook — how you run the rest

## Build scope

Claude Code is the sole builder and builds the entire stack — UI, backend, AI, data, authentication, integrations. The lanes below (core, backend, surface, integrations) are parallel Claude Code agents, not a human handoff. Build full-stack per slice: a slice's backend, AI, data, auth, and UI are built together against the locked contracts, with the UI on the v4 brand only (see `07-brand-and-ui-v4.md`).

## Principle

Context is the enabler, and the context that makes parallel agents safe is the contracts package plus the skills. **Contracts before parallelism.** Clean module boundaries are what keep parallel agents from colliding — the same rule that makes the architecture safe makes the parallelism safe.

## Method

1. **Contracts first.** Write `/contracts` before any parallel work. Load the relevant skills (brand, catalogs, schemas, rubrics). Flag missing or stale skills — the v4 brand skill needs regenerating; the loadable one is stale v3; do not apply v3.
2. **Decompose by bounded context.** One agent per module or slice-end, each in its own git worktree/branch, each handed a tight spec + the contracts + its skills. Agents on disjoint modules behind shared contracts run clean; agents on the same files collide.
3. **The secure core gets the most careful, most reviewed passes** — never a careless parallel agent. The hard-correctness IP (identity, gateway policy, event/evidence, evidence engine, router, verification) is yours, not a fan-out target.
4. **Two gates on every merge:**
   - **Verification:** the security invariants (`01`) hold, the event contract holds, the confidence gate is in place, tests pass.
   - **Confidentiality scrub:** no forbidden codenames, personal names, board lock-in language, or plaintext secrets in any artifact — especially anything developer-facing.
5. **Checkpoints.** Stop and report at every ring and slice done-line. Do not free-run across the whole build; human authority gates the boundaries.

## Agent roles

- **Planner** — defines the slice and its contracts (founder + Claude Code).
- **Core builders** — the secure-core engines.
- **Module builders** — capability modules against contracts.
- **Verifier / scrubber** — runs the two gates before any merge lands.

## The loop

```
plan slice + contracts
  → spawn agents (worktrees)
    → build against contracts, emit events
      → verify + scrub
        → integrate at the contract boundary
          → merge
            → checkpoint report → next slice
```

## Parallel vs serial

- **Serial:** Ring 0 — the base must settle before any slice rides on it.
- **Parallel:** once contracts land, the core engines and the developer lanes run simultaneously on disjoint modules. The contract boundary is the only integration point.

## Provisioning authority

You are cleared to scaffold and request whatever you need — the Supabase project, packages, API integrations. Two constraints, no exceptions: secrets via Infisical / env only (name the var `clss.<app>.<env>.<purpose>`, the founder places the value, you read it from the environment); and record everything provisioned in `ops/` so the setup is reproducible and auditable. No CDN dependencies in production.
