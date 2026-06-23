import { describe, it, expect } from 'vitest';
import * as contracts from '../index.js';
import {
  SEED_ONTOLOGY,
  SEED_ONTOLOGY_STATE,
  SEED_ONTOLOGIES,
} from '../ontology/seed.js';
import { OntologySnapshot } from '../ontology/types.js';
import { GAP_TYPES } from '../events/gaps.js';

describe('event/evidence contract', () => {
  it('defines exactly the ten gap types', () => {
    expect(GAP_TYPES).toHaveLength(10);
    expect(new Set(GAP_TYPES).size).toBe(10);
    expect(GAP_TYPES).toContain('prerequisite');
    expect(GAP_TYPES).toContain('support-dependency');
  });

  it('exposes the contract surface from the barrel', () => {
    expect(contracts).toBeTypeOf('object');
    expect(contracts.tokens).toBeDefined();
  });
});

describe('ontology seed — one board, one grade, two subjects', () => {
  it('validates against the OntologySnapshot schema', () => {
    expect(() => OntologySnapshot.parse(SEED_ONTOLOGY)).not.toThrow();
  });

  it('covers two subjects with a real topic graph', () => {
    expect(SEED_ONTOLOGY.subjects.length).toBeGreaterThanOrEqual(2);
    expect(SEED_ONTOLOGY.topics.length).toBeGreaterThanOrEqual(6);
  });

  it('has prerequisite edges that reference real topics, with no self-loops', () => {
    const topicIds = new Set(SEED_ONTOLOGY.topics.map((t) => t.id));
    expect(SEED_ONTOLOGY.edges.length).toBeGreaterThan(0);
    for (const edge of SEED_ONTOLOGY.edges) {
      expect(topicIds.has(edge.from_topic_id)).toBe(true);
      expect(topicIds.has(edge.to_topic_id)).toBe(true);
      expect(edge.from_topic_id).not.toBe(edge.to_topic_id);
    }
  });

  it('attaches every outcome to a real topic', () => {
    const topicIds = new Set(SEED_ONTOLOGY.topics.map((t) => t.id));
    for (const outcome of SEED_ONTOLOGY.outcomes) {
      expect(topicIds.has(outcome.topic_id)).toBe(true);
    }
  });
});

describe('ontology seed — rich, board-agnostic graph', () => {
  it('both board snapshots validate against the schema', () => {
    expect(() => OntologySnapshot.parse(SEED_ONTOLOGY)).not.toThrow();
    expect(() => OntologySnapshot.parse(SEED_ONTOLOGY_STATE)).not.toThrow();
    expect(SEED_ONTOLOGIES).toHaveLength(2);
  });

  it('models two distinct, neutrally-named boards (no real board lock-in)', () => {
    const codes = SEED_ONTOLOGIES.map((s) => s.board.code);
    expect(new Set(codes).size).toBe(2);
    for (const snap of SEED_ONTOLOGIES) {
      // Neutral example boards only — guard against accidental real-board lock-in.
      expect(snap.board.name.toLowerCase()).toContain('example');
    }
  });

  it('covers grades 9 and 10 on each board', () => {
    for (const snap of SEED_ONTOLOGIES) {
      const levels = new Set(snap.grades.map((g) => g.level));
      expect(levels.has(9)).toBe(true);
      expect(levels.has(10)).toBe(true);
    }
  });

  it('covers at least six subjects per grade on each board', () => {
    const expected = [
      'Mathematics',
      'Physics',
      'Chemistry',
      'Biology',
      'English',
      'Social Science',
    ];
    for (const snap of SEED_ONTOLOGIES) {
      for (const grade of snap.grades) {
        const names = snap.subjects
          .filter((s) => s.grade_id === grade.id)
          .map((s) => s.name);
        expect(names.length).toBeGreaterThanOrEqual(6);
        for (const subject of expected) {
          expect(names).toContain(subject);
        }
      }
    }
  });

  it('keeps the full tree referentially intact (no dangling parents)', () => {
    for (const snap of SEED_ONTOLOGIES) {
      const gradeIds = new Set(snap.grades.map((g) => g.id));
      const subjectIds = new Set(snap.subjects.map((s) => s.id));
      const unitIds = new Set(snap.units.map((u) => u.id));
      const chapterIds = new Set(snap.chapters.map((c) => c.id));
      const topicIds = new Set(snap.topics.map((t) => t.id));

      for (const g of snap.grades) expect(g.board_id).toBe(snap.board.id);
      for (const s of snap.subjects) expect(gradeIds.has(s.grade_id)).toBe(true);
      for (const u of snap.units) expect(subjectIds.has(u.subject_id)).toBe(true);
      for (const c of snap.chapters) expect(unitIds.has(c.unit_id)).toBe(true);
      for (const t of snap.topics) expect(chapterIds.has(t.chapter_id)).toBe(true);
      for (const o of snap.outcomes) expect(topicIds.has(o.topic_id)).toBe(true);
      for (const c of snap.competencies) {
        expect(subjectIds.has(c.subject_id)).toBe(true);
        const outcomeIds = new Set(snap.outcomes.map((o) => o.id));
        for (const oid of c.outcome_ids) expect(outcomeIds.has(oid)).toBe(true);
      }
    }
  });

  it('has prerequisite edges between real topics, with no dangling endpoints or self-loops', () => {
    for (const snap of SEED_ONTOLOGIES) {
      const topicIds = new Set(snap.topics.map((t) => t.id));
      expect(snap.edges.length).toBeGreaterThan(0);
      for (const edge of snap.edges) {
        expect(topicIds.has(edge.from_topic_id)).toBe(true);
        expect(topicIds.has(edge.to_topic_id)).toBe(true);
        expect(edge.from_topic_id).not.toBe(edge.to_topic_id);
      }
    }
  });

  it('includes cross-grade prerequisite edges (Class 9 secures Class 10)', () => {
    for (const snap of SEED_ONTOLOGIES) {
      const grade9 = snap.grades.find((g) => g.level === 9)!;
      const grade10 = snap.grades.find((g) => g.level === 10)!;

      // Build topic id -> grade id, walking topic -> chapter -> unit -> subject -> grade.
      const subjectGrade = new Map(snap.subjects.map((s) => [s.id, s.grade_id]));
      const unitGrade = new Map(snap.units.map((u) => [u.id, subjectGrade.get(u.subject_id)!]));
      const chapterGrade = new Map(snap.chapters.map((c) => [c.id, unitGrade.get(c.unit_id)!]));
      const topicGrade = new Map(snap.topics.map((t) => [t.id, chapterGrade.get(t.chapter_id)!]));

      const crossGrade = snap.edges.filter(
        (e) =>
          topicGrade.get(e.from_topic_id) === grade9.id &&
          topicGrade.get(e.to_topic_id) === grade10.id,
      );
      expect(crossGrade.length).toBeGreaterThan(0);
    }
  });

  it('exercises cross-board equivalences that resolve to real topics in the other board', () => {
    const byCode = new Map(SEED_ONTOLOGIES.map((s) => [s.board.code, s]));

    for (const snap of SEED_ONTOLOGIES) {
      const ownTopicIds = new Set(snap.topics.map((t) => t.id));
      expect(snap.equivalences.length).toBeGreaterThan(0);

      for (const eq of snap.equivalences) {
        // Source node belongs to this board.
        expect(ownTopicIds.has(eq.node_id)).toBe(true);
        // Target board is a different, known board (no self-equivalence).
        expect(eq.equivalent_board_code).not.toBe(snap.board.code);
        const other = byCode.get(eq.equivalent_board_code);
        expect(other).toBeDefined();
        // The equivalent node id resolves to a REAL topic in the other board.
        expect(eq.equivalent_node_id).toBeDefined();
        const otherTopicIds = new Set(other!.topics.map((t) => t.id));
        expect(otherTopicIds.has(eq.equivalent_node_id!)).toBe(true);
      }
    }
  });
});
