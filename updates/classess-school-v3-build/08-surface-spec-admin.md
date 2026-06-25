# 08 · Surface Spec — Admin (34 surfaces)

Template as in `06`. **Admin cross-cutting:** role-scoped (owner, principal,
coordinator, HOD, examination, support, IT each see a different slice); manage by
exception — the platform surfaces what needs attention, the admin approves and steers;
the most powerful surfaces are the best-governed (tiered access, immutable audit,
break-glass). No single subject accent dominates; use the signature sparingly + neutral
steel.

---

## Home & assistant

### This morning · `/admin/`
Manage by exception.
- *v2→v3:* v2 opened on a principal KPI dashboard / module grid. v3 deletes both; the
  conversation-first home greets, and this is the calm morning-briefing destination.
- *Contains:* primary briefing (3 classes behind · 5 approvals blocking); actions Open
  exceptions / Approvals (5) / Ask anything; suggestion chips Academic / Operations /
  Curriculum.
- *Behaviour:* a morning briefing, not a dashboard — what requires attention today, which
  classes are behind, which teachers need support, which students need intervention, open
  parent concerns, blocking approvals, what improved after the last intervention. Each is
  a recommendation item.
- *Reads:* the proactive loop, approvals queue. *Emits:* `recommendation.actioned`.
- *DoD:* briefing not dashboard; role-scoped; recommendations carry provenance.

### Exceptions · `/admin/exceptions`
What needs attention, with evidence.
- *Contains:* list (Grade 8 Science — pacing; teacher support — 2; parent concerns — 4),
  each a recommendation item. *DoD:* full provenance; Approve acts.

### Institution assistant · `/admin/assistant`
Ask the institution anything.
- *Contains:* the Vidya canvas, shaped to the school's norms via hyperlocalization.
  *Behaviour:* admin-shaped assistant; answers and acts within the permission ladder.
  *DoD:* institution-shaped; permission-laddered.

### Ask-anything dashboard · `/admin/ask`
Question → widgets and reports, live.
- *v2→v3:* new — replaces v2's static dashboards with on-the-fly composition.
- *Contains:* the canvas ("Which Grade 8 sections are declining and why?"); actions Ask /
  Export. *Behaviour:* composes the requested view live from the governed semantic layer
  (one metric defined once, computed the same everywhere); focuses on actionable insight.
  *Capabilities:* compose-dashboard (read). *DoD:* live composition; governed metrics;
  export.

---

## Setup & governance config

### Blueprint wizard · `/admin/setup`
Stand up the school by interview.
- *v2→v3:* v2 had a deep School & Classrooms / infrastructure setup tree. v3 makes it a
  **conversational guided interview** (Vidya-driven), not hundreds of fields.
- *Contains:* the wizard (structure, boards, calendar, policies, approvals, comms); actions
  Run wizard / Approve structure.
- *Behaviour:* captures org structure, board/curriculum, academic year, working days/
  holidays, assessment/timetable policies, approval workflows, comms rules; generates the
  recommended structure/roles/policies for approval; builds the institution's digital twin;
  **persists to the real DB** (survives reload).
- *Writes:* institution, structure, roster, policies. *Emits:* `institution.configured`.
  *DoD:* conversational; generates + persists; human-approved.

### Hierarchy & relationships · `/admin/hierarchy`
Group → campus → grade → section, plus a relationship graph.
- *Contains:* configurable nodes + ownership/management/affiliation/funding edges; actions
  Add node / Link relationship.
- *Behaviour:* nodes configurable (not hard-coded levels); many-to-many, scoped + time-
  bound — a school can sit in a group, a district, and a funded programme at once.
- *DoD:* configurable nodes; relationship overlays; scoped + time-bound.

### Policies · `/admin/policies`
Inherit, override, or lock down the tree.
- *Contains:* table (policy · level · state); actions Set policy / Lock at node.
- *Behaviour:* policies flow down; inherit/override/lock per level; versioned with
  effective dates + audit; governs curriculum, assessment, grading, attendance, comms, AI
  usage, data retention.
- *DoD:* inheritance; versioning + effective dates; audit.

### Roles & access · `/admin/roles`
Role + attribute scoping.
- *v2→v3:* v2 had role definitions + user-role management. v3 keeps the role catalog,
  adds attribute scoping + delegation.
- *Contains:* table (role · scope · members); actions Add role / Scope by grade / Delegate-
  temporary. *Behaviour:* RBAC (what) + ABAC (where/for whom); delegated/temporary/
  substitute access first-class; role removal immediate on enrolment/employment change.
- *DoD:* RBAC+ABAC; delegation; immediate removal.

### Consent & permissions · `/admin/consent`
Captured once, travels with the data.
- *Contains:* list (AI use, camera/mic/recording, data sharing); actions Manage consent.
- *Behaviour:* consent established at the identity layer travels with the data, gating
  each role and cross-context read; age-tier aware. *DoD:* consent scoped + revocable;
  gates reads; age-tier aware.

### Hyperlocalization · `/admin/hyperlocalization`
Board, language, calendar, exam formats as config.
- *Contains:* form (primary language, region/calendar, exam patterns). *Behaviour:* becomes
  live configuration + AI behaviour (relevance, not translation). *DoD:* config drives
  delivery + AI behaviour.

---

## Academic config

### Curriculum & ontology · `/admin/curriculum`
Board mapping and ingestion.
- *v2→v3:* v2 had course/curriculum management + publisher selection. v3 keeps ingestion,
  adds the ontology + steward.
- *Contains:* the ontology view (board → subject → chapter → topic → outcome); actions
  Ingest curriculum / Map cross-board / Review steward proposals.
- *Behaviour:* curriculum ingested from documents/standards/publisher content and mapped;
  the **ontology steward** proposes mappings, flags duplicates, detects missing
  prerequisites — confirmed by a human before trusted; cross-board equivalence; versioned;
  outcome-coverage tracked. *Capabilities:* ingest, steward-propose (Prepare). *DoD:*
  ingestion + mapping; steward propose→confirm; equivalence; versioning.

### Grading config · `/admin/grading-config`
Blueprints, grade points, mark schemes.
- *v2→v3:* v2 grade-point setup + assessment structure re-skinned. *Contains:* form (grade
  scale, blueprint defaults, grade-point mapping). *DoD:* scale + blueprint defaults +
  grade points.

### Assessment config · `/admin/assessment-config`
Exam types, weightages, moderation rules.
- *v2→v3:* v2 report settings + assessment structure (formative/summative, scholastic/
  co-scholastic) re-skinned. *Contains:* table (type · weight · moderation). *DoD:* types +
  weightages + moderation rules.

---

## Calendar & timetable

### Academic calendar · `/admin/calendar`
Year, working days, holidays, events.
- *v2→v3:* v2 calendar dashboard + academic planner re-skinned. *Contains:* calendar with
  policy overlays. *DoD:* year + holidays + events + policy overlays.

### Timetable · `/admin/timetable`
Generated, scored, approvable.
- *v2→v3:* v2 timetable grids re-skinned; adds from-scratch generation with scored
  alternatives.
- *Contains:* 3 scored alternatives; actions Generate / Compare-approve / Trigger
  substitution. *Behaviour:* a constraint solver classifies rules hard/soft/contextual and
  produces alternatives (best academic balance / best workload balance / best resource use)
  for human approval; persists. *Capabilities:* generate-timetable (Prepare). *DoD:*
  generation; three named axes; human approval; persists.

### Substitution · `/admin/substitution`
The 6-level ladder, automatic.
- *v2→v3:* v2 teacher-substitution (with unassigned red state) re-skinned; the full ladder.
- *Contains:* list L1 same teacher → L6 academic-continuity alternative; actions Approve
  cover. *Behaviour:* the ladder searches in order (L1 same class+subject; L2 same subject
  another grade; L3 another qualified teacher; L4 cross-campus online under supervision;
  L5 external time-bound access then removed; L6 guided/recorded continuity — never a free
  period); picks up the lesson at the right point; absence triggers it automatically.
- *DoD:* six aligned levels; pick-up-at-the-right-point; absence-triggered; approval-gated.

### Pacing protection · `/admin/pacing`
Planned vs delivered; recover when behind.
- *Contains:* behind / recovery; actions Approve recovery. *Behaviour:* tracks planned vs
  delivered + instructional time lost; recommends recovery (added periods, revision blocks,
  reallocated slots); low-risk automatable within policy. *DoD:* tracking; recovery
  recommendations; policy automation.

---

## Intelligence

### Intelligence · `/admin/intelligence`
Academics, behaviour, care — with action.
- *v2→v3:* v2 principal analytics re-expressed as the proactive intelligence views.
- *Contains:* tabs Academics / Behaviour / Care; the study quadrant; actions Drill / Ask.
  *Behaviour:* surfaces actionable insight + recommended action, not routine stats; every
  alert carries evidence · confidence · owner · due · why-am-I-seeing-this. *DoD:* three
  lenses; action-first; full provenance.

### Study quadrant · `/admin/study-quadrant`
Star / emerging / potential / at-risk.
- *Contains:* the quadrant. *Behaviour:* sorts students into bands to target teaching; tap
  to drill/intervene. *DoD:* quadrant on v4; drill acts.

### Target analytics · `/admin/target-analytics`
Performance vs defined goals.
- *v2→v3:* v2 target settings + analytics re-skinned. *Contains:* target vs actual. *DoD:*
  targets vs actual; per subject.

### Syllabus coverage · `/admin/coverage`
Completion intelligence by class. *Contains:* table (class · subject · coverage). *DoD:*
  per-class coverage; flags behind.

### Prediction & trajectory · `/admin/trajectory`
Actual solid, predicted dotted.
- *v2→v3:* v2 trajectory/tendency charts re-skinned. *Contains:* trajectory per grade/
  subject. *Behaviour:* success probability + trajectory; recalculates achievable given
  time + weightage. *DoD:* actual+predicted; recalculation.

### Teacher analytics · `/admin/teacher-analytics`
Aggregate, support-first.
- *Contains:* note "no punitive ranking; employment decisions need human review."
  *Behaviour:* aggregate only after private coaching reaches the teacher first. *DoD:*
  support-first; no punitive ranking.

---

## People & ops

### Students registry · `/admin/students-registry`
Enrolment and scoped records.
- *v2→v3:* v2 student management + bulk import re-skinned. *Contains:* table (student ·
  grade · status); actions Add / Import (OneRoster). *DoD:* enrolment; scoped records;
  OneRoster import.

### Teachers & staff · `/admin/teachers-staff`
People and assignments. *Contains:* table (name · role · load); actions Add / Assign.
*DoD:* people + assignments + load.

### Houses & groups · `/admin/houses`
Non-academic structure. *Contains:* cards (Red, Blue, Green). *DoD:* house structure.

### Admissions · `/admin/admissions`
Edmissions citizen — linked, not built here. *Contains:* note "handled by the Edmissions
citizen." *DoD:* a clean link/handoff, not a built module.

### Content management · `/admin/content-mgmt`
E-books, recorded lectures, resources. *Contains:* table (asset · type · status). *DoD:*
  institution content catalog; status.

---

## Governance & integrations

### AI control centre · `/admin/control-centre`
Which agents run, their tools, routing.
- *Contains:* table (agent · tools · routing); actions Govern agents / Emergency disable /
  Model routing. *Behaviour:* the institution-level AI control centre — which agents run,
  permitted tools, model routing, an emergency disable switch; the most powerful surface,
  the best governed. *DoD:* agent governance; emergency disable; routing control; fully
  audited.

### Audit · `/admin/audit`
Immutable record of privileged actions. *Contains:* table (actor · action · when). *DoD:*
  immutable; queryable; complete.

### Break-glass · `/admin/break-glass`
Emergency access, fully logged. *Contains:* note "time-bound, reviewed, recorded"; actions
  Request access. *DoD:* time-bound; reviewed; recorded.

### Data governance · `/admin/data-governance`
Retention, lineage, consent, deletion.
- *Contains:* list (retention schedules, source lineage, export/correction/deletion).
  *Behaviour:* every insight carries lineage + recalculates when permissions change;
  export/correction/deletion first-class; deletion severs the PII link, aggregate remains.
  *DoD:* retention + lineage + erasure; recalculation on permission change.

### Integrations (FLUID) · `/admin/integrations`
Connect what the school runs.
- *Contains:* table (system · standard · health); actions Add connector / View sync
  history. *Behaviour:* LTI/OneRoster/xAPI/QTI/SCORM/Clever/Ed-Fi/CASE/MCP; can run as the
  intelligence layer on top, take over, or exchange data; connector-health monitoring;
  adapters are provider-pluggable (`13`). *DoD:* connector catalog; health; sync history;
  contract-complete adapters.

### Settings · `/admin/settings`
Institution preferences. *Contains:* list (branding, preferences). *DoD:* branding +
  preferences.
