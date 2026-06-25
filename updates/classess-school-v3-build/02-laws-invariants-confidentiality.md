# 02 · Laws, Invariants, Confidentiality

These govern every decision. When a choice is unclear, these settle it.

## Altitude

- The ecosystem is the entity. The platform identity-and-intelligence layer is the
  platform citizen. Classess School is a citizen built on it.
- **Spine (ecosystem-owned):** identity, ontology, the event/evidence contract, the
  AI fabric, governance. **School-specific:** capability modules + role surfaces.
- **Hard rule:** a School module never owns a spine concern. If you are about to put
  identity, the event contract, the ontology, or the evidence/mastery/gap engine
  inside a School module, stop — it belongs to the spine. Fusing it to School blocks
  the next citizen from reusing it.
- Board-agnostic. K-12 first, not narrowed to children. AI-native — intelligence is
  the substrate, not a chat button. Offline-capable, multilingual with code-switching.

## The ten principles

1. **One screen, one intention, one next action.** Journey-based, not module-based.
2. **Explainable intelligence.** Every recommendation shows why it appeared, the
   evidence, a confidence level, the owner, and the consequence of ignoring it.
3. **Human authority.** AI recommends, prepares, assists. People make consequential
   decisions. The system never quietly acts on something that matters.
4. **Calm on the surface, intensity underneath.** The intelligence works hard; the
   interface never shouts. Calm is a deliberate status signal.
5. **Progressive disclosure.** Show the simple thing first; power is available, never
   imposed.
6. **Board-agnostic and adaptive.** The platform conforms to the institution;
   curriculum is mapped, never assumed.
7. **Evidence over assertion.** Every conclusion about a learner links to evidence;
   no permanent judgment from a single interaction.
8. **Offline and low-bandwidth.** Attendance, lessons, assignments, basic evaluation
   survive a dead network.
9. **Multilingual by design.** Interface, conversation, content, reports support local
   languages and code-switching while preserving subject terminology.
10. **Trust is a product layer.** Consent, source attribution, data control, and
    auditability are built in from the first line.

## The twelve security invariants (checkable; a merge that violates any is rejected)

1. **PII is vaulted and segregated.** Canonical identity (PII) lives in a separate,
   more-restricted store. The event store, profile, graph, and feature store carry
   only the opaque `canonical_uuid` and behavioral data — never PII.
2. **The canonical UUID is opaque** — random, never derived from PII. Deletion drops
   the PII vault row, severing the link; de-identified aggregate behavior remains and
   is unlinkable.
3. **Every call passes the gateway.** No service is reachable unauthenticated. RBAC +
   ABAC enforced at the wall, not inside services. A verified identity token is
   required for every request. *(v2/repo drift: surfaces that call Supabase Auth or
   the DB directly must be re-routed through the gateway and identity — see `03`.)*
4. **Secrets are environment-only.** Infisical / env vars exclusively. Never in code,
   config, logs, error messages, or chat. Key naming `clss.<app>.<env>.<purpose>`.
   Rotate immediately on any exposure.
5. **The event contract is immutable and append-only from line one.** Emit a clean,
   attributed event for every meaningful action. Events are never mutated or deleted
   in place.
6. **Consent is a primitive.** Captured at the identity layer, stamped on every event,
   gating every cross-context read. No read proceeds without a satisfied consent +
   purpose check.
7. **Generate-and-verify.** No generated content is served unverified. A confidence
   gate refuses anything that fails verification. Deterministic checks where possible
   (symbolic for math/physics, re-run simulations, numeric bounds), plus a
   second-model cross-check.
8. **Permission ladder on any agent action:** Recommend → Prepare →
   Execute-with-permission → Safe-automatic. Anything that sends, submits, publishes,
   deletes, or charges requires explicit human approval. Agents hold no credentials
   and invoke only governed, least-privilege capabilities.
9. **Audit is immutable; privileged actions are break-glass.**
10. **Encryption in transit and at rest; tenant isolation** with logical separation
    per institution.
11. **Two tracks are never conflated.** Track 1 (external LLM routing) and Track 2
    (proprietary / edge models) are separate in gateway config, different ownership.
    The Track 2 slot exists from the start, filled later, no re-architecture.
12. **Confidentiality discipline.** Forbidden codenames, personal names, board
    lock-in language, and placeholder text never appear in any developer- or
    team-facing artifact. The confidential orchestrator is never named in those
    outputs; the team interacts with it only through the API.

**DPDP / consent-tier note.** The depth of behavioral profiling that lights up is
gated by the consent/age tier that legally permits it. Verify the current DPDP
children's-data rules before treating any tier as settled; build the doors the law
provides, never chase gaps. Profiling is transparent and revocable. Treat the
children's-data consent model as an **open gating item**, not settled.

## The confidentiality scrub (run on every artifact before it lands)

A generated artifact — code comment, doc, seed data, UI string, commit message,
mock content — passes only if all hold:

- [ ] No confidential orchestrator / engine codename appears anywhere. Use generic
      names: "the orchestrator," "Vidya," "the content engine," "the platform
      intelligence layer," "the event store."
- [ ] No real personal names (founders, staff, the pedagogy author). The founding
      pedagogy is referenced as "the conscience layer / the pedagogy principles,"
      never attributed to a person.
- [ ] No board lock-in language (nothing that hard-codes or privileges one board;
      the platform is board-agnostic by contract).
- [ ] No real institution names. Seed/mock data uses fictional institutions and
      learners (e.g. "Northfield International," "Aanya," "Mr. Rao").
- [ ] No real pricing. Tech-facing mockups use `₹X,XXX`.
- [ ] No plaintext secrets, keys, tokens, or connection strings — anywhere, including
      logs and error messages.
- [ ] v4.1 only — no coral/cream/Fraunces remnants, no shadows, no generic defaults.

## The central tension (resolve it one way, always)

The conscience layer describes a calm, dependency-reducing academic OS; the platform
is proactive and habit-forming. Resolve it by one rule: **engineer momentum only
toward the behaviors that make a learner more independent** — mastery, retrieval,
independent attempts, consistency — and keep human authority on everything
consequential. Optimize for outcomes, not engagement. Habit and integrity are the
same loop. Never resolve the tension by abandoning either side.
