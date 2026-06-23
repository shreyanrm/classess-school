# START HERE — Classess School

You are about to build Classess School — an agentic academic intelligence platform, and the first institutional citizen of the Dot eVentures education ecosystem. You build the entire stack: UI, backend, AI, databases, authentication, integrations. Production-grade from line one — no MVP, no stubs.

## Read this dossier in order before writing anything

- `01-vision-and-requirements.md` — what we are building and what must be true.
- `02-laws-altitude-principles-security.md` — altitude, the ten principles, the twelve security invariants. Govern every decision.
- `03-architecture-and-boundary.md` — the three layers, the seam, the connection model, the secure-core boundary, the three rings.
- `04-build-breakdown.md` — the entire build in detail: every spine module, capability module, and surface.
- `05-build-flow.md` — what is built, in what order, how. Rings, slices, critical path, parallelization.
- `06-data-model-and-contracts.md` — the three store classes, the canonical tables, the PII rule, the `/contracts` package.
- `07-brand-and-ui-v4.md` — the v4 brand. The only brand. No exceptions.
- `08-pages-and-experience.md` — pages per role and the component vocabulary the UI is built from.
- `09-dynamic-workflow-playbook.md` — how you run: contracts-first, parallel agents in worktrees, the two gates, checkpoints.
- `10-ring0-build-brief.md` — the concrete first executable step. Build this first.

## Two things that hold across the whole dossier

1. **You build everything, including the UI.** Where any file says "developer lane," read "a Claude Code build agent." You run every lane as a parallel agent. Build full-stack per slice — backend, AI, data, auth, and UI together against the locked contracts. The secure-core boundary is an architectural discipline (credential isolation, the gateway wall, the event seam), not a human handoff; it holds even though you build both sides, and it future-proofs the moment humans join.
2. **The UI is v4 only.** Regenerate the brand skill from the delivered v4 kit and build every screen on it. Never apply the stale v3 skill. Never use generic defaults or framework base styles.
3. **The home is conversation-first and AI-native.** Vidya is the front door — a calm, near-empty conversational home with a slim feature rail, history tucked behind a button, the proactive layer surfaced as quiet suggestion chips, components rendered inline only when warranted, and big tasks routed to their page with Vidya docked. Full Vidya capabilities (on-screen explanations, self-assembling derivations, the editable canvas, interactive teaching content, multimodal, the assistance ladder, teach-back) and the full AI fabric (the model router, frontier and mid models, edge SLMs, the two tracks, generate-and-verify, observability) are intact and non-negotiable. See `07` and `08` for the experience, `04` and `09` for the fabric. No MVP, no phases — the full build, end to end.

## The kickoff prompt

Paste the following to begin:

> You are the build agent for Classess School — an agentic academic intelligence platform and the first institutional citizen of the Dot eVentures education ecosystem. You build the entire stack: UI, backend, AI, databases, authentication, everything. Production-grade from line one — no MVP, no stubs.
>
> Your standing context is this dossier. Read it in order first: 01 vision and requirements, 02 laws (altitude, principles, the twelve security invariants), 03 architecture and the secure-core boundary, 04 the entire build in detail, 05 the flow, 06 data model and the /contracts package, 07 the v4 brand (the only brand), 08 pages and experience, 09 how you run, 10 the Ring 0 kickoff.
>
> Non-negotiables: the twelve security invariants in 02 hold on every merge — PII vaulted and segregated, opaque canonical UUID, every call through the gateway, secrets env-only via Infisical (key naming clss.<app>.<env>.<purpose>, never in code, logs, or chat), the event contract immutable from line one, consent gating every cross-context read, generate-and-verify with a confidence gate, the permission ladder with human approval on anything consequential. Confidentiality discipline: never name the confidential orchestrator or leak codenames or personal names in any artifact. UI on v4 tokens only — regenerate the brand skill from the delivered v4 kit; never apply v3; never use generic defaults.
>
> Method: contracts before parallel work. Decompose by bounded context; run agents in their own git worktrees against the shared /contracts. The secure core gets your most rigorous, most reviewed passes. Every merge passes two gates — verification (invariants, event contract, confidence gate, tests) and a confidentiality scrub. Build full-stack per slice — backend, AI, data, auth, and UI together against the locked contracts. Stop and report at every ring and slice boundary; do not free-run the whole build.
>
> Provisioning: you are cleared to set up Supabase, install packages, and integrate APIs. When you need a credential, name the env var and tell me to place it in Infisical — never handle secrets in plaintext. Record everything you provision in ops/.
>
> Start now with Ring 0 (10-ring0-build-brief): repo + secrets + CI → the /contracts package, including the event and evidence schema (the attempt event, the independent-vs-supported flag, the mastery weighting, the ten gap types) → the Supabase substrate → identity → the gateway → the immutable event store. Pass the Ring 0 done-line, then stop and report before the first slice. Begin.
