# Vision and requirements

## The vision

We are not building another learning-management system. We are building an **agentic academic intelligence platform** — one connected system that understands what is happening across an institution, surfaces what matters, recommends the next best action, coordinates the right people, and measures whether it worked. It does not wait to be asked. It observes, interprets, and acts.

A traditional LMS hands users dashboards and leaves them to find the problem and decide what to do. Classess School inverts this. The modules are stitched into one continuous workflow — **Plan → Teach → Observe → Assign → Assess → Evaluate → Support → Communicate → Improve** — and intelligence runs across all of it. Every cycle sharpens the next.

It is **board-agnostic**: CBSE, ICSE, Cambridge, IB, state boards and more, simultaneously, in a single deployment. Curriculum is ingested and mapped, never hard-coded. It targets **K-12** first, but the architecture carries a learner across stages without fracturing. It is **AI-native** — intelligence is the substrate: content is generated rather than stored, learners are understood rather than recorded, experiences are composed per person, and the system improves across every user and event. Remove the AI from a conventional product and you still have a product; remove it from this one and there is nothing underneath.

### How the intelligence works (six mechanisms)

1. **Academic ontology** — board → curriculum → grade → subject → unit → chapter → topic → prerequisite → outcome → competency → skill → question → resource, with cross-board equivalence. Relevance, not similarity.
2. **Hyperlocalization** — the same concept delivered for this board, language, region, calendar, and culture. Relevance, not translation.
3. **The mastery model** — never an average. Mastery = Performance × Reliability × Independence × Difficulty × Recency × Consistency. The Independence dimension separates what a learner can do alone from what they can only do with help.
4. **The learning-gap engine** — ten gap types (prerequisite, conceptual, procedural, application, retention, language, accuracy, speed, confidence, support-dependency), each needing a different response. Never confirmed from a single bad score.
5. **Generate, then verify** — content generated against the ontology, then passed through verification (deterministic checks, second-model cross-check, a confidence gate that refuses unverified work) before it ever reaches a learner.
6. **The proactive loop** — observe → interpret → recommend → approve → execute → outcome → learn, turning patterns into approvable actions carrying evidence, confidence, owner, due date, and consequence.

### The thread through all of it

Every mechanism points at one outcome: helping a learner **see and regulate their own thinking**. The platform's deepest job is not to deliver answers; it is to make a learner a better, more independent judge of their own understanding.

### Four roles, one platform

Admin, Teacher, Student, Parent — four views of one system, each showing only what that person needs, governed by permissions. One person can hold several roles under one identity.

## Requirements — what must be true

### Functional

- The full academic loop runs end to end: plan, teach, observe, assign, assess, evaluate, support, communicate, improve.
- Curriculum for any board is ingested and mapped into the ontology; cross-board equivalence is maintained.
- Mastery is computed multi-dimensionally and shown to learners in plain language (independent vs support-dependent), never as a raw formula.
- Gaps are classified into the ten types and drive which intervention fires; the profile updates only on fresh evidence.
- All learning content is generated and verified; nothing unverified is served.
- The evaluation engine runs three modes (post-submission, scanned-handwriting, preventive-before-submission), confidence-banded, human-final on consequential marks.
- The proactive layer turns patterns into approvable recommendations with full provenance.
- Core flows (attendance, lessons, assignments, basic evaluation) work offline and sync.
- Interface, conversation, content, and reports are multilingual with code-switching.
- Vidya is the intention-primary conversational fast-path across every role.

### Non-functional

- **Security:** the twelve invariants in `02` hold without exception.
- **Production-grade:** no MVP, no stubs; the full capability surface in `04` is the target.
- **Explainable:** every recommendation carries evidence, confidence, owner, and a "why am I seeing this."
- **Human authority:** anything consequential — send, submit, publish, delete, charge, grade — passes through a person.
- **Calm and restrained:** the experience is spacious and certain on the v4 brand (`07`), while the category is red-urgency noise.
- **Trustworthy by construction:** consent-gated, auditable, lineage on every insight, tenant-isolated, encrypted in transit and at rest.
- **Observable:** cost, latency, and quality traced across the AI fabric; full error monitoring and product analytics; every lever flaggable and A/B-testable.
