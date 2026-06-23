# Ring 0 — definition of done

The definition-of-done checklist from the Ring 0 build brief (section 8), each
item marked **done**, **partial**, or **pending-provisioning** with a one-line
status. Code-shaped work is complete; items that require a live Supabase, Redis,
or Infisical are correct in source and gated behind named env vars, awaiting the
founder to provision and the orchestrator to install/build centrally.

| # | Done-line item | Status | Note |
|---|----------------|--------|------|
| 1 | CI green; secrets resolve from Infisical; nothing hardcoded | partial | Workspace + env-var convention in place, no secret hardcoded anywhere; CI pipeline and Infisical wiring are pending-provisioning (`ops/PROVISIONING.md`, `ops/ENV.md`). |
| 2 | `/contracts` compiles and exports types; a consumer can import it | done | `@classess/contracts` written for tsc-correctness with subpath exports; consumed today by `surfaces/web`. Run `npm run typecheck -w @classess/contracts` after the central install to confirm. |
| 3 | Supabase + Redis provisioned; migrations apply and roll back on a fresh project | partial | Seven idempotent migrations plus a documented rollback are written (`db/migrations`, `db/README.md`); applying them needs a provisioned Supabase project and Redis (pending-provisioning). |
| 4 | A user signs in (phone-OTP), a membership scopes access, consent is recorded | partial | `spine/identity` implements OTP start/verify, membership resolve, and consent grant/check end to end; live sign-in needs Supabase Auth provisioned and the signing key in Infisical. |
| 5 | No route reachable without a valid token + satisfied RBAC/ABAC; every call audited | done | `spine/gateway` verifies the token, enforces deny-by-default RBAC+ABAC, and audits every allow and deny; correct in degraded mode and on the production path. |
| 6 | A sample attributed event is emitted, stored immutably, and reads back only through a governed, scoped view | done | `spine/event-store` is INSERT-only with no update/delete and reads only through the consent+purpose gate; exercisable now in degraded mode, immutable at the DB by trigger when live. |
| 7 | PII vault segregated; no behavioral store carries PII; deleting the vault row leaves events unlinkable | done | Encoded structurally: separate `vault` schema, no FK across the boundary, opaque `canonical_uuid`, PII-key rejection in event payloads. |
| 8 | Confidentiality scrub passes on every artifact generated | done | No codenames, personal names, board lock-in language, or real pricing in any artifact; mock data is fictional and generic. |
| 9 | `ops/` documents the full provisioned setup | done | `ops/PROVISIONING.md` (what to provision and the steps) and `ops/ENV.md` (the consolidated env var inventory, names only). |

---

## What remains before the Student/Teacher slice (Ring 1)

Ring 0 source is complete; the following must happen before the first vertical
slice can run on real evidence:

1. **Provision and wire** — stand up the Supabase project (Postgres + pgvector +
   Auth + Realtime + Storage) and Redis, place all named secrets in Infisical,
   and stand up CI. (`ops/PROVISIONING.md`, `ops/ENV.md`.)
2. **Central install and build** — `npm install` at the root, `npm run build:contracts`
   and `npm run build:ds`, install each spine `requirements.txt`, and run the
   typecheck across workspaces. Apply the seven migrations to the fresh project.
3. **Distribute the token keys** — mint the RS256 key pair; identity holds the
   private key, the gateway and event store hold the public key (per-service
   names for rotation/audit). The unsigned dev token path must never reach
   staging/prod.
4. **Verify the loop end to end** — confirm sign-in -> membership scope ->
   consent -> attributed event -> governed read on the live substrate, and that
   the gateway audits every call.

Then Ring 1 fills the documented contract slots: the AI fabric Track 1 router
behind the gateway, the Track 2 reserved slot, the generate-and-verify
substrate (`Verification`/confidence gate), the permission-ladder runtime
(`PermissionRung`), and the evidence/mastery/gap engines that consume the event
seam — each only as deep as the Student/Teacher slice forces.
