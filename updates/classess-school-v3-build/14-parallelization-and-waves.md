# 14 · Parallelization and Waves

How to fan out without collisions. The rule: **contracts before parallel work.** Once
`/contracts` (`12`) is locked, agents run in isolated git worktrees against the shared
contracts; they never edit each other's files and never change a contract without a
deliberate version bump. Build full-stack per slice — backend, AI, data, auth, UI
together against the locked contracts — not layer-by-layer across the whole app.

## Bounded contexts = worktrees

One worktree per bounded context, each owning a directory tree and a module schema, all
binding to the same `/contracts`:

- **Core / spine** (secure-core, highest rigor): identity, gateway, event/evidence store,
  the AI fabric router + capability registry + agents + verification substrate, the
  learner-record engine (b8), governance/audit. *One careful builder; reviewed hardest.*
- **b1 Institution & Policy** · **b2 Scheduling & Continuity** · **b3 Content** ·
  **b4 Teaching** · **b5 Attendance** · **b6 Coursework & Assessment** · **b7 Learning** ·
  **b9 Relationships & Comms** · **b10 Teacher Growth** · **b11 Intelligence Views** —
  each its own worktree.
- **Surfaces** split by role lane: **Student**, **Teacher**, **Admin**, **Parent** — each
  consuming the typed gateway client generated from `/contracts/openapi`, never the module
  internals.
- **Design system** (`packages/design-system`) — built first; every surface depends on it.

Collision avoidance: a worktree edits only its own tree; cross-context needs go through
the gateway API + events, never a direct import or a shared mutable file. The typed client
and the event schemas are generated, not hand-shared.

## The dependency DAG (what must precede what)

```
/contracts  ─┬─► design-system ───────────────► all surfaces
             ├─► identity ─► gateway ──────────► every module + surface call
             ├─► event/evidence store ─────────► every emit; the engine; the feed
             ├─► AI fabric (router+registry+verify) ─► b3/b4/b6/b7/b8/b9/b11 + Vidya
             └─► learner-record engine (b8) ───► b7, b11, all progress/eval surfaces
                                                 (b8 reads events; b7/b11 read b8 views)
b1 ─► b2 (policy/calendar) ─► b5 triggers b2 (substitution)
b3 ─► b4, b6, b7 (content feeds teaching/assessment/learning)
b6 + b7 ─► b8 (coursework/learning produce evidence the engine consumes)
b8 ─► b9 (reports feed comms/absolution) and ─► b11 (feed/quadrant/trajectory)
b4/sessions ─► b10 (coaching signals)
```

Anything not on a path to a shared node runs in parallel. The engine (b8) reads the event
store and is read by b7/b11 — so the event contract and b8's view contracts must land in
Wave 0/early Wave 1 before the surfaces that bind to them.

## The wave schedule (sequence of parallel fronts)

### Wave 0 — reconcile + base (serial; settle before anything rides on it)
- Lock `/contracts` (events, evidence, openapi, db, engine I/O, tokens, capabilities).
- Stand up the data substrate (PII vault separate; event store append-only; projections),
  identity, the gateway, secrets (Infisical), CI.
- Build the design-system package on v4.1 tokens.
- **Fix the four drifts (`03`):** conversation-first home shape; delete the duplicated TS
  engine and route to the spine; route every surface through gateway+identity; plan to
  surface every module.
- **Done-line:** contracts frozen; PII segregation proven; an event round-trips end to end;
  one gateway'd call works from a surface with RBAC/ABAC+consent; the v4 token layer
  renders; `npm run ci` green. **Stop and report.**

### Wave 1 — the Student⇄Teacher loop (the heart; parallel fronts on a settled base)
- Parallel: **b7 Learning** + **b8 Learner-record engine** + **b6 Coursework/Assessment** +
  **b3 Content** + **AI fabric** generate-and-verify + the **Student** and **Teacher**
  surface lanes for the loop (Learn/Practice/Assess/Work/Progress ↔ Plan/Evaluate/Assign/
  Students/Insights).
- The full circuit lights up for one slice: identity → surface → capability → event →
  engine → recommend → approve → execute → outcome → learn.
- **Done-line:** a learner learns→practises→submits; a teacher plans→assigns→evaluates;
  evidence flows; mastery + a gap compute from real events; content is verified; the
  permission ladder holds; every loop action emits its event; all five states present; CI
  green; confidentiality scrub clean. **Stop and report.**

### Wave 2 — Admin + Parent (parallel) + intelligence depth
- Parallel: **b1 Institution/Policy** + **b2 Scheduling/Continuity** + **b5 Attendance** +
  **b11 Intelligence Views** + **b9 Relationships/Comms** + **b10 Teacher Growth**, with
  the **Admin** and **Parent** surface lanes.
- The proactive feed, study quadrant, trajectory, the absolution engine + consent authority,
  PTM, communication, coaching.
- **Done-line:** an admin configures + governs the institution (persisted); the proactive
  loop recommends→approves→executes→returns outcomes; a parent gets reassurance + one action
  + the shareable win; comms translate + make-tasks; CI green; scrub clean. **Stop and
  report.**

### Wave 3 — ecosystem scale + parked providers
- FLUID live connectors; comms lifecycle (WhatsApp/SMS/email keys); multi-tenancy across
  group/franchise/programme/network; **Track 2** models behind the router slot; the **Expo
  native** tree (offline-first); the live-media board adapters.
- **Done-line:** connectors exchange data; tenancy isolates; a Track-2 capability swaps in
  by config; native parity for the core flows; parked adapters activate on key placement.
  **Stop and report.**

The event contract is Wave 0 though the intelligence consuming it matures across 1–3. Emit
from line one; consume as it matures.

## Agent roles (the build crew)

- **Planner** — owns `/contracts` and the DAG; the only one who version-bumps a contract;
  assigns worktrees; runs the wave gates.
- **Core builders** — the secure core (identity/gateway/event/evidence/AI-fabric/engine/
  governance); the most rigorous review; credential-isolated.
- **Module builders** — one per bounded context (b1–b11); own schema + API + events; bind
  to contracts.
- **Surface builders** — one per role lane (Student/Teacher/Admin/Parent); consume the
  typed client + the design system; never re-implement engine logic.
- **Verifier / scrubber** — runs the two gates on every merge.

## The two gates (every merge passes both)

1. **Verification gate:** the twelve invariants hold; the event contract is honoured (every
   consequential action emits its event); the confidence gate refuses unverified content;
   typecheck + vitest + pytest + `next build` green (`npm run ci`); the touched surfaces
   ship all five states; one engine (no TS re-implementation); every call gateway'd.
2. **Confidentiality scrub gate (`02`):** no codenames, no personal names, no board lock-in,
   no real institutions, `₹X,XXX` only, no plaintext secrets, v4.1 only. Automated scan +
   reviewer pass. A merge that fails either gate is rejected.

## Checkpoints

Stop and report at every wave done-line — never free-run the whole build. At each
checkpoint: what shipped, the gate results, what is parked (and its env var), and the next
wave's parallel fronts. Keep `15` green between checkpoints; record provisioning in `ops/`.
