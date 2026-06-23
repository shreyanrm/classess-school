-- =============================================================================
-- 0010_operational_capabilities.sql
-- The per-capability operational tables: content, attendance, coursework +
-- gradebook + rubrics, messaging + tasks, learner record (profile / portfolio /
-- credentials), and timetable (calendars / slots / substitutions).
--
-- Same rules as 0008/0009: uuid PK, institution_id tenant scope, created_at /
-- updated_at, indexes for the obvious lookups, opaque canonical_uuid person
-- refs ONLY (never PII, no FK to pii_vault). Modules own their own tables.
-- RLS default-deny is applied in 0011_operational_rls.sql.
--
-- Idempotent.
-- =============================================================================

-- ===========================================================================
-- CONTENT (module: content, B3) — metadata only, never raw blobs.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- content_items: the library index over supporting material, keyed to ontology
-- topics. Carries the live version pointer, approval state, verification /
-- confidence state, and licence metadata. The version bodies live in
-- content_versions; raw media lives in governed storage, referenced by handle.
-- (mirrors modules/content/repository.py ContentRecord)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.content_items (
  content_id        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id    uuid        NOT NULL,   -- tenant scope (INVARIANT 10)

  -- Opaque ontology references (no PII).
  topic_id          uuid        NOT NULL REFERENCES operational.ontology_topics(topic_id)
                                ON DELETE RESTRICT,
  outcome_ids       uuid[]      NOT NULL DEFAULT '{}',

  kind              text        NOT NULL,   -- explanation|worked_example|practice_item|diagram|reading|video|document
  title             text        NOT NULL,

  approval_state    text        NOT NULL DEFAULT 'draft',  -- draft|in_review|approved|rejected|retired
  -- The live, learner-served version (must be approved + verified). NULL until
  -- approved through the human verification surface.
  live_version_id   uuid,

  -- Licence / provenance metadata. Nothing is served without clear rights.
  licence_code        text      NOT NULL DEFAULT 'all-rights-reserved',
  licence_holder      text,
  licence_source      text,     -- 'generated' | 'uploaded' | attribution URL/name
  attribution_required boolean  NOT NULL DEFAULT false,
  attribution_text    text,
  machine_generated   boolean   NOT NULL DEFAULT false,

  tags              text[]      NOT NULL DEFAULT '{}',
  -- pgvector embedding for semantic search over content (see content_versions
  -- for per-version verification; this is the record-level search vector).
  embedding         vector,

  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT content_items_kind_chk
    CHECK (kind IN ('explanation','worked_example','practice_item','diagram','reading','video','document')),
  CONSTRAINT content_items_approval_chk
    CHECK (approval_state IN ('draft','in_review','approved','rejected','retired'))
);
COMMENT ON TABLE operational.content_items IS
  'Content library index: metadata keyed to ontology topics. Approval + '
  'verification state, licence/provenance, semantic embedding. No raw blobs '
  '(media lives in governed storage, referenced by handle in content_versions).';
COMMENT ON COLUMN operational.content_items.embedding IS
  'Record-level pgvector embedding for semantic search; ANN index added by ops '
  'once the dimension is fixed.';

CREATE INDEX IF NOT EXISTS content_items_tenant_idx
  ON operational.content_items (institution_id);
CREATE INDEX IF NOT EXISTS content_items_topic_idx
  ON operational.content_items (topic_id, approval_state);
CREATE INDEX IF NOT EXISTS content_items_kind_idx
  ON operational.content_items (institution_id, kind);

DROP TRIGGER IF EXISTS content_items_touch ON operational.content_items;
CREATE TRIGGER content_items_touch
  BEFORE UPDATE ON operational.content_items
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- content_versions: the immutable, append-only version history of a content
-- item's body. A new version is appended on every change; existing versions are
-- never mutated (immutability enforced by trigger in 0011). verified_served
-- records whether the body passed the AI-fabric confidence gate (INVARIANT 7).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.content_versions (
  version_id          uuid      PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id      uuid      NOT NULL,
  content_id          uuid      NOT NULL REFERENCES operational.content_items(content_id)
                                ON DELETE CASCADE,

  number              integer   NOT NULL,   -- 1-based, monotonically increasing
  -- Kind-specific body metadata + an opaque handle to any media in governed
  -- storage. NEVER a raw blob inline; never PII.
  body                jsonb     NOT NULL DEFAULT '{}'::jsonb,
  content_ref         text,                 -- opaque handle into governed storage / CDN

  author              text      NOT NULL,   -- 'system:generate' | 'user:<role-label>' | 'ingest'

  -- Verification / confidence state (INVARIANT 7: nothing served unverified).
  verified_served       boolean   NOT NULL DEFAULT false,
  verification_status   text,               -- pending|passed|failed|human-override
  verification_confidence numeric,          -- verifier confidence in [0,1]
  verification_summary  text,
  source_request_id     uuid,               -- AI-fabric request that produced/verified this

  created_at          timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT content_versions_body_is_object CHECK (jsonb_typeof(body) = 'object'),
  CONSTRAINT content_versions_number_pos CHECK (number >= 1),
  CONSTRAINT content_versions_vstatus_chk
    CHECK (verification_status IS NULL
           OR verification_status IN ('pending','passed','failed','human-override')),
  CONSTRAINT content_versions_vconfidence_chk
    CHECK (verification_confidence IS NULL
           OR (verification_confidence >= 0 AND verification_confidence <= 1))
);
COMMENT ON TABLE operational.content_versions IS
  'Immutable, append-only content body versions. verified_served records the '
  'confidence-gate result (INVARIANT 7). content_ref points at governed storage; '
  'no raw blob, no PII. Mutation blocked by trigger.';

CREATE UNIQUE INDEX IF NOT EXISTS content_versions_item_number_uidx
  ON operational.content_versions (content_id, number);
CREATE INDEX IF NOT EXISTS content_versions_item_idx
  ON operational.content_versions (content_id);
CREATE INDEX IF NOT EXISTS content_versions_tenant_idx
  ON operational.content_versions (institution_id);

-- ===========================================================================
-- ATTENDANCE (module: attendance, B8) — opaque learner refs only, never PII.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- attendance_records: one finalised, human-confirmed mark per learner per
-- session. Capture METHODS propose; a human CONFIRMS (d8 / INVARIANT 3 + 8).
-- Only confirmed marks are persisted here; drafts live in the capture surface.
-- (mirrors modules/attendance/app/capture.py Mark / FinalisedRoll)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.attendance_records (
  record_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid        NOT NULL,   -- tenant scope (INVARIANT 10)

  session_id      uuid        NOT NULL,   -- the session/period this roll belongs to
  node_id         uuid        REFERENCES operational.structure_nodes(node_id)
                              ON DELETE SET NULL,   -- the section, when known

  -- Opaque learner ref ONLY. No FK to the pii_vault.
  canonical_uuid  uuid        NOT NULL,

  status          text        NOT NULL,   -- present|absent|late|excused|unknown
  method          text        NOT NULL,   -- photo_scan|voice|photo_roster|absent_only|online_presence|manual
  confidence      numeric     NOT NULL DEFAULT 1.0,    -- capture confidence in [0,1]

  -- Human gate: a confirmed record is consequential and never auto-fired.
  -- confirmed_by is the opaque ref of the confirming teacher (never PII).
  confirmed_by    uuid,
  confirmed_at    timestamptz,
  needs_review    boolean     NOT NULL DEFAULT false,   -- low-confidence / unresolved flag
  -- Risk flags surfaced for a human (consecutive / chronic / pattern). A SIGNAL
  -- only, never a verdict; the response is human-owned (d8).
  risk_flags      jsonb       NOT NULL DEFAULT '[]'::jsonb,
  note            text,                   -- screened free text (no PII)

  occurred_on     date        NOT NULL DEFAULT CURRENT_DATE,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT attendance_status_chk
    CHECK (status IN ('present','absent','late','excused','unknown')),
  CONSTRAINT attendance_method_chk
    CHECK (method IN ('photo_scan','voice','photo_roster','absent_only','online_presence','manual')),
  CONSTRAINT attendance_confidence_chk CHECK (confidence >= 0 AND confidence <= 1),
  CONSTRAINT attendance_risk_flags_is_array CHECK (jsonb_typeof(risk_flags) = 'array')
);
COMMENT ON TABLE operational.attendance_records IS
  'Finalised, human-confirmed attendance marks. Opaque learner ref ONLY, NO '
  'PII (no name/photo/biometric ever). Methods propose; confirmed_by + '
  'confirmed_at record the human confirm. risk_flags are signals, not verdicts.';
COMMENT ON COLUMN operational.attendance_records.canonical_uuid IS
  'Opaque learner reference. Logical link to pii_vault.users; deliberately no FK.';

CREATE INDEX IF NOT EXISTS attendance_tenant_idx
  ON operational.attendance_records (institution_id);
CREATE INDEX IF NOT EXISTS attendance_session_idx
  ON operational.attendance_records (session_id);
CREATE INDEX IF NOT EXISTS attendance_learner_date_idx
  ON operational.attendance_records (canonical_uuid, occurred_on);
-- One record per learner per session.
CREATE UNIQUE INDEX IF NOT EXISTS attendance_session_learner_uidx
  ON operational.attendance_records (session_id, canonical_uuid);

DROP TRIGGER IF EXISTS attendance_touch ON operational.attendance_records;
CREATE TRIGGER attendance_touch
  BEFORE UPDATE ON operational.attendance_records
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ===========================================================================
-- COURSEWORK + GRADEBOOK + RUBRICS (module: coursework, B6)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- rubrics: a named, reusable, criterion-by-criterion marking standard. The
-- criteria (id/description/max_points/weight) ride as jsonb so any rubric shape
-- fits; scoring is deterministic in app logic.
-- (mirrors modules/coursework/app/rubric.py Rubric)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.rubrics (
  rubric_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid        NOT NULL,

  name            text        NOT NULL,
  description     text        NOT NULL DEFAULT '',
  -- Ordered criteria: [{criterion_id, description, max_points, weight}, ...].
  criteria        jsonb       NOT NULL DEFAULT '[]'::jsonb,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT rubrics_criteria_is_array CHECK (jsonb_typeof(criteria) = 'array')
);
COMMENT ON TABLE operational.rubrics IS
  'Reusable, criterion-by-criterion marking standard. Deterministic scoring in '
  'app logic; the per-criterion breakdown is always preserved.';

CREATE INDEX IF NOT EXISTS rubrics_tenant_idx
  ON operational.rubrics (institution_id);

DROP TRIGGER IF EXISTS rubrics_touch ON operational.rubrics;
CREATE TRIGGER rubrics_touch
  BEFORE UPDATE ON operational.rubrics
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- assignments: coursework set against a precise ontology slice. Ontology-mapped,
-- never board-hard-coded. created_by is the opaque authoring teacher ref. Items
-- (with per-item verification for AI-generated content) ride as jsonb.
-- (mirrors modules/coursework/app/assignments.py Assignment)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.assignments (
  assignment_id   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid        NOT NULL,

  created_by      uuid        NOT NULL,   -- opaque authoring teacher ref (never PII)
  kind            text        NOT NULL,   -- quick_check | assignment | project
  title           text        NOT NULL,

  -- The primary ontology node assessed (opaque ids; no PII).
  topic_id        uuid        REFERENCES operational.ontology_topics(topic_id)
                              ON DELETE SET NULL,
  ontology        jsonb       NOT NULL DEFAULT '{}'::jsonb,  -- {topic_id,outcome_id?,competency_id?,skill_id?}
  -- Items: each references an ontology question node + carries verification when
  -- AI-generated (INVARIANT 7). Stored as jsonb so item shape can evolve.
  items           jsonb       NOT NULL DEFAULT '[]'::jsonb,
  rubric_id       uuid        REFERENCES operational.rubrics(rubric_id) ON DELETE SET NULL,

  instructions    text,
  due_at          timestamptz,
  -- Present when the assignment content was AI-generated (INVARIANT 7).
  verification    jsonb,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT assignments_kind_chk CHECK (kind IN ('quick_check','assignment','project')),
  CONSTRAINT assignments_ontology_is_object CHECK (jsonb_typeof(ontology) = 'object'),
  CONSTRAINT assignments_items_is_array CHECK (jsonb_typeof(items) = 'array')
);
COMMENT ON TABLE operational.assignments IS
  'Ontology-mapped coursework (quick_check|assignment|project). created_by is an '
  'opaque teacher ref. AI-generated content carries a verification block '
  '(INVARIANT 7). No PII.';

CREATE INDEX IF NOT EXISTS assignments_tenant_idx
  ON operational.assignments (institution_id);
CREATE INDEX IF NOT EXISTS assignments_topic_idx
  ON operational.assignments (topic_id);
CREATE INDEX IF NOT EXISTS assignments_author_idx
  ON operational.assignments (created_by);

DROP TRIGGER IF EXISTS assignments_touch ON operational.assignments;
CREATE TRIGGER assignments_touch
  BEFORE UPDATE ON operational.assignments
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- submissions: a learner's submission to an assignment. Carries the
-- independent-vs-supported flag (the keystone evidence distinction) and the
-- opaque attempt-event ids that make up the submission.
-- (mirrors contracts SubmissionCreatedPayload + assistance independent/supported)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.submissions (
  submission_id   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid        NOT NULL,

  assignment_id   uuid        NOT NULL REFERENCES operational.assignments(assignment_id)
                              ON DELETE CASCADE,
  -- Opaque submitting-learner ref ONLY. No FK to the pii_vault.
  submitted_by    uuid        NOT NULL,

  -- The keystone evidence flag: was the work done unaided, or with support?
  -- Only an independent demonstration can confirm independent mastery.
  produced_mode   text        NOT NULL DEFAULT 'independent',   -- independent | supported
  -- Opaque attempt-event ids (lineage into the immutable event store).
  attempt_ids     uuid[]      NOT NULL DEFAULT '{}',
  -- Opaque handle(s) to any scanned scripts / uploads in governed storage.
  content_refs    text[]      NOT NULL DEFAULT '{}',

  status          text        NOT NULL DEFAULT 'submitted',     -- submitted|returned|resubmitted
  submitted_at    timestamptz NOT NULL DEFAULT now(),

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT submissions_produced_mode_chk CHECK (produced_mode IN ('independent','supported')),
  CONSTRAINT submissions_status_chk CHECK (status IN ('submitted','returned','resubmitted'))
);
COMMENT ON TABLE operational.submissions IS
  'A learner submission. produced_mode is the independent-vs-supported keystone '
  'flag; only independent work can confirm independent mastery. Opaque learner '
  'ref + opaque attempt-event lineage. No PII, no raw blobs.';

CREATE INDEX IF NOT EXISTS submissions_tenant_idx
  ON operational.submissions (institution_id);
CREATE INDEX IF NOT EXISTS submissions_assignment_idx
  ON operational.submissions (assignment_id);
CREATE INDEX IF NOT EXISTS submissions_learner_idx
  ON operational.submissions (submitted_by);

DROP TRIGGER IF EXISTS submissions_touch ON operational.submissions;
CREATE TRIGGER submissions_touch
  BEFORE UPDATE ON operational.submissions
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- gradebook_scores: a recorded score against a submission. Consequential marks
-- are HUMAN-FINAL (PERMISSION LADDER): the engine recommends with a confidence
-- band; a human confirms before the mark is final. Handwriting/scan quality
-- NEVER reduces a mark (needs_human_review instead).
-- (mirrors contracts ScoreRecordedPayload + evaluation MarkingGate)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.gradebook_scores (
  score_id          uuid      PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id    uuid      NOT NULL,

  submission_id     uuid      NOT NULL REFERENCES operational.submissions(submission_id)
                              ON DELETE CASCADE,
  -- Opaque ref to the learner being scored. No FK to the pii_vault.
  scored_subject    uuid      NOT NULL,
  topic_id          uuid      REFERENCES operational.ontology_topics(topic_id)
                              ON DELETE SET NULL,
  rubric_id         uuid      REFERENCES operational.rubrics(rubric_id) ON DELETE SET NULL,

  mode              text      NOT NULL,   -- post-submission|scanned-handwriting|preventive-before-submission
  -- Normalized engine-recommended score in [0,1] + its confidence band.
  raw_score         numeric   NOT NULL,
  confidence_band   text      NOT NULL,   -- low | medium | high
  -- Per-criterion breakdown (always preserved; never an opaque single number).
  rubric_breakdown  jsonb     NOT NULL DEFAULT '[]'::jsonb,

  -- The human-final gate. A consequential mark is final ONLY when a human
  -- confirms it. needs_human_review forces a human look (low/middle band, or
  -- illegible scan — which never penalises).
  consequential     boolean   NOT NULL DEFAULT true,
  needs_human_review boolean  NOT NULL DEFAULT false,
  human_final       boolean   NOT NULL DEFAULT false,
  confirmed_by      uuid,                 -- opaque ref to the confirming human
  adjusted_score    numeric,              -- the human's adjusted score, when changed
  confirmed_at      timestamptz,

  verification      jsonb,                -- present when scoring used AI (INVARIANT 7)
  rationale         text      NOT NULL DEFAULT '',

  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT gradebook_mode_chk
    CHECK (mode IN ('post-submission','scanned-handwriting','preventive-before-submission')),
  CONSTRAINT gradebook_band_chk CHECK (confidence_band IN ('low','medium','high')),
  CONSTRAINT gradebook_raw_score_chk CHECK (raw_score >= 0 AND raw_score <= 1),
  CONSTRAINT gradebook_adjusted_score_chk
    CHECK (adjusted_score IS NULL OR (adjusted_score >= 0 AND adjusted_score <= 1)),
  CONSTRAINT gradebook_breakdown_is_array CHECK (jsonb_typeof(rubric_breakdown) = 'array'),
  -- A consequential mark cannot be final without a human confirming it.
  CONSTRAINT gradebook_human_final_gate
    CHECK (NOT (consequential AND human_final) OR confirmed_by IS NOT NULL)
);
COMMENT ON TABLE operational.gradebook_scores IS
  'Recorded scores. Consequential marks are human-final: human_final true '
  'requires confirmed_by (PERMISSION LADDER). Handwriting/scan quality never '
  'reduces a mark (sets needs_human_review). Opaque learner ref, no PII.';

CREATE INDEX IF NOT EXISTS gradebook_tenant_idx
  ON operational.gradebook_scores (institution_id);
CREATE INDEX IF NOT EXISTS gradebook_submission_idx
  ON operational.gradebook_scores (submission_id);
CREATE INDEX IF NOT EXISTS gradebook_learner_idx
  ON operational.gradebook_scores (scored_subject, topic_id);
CREATE INDEX IF NOT EXISTS gradebook_review_idx
  ON operational.gradebook_scores (institution_id, needs_human_review)
  WHERE needs_human_review = true;

DROP TRIGGER IF EXISTS gradebook_touch ON operational.gradebook_scores;
CREATE TRIGGER gradebook_touch
  BEFORE UPDATE ON operational.gradebook_scores
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ===========================================================================
-- MESSAGING (module: communication, B9) — every free-text surface is screened.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- channels: a messaging context/thread. Scoped to a tenant; opaque refs only.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.channels (
  channel_id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid        NOT NULL,

  surface         text        NOT NULL,   -- which surface/thread kind (e.g. 'parent', 'class')
  topic_label     text,                   -- generic label for the thread (no PII)
  -- Opaque participant refs (canonical_uuid) — never PII.
  participant_refs uuid[]     NOT NULL DEFAULT '{}',
  node_id         uuid        REFERENCES operational.structure_nodes(node_id)
                              ON DELETE SET NULL,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE operational.channels IS
  'A messaging context/thread. Opaque participant refs only; no PII. Every '
  'message in a channel is safety-screened on ingress (no unmonitored channel).';

CREATE INDEX IF NOT EXISTS channels_tenant_idx
  ON operational.channels (institution_id);
CREATE INDEX IF NOT EXISTS channels_node_idx
  ON operational.channels (node_id);

DROP TRIGGER IF EXISTS channels_touch ON operational.channels;
CREATE TRIGGER channels_touch
  BEFORE UPDATE ON operational.channels
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- messages: a free-text message. ALWAYS screened before admission; the safety
-- verdict travels with the row. sender_ref is an opaque canonical_uuid.
-- Cross-context routing is consent-gated (consent_ref). Body is screened text.
-- (mirrors modules/communication/app/hub.py Message)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.messages (
  message_id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid        NOT NULL,

  channel_id      uuid        REFERENCES operational.channels(channel_id) ON DELETE CASCADE,
  -- Opaque sender ref ONLY. No FK to the pii_vault.
  sender_ref      uuid        NOT NULL,
  context_ref     uuid,                   -- the thread/context this belongs to (opaque)

  body            text        NOT NULL,   -- screened free text (stays in the monitored store)

  -- Child-safety verdict attached to every message (no unmonitored channel).
  safety_verdict  jsonb       NOT NULL DEFAULT '{}'::jsonb,   -- {flagged, requires_human, ...}
  flagged         boolean     NOT NULL DEFAULT false,
  requires_human  boolean     NOT NULL DEFAULT false,
  -- Consent in force for a cross-context route (INVARIANT 6). Soft ref, no FK.
  consent_ref     uuid,

  posted_at       timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT messages_safety_verdict_is_object CHECK (jsonb_typeof(safety_verdict) = 'object')
);
COMMENT ON TABLE operational.messages IS
  'Free-text messages, ALWAYS safety-screened on ingress (safety_verdict + '
  'flagged/requires_human carried on the row). Opaque sender ref, no PII. '
  'Cross-context routing requires consent_ref (INVARIANT 6).';
COMMENT ON COLUMN operational.messages.consent_ref IS
  'platform.consents.consent_id for a consent-gated cross-context route '
  '(INVARIANT 6). Soft reference; no FK.';

CREATE INDEX IF NOT EXISTS messages_tenant_idx
  ON operational.messages (institution_id);
CREATE INDEX IF NOT EXISTS messages_channel_idx
  ON operational.messages (channel_id, posted_at);
CREATE INDEX IF NOT EXISTS messages_sender_idx
  ON operational.messages (sender_ref);
CREATE INDEX IF NOT EXISTS messages_flagged_idx
  ON operational.messages (institution_id, requires_human)
  WHERE requires_human = true;

DROP TRIGGER IF EXISTS messages_touch ON operational.messages;
CREATE TRIGGER messages_touch
  BEFORE UPDATE ON operational.messages
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- tasks: a message promoted into an owned, tracked task (message-to-task
-- routing). Has an owner (role + opaque ref), a due date, a status, and a why.
-- Advanced only by a human (permission ladder); never auto-closed.
-- (mirrors modules/communication/app/hub.py RoutedTask)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.tasks (
  task_id           uuid      PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id    uuid      NOT NULL,

  from_message_id   uuid      REFERENCES operational.messages(message_id) ON DELETE SET NULL,
  title             text      NOT NULL,   -- short, plain-language task title
  owner_role        text      NOT NULL,   -- who is responsible (a role)
  -- Opaque ref of the responsible human (the hub never creates an ownerless task).
  owner_ref         uuid      NOT NULL,
  why               text      NOT NULL DEFAULT '',   -- why this task exists (explainability)

  status            text      NOT NULL DEFAULT 'open',   -- open|in_progress|done|blocked
  due_date          date,
  -- Inherited safety escalation when the source message was flagged (the
  -- qualified human owns both the task and the escalation).
  safety_escalation jsonb,

  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT tasks_status_chk CHECK (status IN ('open','in_progress','done','blocked'))
);
COMMENT ON TABLE operational.tasks IS
  'A message routed into an owned, tracked task. Owner role + opaque owner ref, '
  'a due date, a status, a why. Advanced only by a human (permission ladder); '
  'never auto-closed. No PII.';

CREATE INDEX IF NOT EXISTS tasks_tenant_idx
  ON operational.tasks (institution_id);
CREATE INDEX IF NOT EXISTS tasks_owner_idx
  ON operational.tasks (owner_ref, status);
CREATE INDEX IF NOT EXISTS tasks_message_idx
  ON operational.tasks (from_message_id);

DROP TRIGGER IF EXISTS tasks_touch ON operational.tasks;
CREATE TRIGGER tasks_touch
  BEFORE UPDATE ON operational.tasks
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ===========================================================================
-- LEARNER RECORD (module: learner-record, B8) — evidence-linked, gated.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- profile_items: one topic on the School-facing record — independence state,
-- plain-language sentence, evidence lineage, and permission controls. There is
-- NO mastery number by design (plain language only). Every item links to
-- evidence (source_event_ids). Opaque subject + topic ids only.
-- (mirrors modules/learner-record/app/profile.py ProfileItem)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.profile_items (
  profile_item_id   uuid      PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id    uuid      NOT NULL,

  -- Opaque learner ref ONLY. No FK to the pii_vault.
  subject           uuid      NOT NULL,
  topic_id          uuid      NOT NULL REFERENCES operational.ontology_topics(topic_id)
                              ON DELETE CASCADE,

  -- The foreground read: independent vs support-dependent (never a score).
  independence      text      NOT NULL,   -- independent|support-dependent|not-started
  plain_language    text      NOT NULL,   -- learner-safe sentence, no number/percentage/formula

  -- Evidence lineage (principle 7: no item without evidence).
  source_event_ids  uuid[]    NOT NULL DEFAULT '{}',
  last_evidence_at  timestamptz,
  observation_count integer   NOT NULL DEFAULT 0,

  -- Permission controls (who consented, who can see it, why).
  consent_id        uuid,                 -- soft ref to platform.consents; no FK
  visible_to        uuid[]    NOT NULL DEFAULT '{}',   -- opaque viewer ids in the audience
  learner_controlled boolean  NOT NULL DEFAULT true,
  why_visible       text      NOT NULL DEFAULT '',
  -- Plain-language gap notes with lineage (never a number).
  gaps              jsonb     NOT NULL DEFAULT '[]'::jsonb,

  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT profile_items_independence_chk
    CHECK (independence IN ('independent','support-dependent','not-started')),
  CONSTRAINT profile_items_gaps_is_array CHECK (jsonb_typeof(gaps) = 'array'),
  -- Evidence over assertion: an item must link to at least one source event,
  -- unless it is a not-started placeholder (no evidence yet by definition).
  CONSTRAINT profile_items_evidence_required
    CHECK (independence = 'not-started' OR cardinality(source_event_ids) > 0)
);
COMMENT ON TABLE operational.profile_items IS
  'School-facing learner record items: independence state + plain language + '
  'evidence lineage + permission controls. NO mastery number by design. Opaque '
  'subject/topic refs, no PII.';

CREATE INDEX IF NOT EXISTS profile_items_tenant_idx
  ON operational.profile_items (institution_id);
CREATE INDEX IF NOT EXISTS profile_items_subject_idx
  ON operational.profile_items (subject, topic_id);
-- One current item per (subject, topic).
CREATE UNIQUE INDEX IF NOT EXISTS profile_items_subject_topic_uidx
  ON operational.profile_items (subject, topic_id);

DROP TRIGGER IF EXISTS profile_items_touch ON operational.profile_items;
CREATE TRIGGER profile_items_touch
  BEFORE UPDATE ON operational.profile_items
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- portfolio_items: a learner-curated artifact with provenance and the
-- independent-vs-supported produced mode. An artifact with no provenance cannot
-- exist. content_ref is an opaque handle into governed storage, never a blob.
-- (mirrors modules/learner-record/app/portfolio.py Artifact)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.portfolio_items (
  artifact_id       uuid      PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id    uuid      NOT NULL,

  -- Opaque owner ref ONLY. No FK to the pii_vault.
  subject           uuid      NOT NULL,
  topic_id          uuid      REFERENCES operational.ontology_topics(topic_id)
                              ON DELETE SET NULL,

  title             text      NOT NULL,
  caption           text      NOT NULL DEFAULT '',   -- learner-facing, no raw score
  content_ref       text      NOT NULL,              -- opaque handle into governed storage

  -- Provenance: how it was produced + its evidence lineage.
  produced_mode     text      NOT NULL,   -- independent | supported
  source_event_ids  uuid[]    NOT NULL DEFAULT '{}',
  produced_at       timestamptz,
  featured          boolean   NOT NULL DEFAULT false,

  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT portfolio_produced_mode_chk CHECK (produced_mode IN ('independent','supported')),
  -- Evidence over assertion: an artifact must carry provenance.
  CONSTRAINT portfolio_provenance_required CHECK (cardinality(source_event_ids) > 0)
);
COMMENT ON TABLE operational.portfolio_items IS
  'Learner-curated portfolio artifacts with provenance (source events + '
  'produced_mode). content_ref is an opaque governed-storage handle, never a '
  'blob. Opaque owner ref, no PII.';

CREATE INDEX IF NOT EXISTS portfolio_items_tenant_idx
  ON operational.portfolio_items (institution_id);
CREATE INDEX IF NOT EXISTS portfolio_items_subject_idx
  ON operational.portfolio_items (subject);
CREATE INDEX IF NOT EXISTS portfolio_items_featured_idx
  ON operational.portfolio_items (subject, featured)
  WHERE featured = true;

DROP TRIGGER IF EXISTS portfolio_items_touch ON operational.portfolio_items;
CREATE TRIGGER portfolio_items_touch
  BEFORE UPDATE ON operational.portfolio_items
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- credentials: verifiable, portable attestations under the learner's control.
-- State: draft (no signing key -> NOT verifiable) | verified (signed) | revoked.
-- Evidence-linked (source_event_ids). PII-free: opaque subject + topic ids and
-- a plain-language statement (no raw score). We never fake a signature.
-- (mirrors modules/learner-record/app/credentials.py Credential)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.credentials (
  credential_id     uuid      PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id    uuid      NOT NULL,

  -- Opaque holder ref ONLY. No FK to the pii_vault.
  subject           uuid      NOT NULL,

  -- The claim (PII-free, plain language).
  claim_kind        text      NOT NULL,   -- independent-mastery|course-completion|skill-badge
  topic_id          uuid      REFERENCES operational.ontology_topics(topic_id)
                              ON DELETE SET NULL,
  statement         text      NOT NULL,   -- plain language, no raw score
  source_event_ids  uuid[]    NOT NULL DEFAULT '{}',   -- evidence lineage

  -- Lifecycle + verifiability.
  state             text      NOT NULL DEFAULT 'draft',  -- draft|verified|revoked
  issuer            text      NOT NULL DEFAULT 'classess-school',
  signature         text,                 -- present only in the verified state
  issued_at         timestamptz NOT NULL DEFAULT now(),
  expires_at        timestamptz,

  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT credentials_claim_kind_chk
    CHECK (claim_kind IN ('independent-mastery','course-completion','skill-badge')),
  CONSTRAINT credentials_state_chk CHECK (state IN ('draft','verified','revoked')),
  -- Evidence over assertion: a credential is backed by evidence.
  CONSTRAINT credentials_evidence_required CHECK (cardinality(source_event_ids) > 0),
  -- Never fake a signature: a verified credential must carry one; a draft must not.
  CONSTRAINT credentials_verified_signed
    CHECK ((state = 'verified' AND signature IS NOT NULL)
           OR (state <> 'verified' AND signature IS NULL))
);
COMMENT ON TABLE operational.credentials IS
  'Verifiable, portable, learner-controlled credentials. draft (no signature, '
  'not verifiable) | verified (signed) | revoked. Evidence-linked, PII-free '
  '(opaque subject/topic ids, plain-language statement). Signatures never faked.';

CREATE INDEX IF NOT EXISTS credentials_tenant_idx
  ON operational.credentials (institution_id);
CREATE INDEX IF NOT EXISTS credentials_subject_idx
  ON operational.credentials (subject, state);

DROP TRIGGER IF EXISTS credentials_touch ON operational.credentials;
CREATE TRIGGER credentials_touch
  BEFORE UPDATE ON operational.credentials
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ===========================================================================
-- TIMETABLE (module: scheduling, B2) — board-agnostic, opaque refs only.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- calendars: the academic calendar for a tenant — terms, working-week pattern,
-- and dated exceptions. Board-agnostic; keyed by opaque institution_id only.
-- (mirrors modules/scheduling/app/calendar.py AcademicCalendar)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.calendars (
  calendar_id       uuid      PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id    uuid      NOT NULL,

  label             text      NOT NULL,   -- generic, e.g. 'Academic Year 2026-27'
  -- Instructional weekdays (0=Mon..6=Sun). No fixed week assumed.
  working_weekdays  integer[] NOT NULL DEFAULT '{0,1,2,3,4}',
  -- Terms: [{term_id,label,start,end}, ...] (inclusive start/end).
  terms             jsonb     NOT NULL DEFAULT '[]'::jsonb,
  -- Dated exceptions: [{day,kind,label}] kind in holiday|non_working|working_override.
  exceptions        jsonb     NOT NULL DEFAULT '[]'::jsonb,

  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT calendars_terms_is_array CHECK (jsonb_typeof(terms) = 'array'),
  CONSTRAINT calendars_exceptions_is_array CHECK (jsonb_typeof(exceptions) = 'array')
);
COMMENT ON TABLE operational.calendars IS
  'Board-agnostic academic calendar: terms, working-week pattern, dated '
  'exceptions. Keyed by opaque institution_id; no PII, no board lock-in.';

CREATE INDEX IF NOT EXISTS calendars_tenant_idx
  ON operational.calendars (institution_id);

DROP TRIGGER IF EXISTS calendars_touch ON operational.calendars;
CREATE TRIGGER calendars_touch
  BEFORE UPDATE ON operational.calendars
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- timetable_slots: one scheduled period — a section, a weekday+period slot, a
-- subject, an (opaque) teacher, and an optional room. The live timetable; only
-- mutated by an approved change (substitutions reference it).
-- (mirrors modules/scheduling/app/timetable.py Period)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.timetable_slots (
  slot_id           uuid      PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id    uuid      NOT NULL,

  -- The section this period is for (a structure node).
  node_id           uuid      REFERENCES operational.structure_nodes(node_id)
                              ON DELETE CASCADE,
  section_label     text,                 -- generic label cache (no PII)

  weekday           integer   NOT NULL,   -- 0 (Mon) .. 6 (Sun)
  period            integer   NOT NULL,   -- 1-based period number within the day

  subject_id        uuid      REFERENCES operational.ontology_subjects(subject_id)
                              ON DELETE SET NULL,
  -- Opaque ref of the assigned teacher (never PII).
  teacher_ref       uuid,
  room_id           text,                 -- opaque/generic room handle

  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT timetable_slots_weekday_chk CHECK (weekday >= 0 AND weekday <= 6),
  CONSTRAINT timetable_slots_period_chk CHECK (period >= 1)
);
COMMENT ON TABLE operational.timetable_slots IS
  'The live timetable: one scheduled period (section + weekday/period slot + '
  'subject + opaque teacher + optional room). Mutated only by an approved '
  'change. No PII.';

CREATE INDEX IF NOT EXISTS timetable_slots_tenant_idx
  ON operational.timetable_slots (institution_id);
CREATE INDEX IF NOT EXISTS timetable_slots_node_slot_idx
  ON operational.timetable_slots (node_id, weekday, period);
CREATE INDEX IF NOT EXISTS timetable_slots_teacher_idx
  ON operational.timetable_slots (teacher_ref, weekday, period);

DROP TRIGGER IF EXISTS timetable_slots_touch ON operational.timetable_slots;
CREATE TRIGGER timetable_slots_touch
  BEFORE UPDATE ON operational.timetable_slots
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- substitutions: an approved cover for a vacated period (the substitution
-- ladder Level 1-6, never a free period). Assigning is consequential and
-- human-gated: approved_by is the opaque approver ref. Records what the human
-- approved, against a slot, on a date.
-- (mirrors modules/scheduling/app/substitution.py SubstituteOption)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.substitutions (
  substitution_id   uuid      PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id    uuid      NOT NULL,

  slot_id           uuid      NOT NULL REFERENCES operational.timetable_slots(slot_id)
                              ON DELETE CASCADE,
  on_date           date      NOT NULL,

  -- The cover. Opaque refs only. substitute_ref may be NULL only for a
  -- supervised study-room combine with no single named teacher (still supervised).
  absent_teacher_ref uuid,
  substitute_ref     uuid,
  level             integer   NOT NULL,   -- substitution ladder level 1..6 (1 = best)

  -- Human gate: assigning a substitute is consequential and never auto-fires.
  approved_by       uuid,                 -- opaque approver ref; NULL while only proposed
  approved_at       timestamptz,
  why               text      NOT NULL DEFAULT '',   -- explainability
  notes             jsonb     NOT NULL DEFAULT '[]'::jsonb,

  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT substitutions_level_chk CHECK (level >= 1 AND level <= 6),
  CONSTRAINT substitutions_notes_is_array CHECK (jsonb_typeof(notes) = 'array'),
  -- Coverage is guaranteed: a confirmed substitution names a substitute unless
  -- it is the Level 6 supervised combine (which is still supervised, never free).
  CONSTRAINT substitutions_never_free_period
    CHECK (substitute_ref IS NOT NULL OR level = 6)
);
COMMENT ON TABLE operational.substitutions IS
  'Approved cover for a vacated period (ladder level 1-6, never a free period). '
  'Assigning is consequential and human-gated (approved_by). Opaque refs only, '
  'no PII. substitute_ref NULL only for the Level 6 supervised combine.';

CREATE INDEX IF NOT EXISTS substitutions_tenant_idx
  ON operational.substitutions (institution_id);
CREATE INDEX IF NOT EXISTS substitutions_slot_date_idx
  ON operational.substitutions (slot_id, on_date);
CREATE INDEX IF NOT EXISTS substitutions_substitute_idx
  ON operational.substitutions (substitute_ref, on_date);

DROP TRIGGER IF EXISTS substitutions_touch ON operational.substitutions;
CREATE TRIGGER substitutions_touch
  BEFORE UPDATE ON operational.substitutions
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();
