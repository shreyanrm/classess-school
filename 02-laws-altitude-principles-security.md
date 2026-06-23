# Laws — altitude, principles, security

These govern every decision in the build. When a choice is unclear, these settle it.

## Altitude

- The ecosystem is the entity. KGtoPG is the platform citizen. Classess School is a citizen built on it.
- Spine (ecosystem-owned): identity, ontology, the event/evidence contract, the AI fabric, governance.
- School-specific: capability modules + role surfaces.
- **Hard rule:** a School module never owns a spine concern. Identity, the event contract, the ontology, and the evidence/mastery engine belong to the spine. Fusing any of them to School blocks the next citizen (Classess Learner) from reusing it.
- Board-agnostic — CBSE, ICSE, Cambridge, IB, state boards and more, simultaneously. Curriculum is ingested and mapped, never hard-coded.
- K-12 first, but the architecture is not narrowed to children — the identity model, the academic graph, and the intelligence carry a learner across stages.
- AI-native — intelligence is the substrate, not a chat button. Content is generated not stored, learners understood not recorded, experiences composed per person, the system improving across every event.
- Offline-capable and multilingual with code-switching.

## The ten principles

1. One screen, one intention, one next action. Navigation is journey-based, not module-based.
2. Explainable intelligence. Every recommendation shows why it appeared, the evidence, a confidence level, who is responsible, and the consequence of ignoring it.
3. Human authority. AI recommends, prepares, assists. People make consequential decisions. The system never quietly acts on something that matters.
4. Calm on the surface, intensity underneath. The intelligence works hard; the interface never shouts.
5. Progressive disclosure. Show the simple thing first; power is available, never imposed.
6. Board-agnostic and adaptive. The platform conforms to the institution; curriculum is mapped, never assumed.
7. Evidence over assertion. Every conclusion about a learner is linked to evidence; no permanent judgment from a single interaction.
8. Offline and low-bandwidth. Attendance, lessons, assignments, basic evaluation survive a dead network.
9. Multilingual by design. Interface, conversation, content, and reports support local languages while preserving subject terminology.
10. Trust is a product layer. Consent, source attribution, data control, and auditability are built in from the first line.

**The central tension.** The conscience layer describes a calm, dependency-reducing academic OS; the platform is proactive and habit-forming. Resolve it by one rule: engineer momentum only toward the behaviors that make a learner more independent — mastery, retrieval, independent attempts, consistency — and keep human authority on everything consequential. Optimize for outcomes, not engagement. Habit and integrity are the same loop.

## Security invariants (non-negotiable)

Checkable. A merge that violates any is rejected.

1. **PII is vaulted and segregated.** Canonical identity (PII) lives in a separate, more-restricted store. The event store, profile, graph, and feature store carry only the opaque `canonical_uuid` and behavioral data — never PII.
2. **The canonical UUID is opaque** — random, never derived from PII. Deletion drops the PII vault row, severing the link; de-identified aggregate behavior remains and is unlinkable to a person.
3. **Every call passes the gateway.** No service is reachable unauthenticated. RBAC + ABAC are enforced at the wall, not inside services.
4. **Secrets are environment-only.** Infisical / env vars exclusively. Never in code, config, logs, error messages, or chat. Key naming `clss.<app>.<env>.<purpose>`. Rotate immediately on exposure.
5. **The event contract is immutable and append-only from line one.** Emit a clean, attributed event for every meaningful action. Events are never mutated or deleted in place.
6. **Consent is a primitive.** Captured at the identity layer, stamped on every event, gating every cross-context read. No read proceeds without a satisfied consent + purpose check.
7. **Generate-and-verify.** No generated content is served unverified. A confidence gate refuses anything that fails verification. Deterministic checks where possible (symbolic for math/physics, re-run simulations, numeric bounds), plus a second-model cross-check.
8. **Permission ladder on any agent action:** Recommend → Prepare → Execute-with-permission → Safe-automatic. Anything that sends, submits, publishes, deletes, or charges requires explicit human approval. Agents hold no credentials and invoke only governed, least-privilege capabilities.
9. **Audit is immutable; privileged actions are break-glass.**
10. **Encryption in transit and at rest; tenant isolation** with logical separation per institution.
11. **Two tracks are never conflated.** Track 1 (external LLM routing) and Track 2 (proprietary / edge models) are separate in gateway config. The Track 2 slot exists from the start, filled later, no re-architecture.
12. **Confidentiality discipline.** Forbidden codenames, personal names, board lock-in language, and placeholder text never appear in any developer- or team-facing artifact. The confidential orchestrator is never named in those outputs; the team interacts with it only through the API.

**DPDP / consent-tier note:** the depth of behavioral profiling that lights up is gated by the consent/age tier that legally permits it. Verify the current DPDP children's-data rules before treating any tier as settled; build the doors the law provides, never chase gaps.
