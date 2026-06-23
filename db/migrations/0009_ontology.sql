-- =============================================================================
-- 0009_ontology.sql
-- The board-agnostic academic ontology (module: ontology-ingestion / content).
--
-- Graph: Board -> Grade -> Subject -> Unit -> Chapter -> Topic -> Outcome ->
-- Competency, plus prerequisite Edges (topic -> topic, OWNED + expert-validated)
-- and cross-board equivalences. Mirrors contracts/src/ontology/types.ts.
--
-- The board is a FIELD on the tree, never a baked-in enum of permitted boards.
-- Ontology nodes carry NO PII and reference one another by opaque id. A
-- pgvector embedding column rides on topics (and on content in 0010) for
-- semantic routing / search.
--
-- Tenancy: ingested curriculum may be platform-shared OR institution-scoped.
-- institution_id is NULLABLE here: NULL = a platform-shared canonical ontology
-- usable by every tenant; a non-NULL value scopes a private/extended ontology
-- to one institution (INVARIANT 10). Every other operational table keeps
-- institution_id NOT NULL; ontology is the deliberate shared-catalog exception.
--
-- Idempotent.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- ontology_boards: a labelled board node. Board-agnostic: a row, not an enum.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.ontology_boards (
  board_id        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid,                    -- NULL = platform-shared; else tenant-scoped

  code            text        NOT NULL,    -- short stable handle, e.g. 'example-state-board'
  name            text        NOT NULL,    -- display name (a field, never the only option)
  region          text,                    -- optional jurisdiction/region the board governs

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE operational.ontology_boards IS
  'A labelled board node. Board-agnostic by construction (a row, never an enum '
  'of permitted boards). institution_id NULL = platform-shared canonical ontology.';

CREATE INDEX IF NOT EXISTS ontology_boards_tenant_idx
  ON operational.ontology_boards (institution_id);
CREATE INDEX IF NOT EXISTS ontology_boards_code_idx
  ON operational.ontology_boards (code);

DROP TRIGGER IF EXISTS ontology_boards_touch ON operational.ontology_boards;
CREATE TRIGGER ontology_boards_touch
  BEFORE UPDATE ON operational.ontology_boards
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- ontology_grades: a grade/standard within a board.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.ontology_grades (
  grade_id        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid,
  board_id        uuid        NOT NULL REFERENCES operational.ontology_boards(board_id)
                              ON DELETE CASCADE,

  level           integer     NOT NULL,    -- numeric standard, e.g. 10
  name            text        NOT NULL,    -- display name, e.g. 'Class 10'

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE operational.ontology_grades IS 'A grade/standard within a board.';

CREATE INDEX IF NOT EXISTS ontology_grades_board_idx
  ON operational.ontology_grades (board_id);
CREATE INDEX IF NOT EXISTS ontology_grades_tenant_idx
  ON operational.ontology_grades (institution_id);

DROP TRIGGER IF EXISTS ontology_grades_touch ON operational.ontology_grades;
CREATE TRIGGER ontology_grades_touch
  BEFORE UPDATE ON operational.ontology_grades
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- ontology_subjects: a subject within a grade.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.ontology_subjects (
  subject_id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid,
  grade_id        uuid        NOT NULL REFERENCES operational.ontology_grades(grade_id)
                              ON DELETE CASCADE,

  name            text        NOT NULL,    -- e.g. 'Mathematics', 'Physics'

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE operational.ontology_subjects IS 'A subject within a grade.';

CREATE INDEX IF NOT EXISTS ontology_subjects_grade_idx
  ON operational.ontology_subjects (grade_id);
CREATE INDEX IF NOT EXISTS ontology_subjects_tenant_idx
  ON operational.ontology_subjects (institution_id);

DROP TRIGGER IF EXISTS ontology_subjects_touch ON operational.ontology_subjects;
CREATE TRIGGER ontology_subjects_touch
  BEFORE UPDATE ON operational.ontology_subjects
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- ontology_units: a unit within a subject, ordered by sequence.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.ontology_units (
  unit_id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid,
  subject_id      uuid        NOT NULL REFERENCES operational.ontology_subjects(subject_id)
                              ON DELETE CASCADE,

  name            text        NOT NULL,
  sequence        integer     NOT NULL DEFAULT 0,    -- ordering within the subject

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT ontology_units_sequence_nonneg CHECK (sequence >= 0)
);
COMMENT ON TABLE operational.ontology_units IS 'A unit within a subject.';

CREATE INDEX IF NOT EXISTS ontology_units_subject_idx
  ON operational.ontology_units (subject_id, sequence);
CREATE INDEX IF NOT EXISTS ontology_units_tenant_idx
  ON operational.ontology_units (institution_id);

DROP TRIGGER IF EXISTS ontology_units_touch ON operational.ontology_units;
CREATE TRIGGER ontology_units_touch
  BEFORE UPDATE ON operational.ontology_units
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- ontology_chapters: a chapter within a unit, ordered by sequence.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.ontology_chapters (
  chapter_id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid,
  unit_id         uuid        NOT NULL REFERENCES operational.ontology_units(unit_id)
                              ON DELETE CASCADE,

  name            text        NOT NULL,
  sequence        integer     NOT NULL DEFAULT 0,    -- ordering within the unit

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT ontology_chapters_sequence_nonneg CHECK (sequence >= 0)
);
COMMENT ON TABLE operational.ontology_chapters IS 'A chapter within a unit.';

CREATE INDEX IF NOT EXISTS ontology_chapters_unit_idx
  ON operational.ontology_chapters (unit_id, sequence);
CREATE INDEX IF NOT EXISTS ontology_chapters_tenant_idx
  ON operational.ontology_chapters (institution_id);

DROP TRIGGER IF EXISTS ontology_chapters_touch ON operational.ontology_chapters;
CREATE TRIGGER ontology_chapters_touch
  BEFORE UPDATE ON operational.ontology_chapters
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- ontology_topics: the grain attempts/mastery are usually keyed to. Carries a
-- pgvector embedding for semantic routing (nearest topics, content matching).
-- The embedding is nullable: a topic exists before it is embedded.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.ontology_topics (
  topic_id        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid,
  chapter_id      uuid        NOT NULL REFERENCES operational.ontology_chapters(chapter_id)
                              ON DELETE CASCADE,

  name            text        NOT NULL,
  sequence        integer     NOT NULL DEFAULT 0,    -- ordering within the chapter

  -- pgvector embedding for semantic search / nearest-topic routing. Dimension
  -- is left unspecified so any embedder fits; index is added by ops once a
  -- fixed dimension is chosen (an ivfflat/hnsw index needs a typed dimension).
  embedding       vector,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT ontology_topics_sequence_nonneg CHECK (sequence >= 0)
);
COMMENT ON TABLE operational.ontology_topics IS
  'A topic — the grain attempts and mastery readings key to. Carries an '
  'optional pgvector embedding for semantic routing/search.';
COMMENT ON COLUMN operational.ontology_topics.embedding IS
  'pgvector embedding for semantic search. Dimension chosen at ingest time; '
  'an ANN index (ivfflat/hnsw) is added by ops once the dimension is fixed.';

CREATE INDEX IF NOT EXISTS ontology_topics_chapter_idx
  ON operational.ontology_topics (chapter_id, sequence);
CREATE INDEX IF NOT EXISTS ontology_topics_tenant_idx
  ON operational.ontology_topics (institution_id);

DROP TRIGGER IF EXISTS ontology_topics_touch ON operational.ontology_topics;
CREATE TRIGGER ontology_topics_touch
  BEFORE UPDATE ON operational.ontology_topics
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- ontology_outcomes: a verifiable can-do statement under a topic.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.ontology_outcomes (
  outcome_id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid,
  topic_id        uuid        NOT NULL REFERENCES operational.ontology_topics(topic_id)
                              ON DELETE CASCADE,

  statement       text        NOT NULL,    -- observable can-do statement

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE operational.ontology_outcomes IS
  'A learning outcome — an observable can-do statement under a topic.';

CREATE INDEX IF NOT EXISTS ontology_outcomes_topic_idx
  ON operational.ontology_outcomes (topic_id);
CREATE INDEX IF NOT EXISTS ontology_outcomes_tenant_idx
  ON operational.ontology_outcomes (institution_id);

DROP TRIGGER IF EXISTS ontology_outcomes_touch ON operational.ontology_outcomes;
CREATE TRIGGER ontology_outcomes_touch
  BEFORE UPDATE ON operational.ontology_outcomes
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- ontology_competencies: a broader capability several outcomes roll up into,
-- crossing topics within a subject. outcome_ids is the contributing-outcome set.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.ontology_competencies (
  competency_id   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid,
  subject_id      uuid        NOT NULL REFERENCES operational.ontology_subjects(subject_id)
                              ON DELETE CASCADE,

  name            text        NOT NULL,
  statement       text        NOT NULL,    -- what the learner can durably do across topics
  -- Opaque outcome ids that contribute evidence to this competency.
  outcome_ids     uuid[]      NOT NULL DEFAULT '{}',

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE operational.ontology_competencies IS
  'A competency — a broader capability several outcomes roll up into, across '
  'topics within a subject.';

CREATE INDEX IF NOT EXISTS ontology_competencies_subject_idx
  ON operational.ontology_competencies (subject_id);
CREATE INDEX IF NOT EXISTS ontology_competencies_tenant_idx
  ON operational.ontology_competencies (institution_id);

DROP TRIGGER IF EXISTS ontology_competencies_touch ON operational.ontology_competencies;
CREATE TRIGGER ontology_competencies_touch
  BEFORE UPDATE ON operational.ontology_competencies
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- prerequisite_edges: topic -> topic, an OWNED, expert-validated artifact.
-- `confirmed` is false until a steward validates it (A2); only confirmed edges
-- are trusted for routing. `kind` is hard (blocked) or soft (eased).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.prerequisite_edges (
  edge_id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id  uuid,

  from_topic_id   uuid        NOT NULL REFERENCES operational.ontology_topics(topic_id)
                              ON DELETE CASCADE,    -- prerequisite (secure first)
  to_topic_id     uuid        NOT NULL REFERENCES operational.ontology_topics(topic_id)
                              ON DELETE CASCADE,    -- dependent topic

  kind            text        NOT NULL,    -- 'hard' (blocked) | 'soft' (eased)
  -- True only once a human steward has validated the edge. Proposed edges are
  -- never trusted for routing.
  confirmed       boolean     NOT NULL DEFAULT false,
  rationale       text        NOT NULL DEFAULT '',  -- plain-language why, for explainability
  -- Opaque ref to the steward who confirmed (set with confirmed). Never PII.
  confirmed_by    uuid,
  confirmed_at    timestamptz,

  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT prerequisite_edges_kind_chk CHECK (kind IN ('hard','soft')),
  CONSTRAINT prerequisite_edges_distinct CHECK (from_topic_id <> to_topic_id),
  CONSTRAINT prerequisite_edges_confirm_attribution
    CHECK (confirmed = false OR confirmed_by IS NOT NULL)
);
COMMENT ON TABLE operational.prerequisite_edges IS
  'Prerequisite edge topic->topic. OWNED, expert-validated: confirmed is false '
  'until a steward validates it; only confirmed edges are trusted for routing.';

CREATE UNIQUE INDEX IF NOT EXISTS prerequisite_edges_pair_uidx
  ON operational.prerequisite_edges (from_topic_id, to_topic_id);
CREATE INDEX IF NOT EXISTS prerequisite_edges_to_idx
  ON operational.prerequisite_edges (to_topic_id, confirmed);
CREATE INDEX IF NOT EXISTS prerequisite_edges_tenant_idx
  ON operational.prerequisite_edges (institution_id);

DROP TRIGGER IF EXISTS prerequisite_edges_touch ON operational.prerequisite_edges;
CREATE TRIGGER prerequisite_edges_touch
  BEFORE UPDATE ON operational.prerequisite_edges
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();

-- ---------------------------------------------------------------------------
-- cross_board_equivalences: map a node in this ontology to the conceptually
-- equivalent node in another board's ontology — so evidence travels across
-- boards without hard-coding any board. confidence in [0,1].
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operational.cross_board_equivalences (
  equivalence_id        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_id        uuid,

  -- The node in THIS ontology (opaque id) and its kind.
  node_id               uuid        NOT NULL,
  node_kind             text        NOT NULL,    -- board|grade|subject|unit|chapter|topic|outcome|competency

  -- The other board (a label, not an enum) and its matching node, when known.
  equivalent_board_code text        NOT NULL,
  equivalent_node_id    uuid,
  equivalent_label      text        NOT NULL,    -- human-readable label of the equivalent node
  confidence            numeric     NOT NULL,    -- how strong the equivalence is, in [0,1]

  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT cross_board_equivalences_node_kind_chk
    CHECK (node_kind IN ('board','grade','subject','unit','chapter','topic','outcome','competency')),
  CONSTRAINT cross_board_equivalences_confidence_chk
    CHECK (confidence >= 0 AND confidence <= 1)
);
COMMENT ON TABLE operational.cross_board_equivalences IS
  'Cross-board equivalence: maps a node here to the conceptually equivalent '
  'node in another board (a label, not an enum). Lets evidence travel across '
  'boards with no board lock-in.';

CREATE INDEX IF NOT EXISTS cross_board_equivalences_node_idx
  ON operational.cross_board_equivalences (node_id, node_kind);
CREATE INDEX IF NOT EXISTS cross_board_equivalences_board_idx
  ON operational.cross_board_equivalences (equivalent_board_code);
CREATE INDEX IF NOT EXISTS cross_board_equivalences_tenant_idx
  ON operational.cross_board_equivalences (institution_id);

DROP TRIGGER IF EXISTS cross_board_equivalences_touch ON operational.cross_board_equivalences;
CREATE TRIGGER cross_board_equivalences_touch
  BEFORE UPDATE ON operational.cross_board_equivalences
  FOR EACH ROW EXECUTE FUNCTION operational.touch_updated_at();
