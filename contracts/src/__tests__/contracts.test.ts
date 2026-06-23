import { describe, it, expect } from 'vitest';
import * as contracts from '../index.js';
import { SEED_ONTOLOGY } from '../ontology/seed.js';
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
