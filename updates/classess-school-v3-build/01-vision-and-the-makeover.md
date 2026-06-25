# 01 · Vision and the Makeover

## Part A — The vision, compressed

We are not building another LMS. We are building an **agentic academic intelligence
platform** — one connected system that understands what is happening across an
institution, surfaces what matters, recommends the next best action, coordinates the
right people, and measures whether it worked. It does not wait to be asked.

The whole platform is one loop: **Plan → Teach → Observe → Assign → Assess →
Evaluate → Support → Communicate → Improve**, with intelligence running across all of
it, every cycle sharpening the next. Board-agnostic (CBSE, ICSE, Cambridge, IB, state
boards, simultaneously; curriculum ingested and mapped, never hard-coded). K-12 first,
architecture not narrowed to children. AI-native: content generated not stored,
learners understood not recorded, experiences composed per person, the system
improving across every event.

**The six intelligence mechanisms** (detail in `11`): the academic ontology
(relevance, not similarity); hyperlocalization (relevance, not translation); the
mastery model (`Performance × Reliability × Independence × Difficulty × Recency ×
Consistency` — never an average); the ten-gap engine (prerequisite, conceptual,
procedural, application, retention, language, accuracy, speed, confidence,
support-dependency); generate-and-verify (nothing unverified reaches a learner); and
the proactive loop (observe → interpret → recommend → approve → execute → outcome →
learn).

**The thread through all of it:** help a learner see and regulate their own thinking.
The deepest job is not to deliver answers; it is to make a learner a better,
more-independent judge of their own understanding. **The day a learner needs the
platform less is the day it succeeded.**

---

## Part B — The v2 audit (what is actually there today)

v2 is a real, comprehensive, in-use product across all four roles (235 screens
reviewed). **Its flow and coverage are an asset — they are validated by real
institutions and they map almost completely onto the d1–d22 capability surface.** Do
not invent a new flow; inherit this one. What must go is the *expression*.

### What v2 already covers (inherit this)

- **Student (44 screens):** a conversational-ish home, a course/chapter/topic outline,
  a lesson player with predict-then-check, a practice variety system (concept mastery,
  smart match, mind match, quick quiz, flashcards, match-the-pairs), generated content
  (fill-in-the-blank, mind maps), a galaxy/knowledge-map visual, quizzes and mock
  tests with question palettes and result breakdowns, assignments + submission, a
  comprehensive-insights analytics view, an attendance heatmap, printable report cards,
  subject progress, timetable, calendar, notifications, chat, and a full profile/
  settings cluster.
- **Teacher (77 screens):** a home, an analytics dashboard with a **study quadrant**
  (star / emerging / potential / at-risk), a course flow (term → period → chapter →
  topic) with launch/plan, lesson generation (plan / quiz / material / worksheet),
  a resource library, assignment creation and a **per-question student × question
  grading heatmap**, group projects with a multi-dimension rubric, blueprint-driven
  paper generation with sections and question types, a question bank, mock tests,
  remedial auto-grouping, timetable + a dense annual academic calendar, attendance
  grids, leave approval, a class roster with mastery, trajectory/tendency analytics,
  a gradebook, printable holistic report cards, PTM scheduling + a PTM dashboard, and
  a profile/preferences/leaves cluster.
- **Admin (83 screens):** a home, a principal dashboard, daily-operations and
  school-management module grids, staff + classroom attendance, leave + substitution
  (with an unassigned-substitution red state), a discipline log, assignment/performance
  oversight, a calendar dashboard + academic planner + exam calendar, a PTM/FTM
  creation wizard, a deep institutional-setup tree (infrastructure, academic year,
  class & division, terms, assessment structure, grading scheme, grade-point setup,
  targets, report settings), role & permission management with role definitions, user
  management + bulk import, course/curriculum management with publisher ingestion,
  assign-teachers-to-courses, lesson-plan setter, attendance-access control (manual /
  face recognition / geofencing), and student-level performance heatmaps.
- **Parent (31 screens):** a home with a child switcher, a parent dashboard, a child
  overview, attendance, assignments, results, report cards, holistic progress,
  comprehensive insights + trajectory, timetable, calendar, chat, meetings + a PTM
  booking wizard, notifications, and a profile (my children / security) cluster.

### What is wrong with v2 (discard this)

1. **The dead brand.** Coral + cream + Fraunces is the superseded v3 brand. Every
   surface must move to v4.1 steel + ultramarine (`04`). This alone transforms the
   product.
2. **Dashboard-first and module-grid homes.** Every role opens onto either a KPI
   dashboard or a "My Workspace" tile grid. **Both are deleted as homes.** The home
   is conversation-first and calm (`05`). Modules live in the rail, not as a wall of
   tiles the user must navigate.
3. **Chrome over meaning.** Donut charts, stacked KPI cards, and dense tables are used
   as the primary way to present everything — including things that should be a single
   plain-language sentence and a next action. v2 shows "82%" and a pie; v3 shows
   "Aanya can do this with guidance — the goal now is to do it without," with the
   evidence one tap away.
4. **Raw scores and percentages everywhere.** v2 leans on numbers (mastery %, marks,
   percentages) as the unit of truth. v3 replaces learner-facing numbers with the
   independence-aware plain-language mastery view; numbers remain only where a
   professional genuinely needs them (gradebook, blueprint marks) and always with
   evidence behind them.
5. **Modal-heavy, table-heavy density.** v2 buries flows in modals and packs screens
   with tables. v3 uses the tight matrix and the briefing/recommendation primitives,
   progressive disclosure, and generous European whitespace.
6. **No visible intelligence layer.** v2 reports the past; it rarely says "here is
   what I found and what to do about it." v3 makes the proactive loop the spine of
   every role's home and feed.
7. **No first-class evidence, confidence, or consent surfacing.** v3 adds the evidence
   drawer, the confidence band, and consent-aware reads everywhere a conclusion or an
   AI output appears.

---

## Part C — The makeover thesis (how each page is restructured)

The makeover is a **translation discipline**, applied identically to every one of the
136 surfaces. For each v2 screen, ask these in order and the v3 version falls out:

1. **What is the one intention of this screen?** Strip everything that does not serve
   it. If the v2 screen had five panels, four are probably progressive-disclosure or
   belong on another surface.
2. **What is the single next action?** Make it the visual focus (the briefing card /
   primary action), with time estimate, the "why," and the progress it creates.
3. **What here is a number that should be a sentence?** Convert learner-facing scores
   to independence-aware plain language; keep the number only for professionals, and
   attach an evidence drawer.
4. **What here is a dashboard that should be a recommendation?** Convert "here is the
   data" into "here is what I found, the evidence, the owner, and the action to
   approve." A chart survives only if a human genuinely reads the shape; otherwise it
   becomes a recommendation item.
5. **What modal should become an inline disclosure or its own page?** Small ephemeral
   results render inline (with "open in its page"); anything with persistent state
   gets a real page with Vidya docked.
6. **Where does Vidya belong on this screen?** Every surface is reachable and operable
   by conversation; the page is a destination Vidya routes to and stays docked over.
7. **Re-skin to v4.1.** Steel shell, one semantic accent for the surface's subject,
   hairlines and tonal steps instead of shadows, sharp corners, the tight matrix for
   grouped cards, Google Sans Flex, motion that animates meaning.

### The translation table (v2 pattern → v3 pattern)

| v2 pattern (discard) | v3 pattern (build) | Where defined |
|---|---|---|
| Coral/cream/Fraunces skin | v4.1 steel + ultramarine + Google Sans Flex | `04` |
| "My Workspace" tile grid home | Conversation-first home + slim icon rail | `05`, `11` |
| Principal/role KPI dashboard home | Today briefing (manage-by-exception) + proactive feed | `05`, `10` |
| Donut + KPI stack as default | Briefing card / recommendation item; chart only when shape is read | `10` |
| Raw mastery % to learners | Independence-aware plain-language mastery view | `10` |
| Modal-buried flows | Inline disclosure for small; dedicated page with docked Vidya for large | `05`, `11` |
| Dense tables everywhere | Tight matrix + evaluation review table + progressive disclosure | `04`, `10` |
| Static report of the past | Proactive loop: observe → recommend → approve → outcome | `11`, `13` |
| Conclusions without provenance | Evidence drawer + confidence band on every conclusion | `10` |
| Grading heatmap (student × question) | Same grid, re-skinned, now feeding the gap engine + confidence bands | `07`, `13` |
| Study quadrant (4-colour scatter) | Same quadrant, re-skinned, now a grouping + intervention launcher | `10` |
| Galaxy/knowledge-map visual | The knowledge view — independent vs support-dependent, queryable, ignite-on-mastery | `06`, `10` |
| Face-recognition / geofencing attendance | Same capability, consent-gated, assist-not-finalise, "needs human review" | `08`, `13` |
| Printable report cards | Same artifacts, re-skinned; parent version is the shareable proof artifact | `07`, `09`, `10` |

**The rule that prevents drift:** the makeover never removes a capability v2 had and
never adds a number where a sentence works. It changes the *expression and the
intelligence*, never the *coverage*. If a v2 flow exists, the v3 equivalent exists —
better. If a vision capability exists, it is threaded into the relevant v2 flow, not
bolted on as a new silo.
