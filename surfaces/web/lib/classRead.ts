/* ============================================================================
   lib/classRead.ts — derived class reads for the Teacher surface.

   Replays the seed events through lib/engine.ts to produce per-student,
   per-topic mastery + gaps, then rolls them up into the lists the teacher day
   and student-insights pages render. PURE over the event log; deterministic.

   Confidentiality: works only over opaque canonical refs and generic labels.
   ============================================================================ */

import {
  computeMastery,
  detectGaps,
  topicsWithEvidence,
  type EngineEvent,
  type GapResult,
  type MasteryResult,
} from './engine';
import {
  EDGES,
  ROSTER,
  SCENARIO_NOW,
  SEED_EVENTS,
  studentLabel,
  topicInfo,
  type TopicInfo,
} from './loopData';

export interface StudentTopicRead {
  studentRef: string;
  studentLabel: string;
  topic: TopicInfo;
  mastery: MasteryResult;
  gaps: GapResult[];
  confirmedGaps: GapResult[];
}

/**
 * Every (student, touched-topic) read in the class, computed live. The single
 * source the teacher pages roll up from.
 */
export function computeClassReads(
  events: EngineEvent[] = SEED_EVENTS,
  asof: number = SCENARIO_NOW,
): StudentTopicRead[] {
  const reads: StudentTopicRead[] = [];
  for (const student of ROSTER) {
    const topics = topicsWithEvidence(events, student.ref);
    for (const topicId of topics) {
      const mastery = computeMastery(events, student.ref, topicId, asof);
      const gaps = detectGaps(events, student.ref, topicId, EDGES, asof, undefined, mastery);
      reads.push({
        studentRef: student.ref,
        studentLabel: studentLabel(student.ref),
        topic: topicInfo(topicId),
        mastery,
        gaps,
        confirmedGaps: gaps.filter((g) => g.evidence.confirmed),
      });
    }
  }
  return reads;
}

/** Students with at least one confirmed gap — the "needing attention" list. */
export function studentsNeedingAttention(reads: StudentTopicRead[]): StudentTopicRead[] {
  return reads
    .filter((r) => r.confirmedGaps.length > 0)
    .sort((a, b) => b.confirmedGaps[0]!.evidence.confidence - a.confirmedGaps[0]!.evidence.confidence);
}

/** Class-level plain-language counts (never a formula). */
export interface ClassSummary {
  working_independently: number;
  need_support: number;
  revision_due: number;
  confirmed_gaps: number;
}

export function summariseClass(reads: StudentTopicRead[]): ClassSummary {
  let independent = 0;
  let support = 0;
  let revision = 0;
  let gaps = 0;
  for (const r of reads) {
    if (r.mastery.reading.independent) independent += 1;
    else support += 1;
    if (r.mastery.revisionDue) revision += 1;
    gaps += r.confirmedGaps.length;
  }
  return {
    working_independently: independent,
    need_support: support,
    revision_due: revision,
    confirmed_gaps: gaps,
  };
}
