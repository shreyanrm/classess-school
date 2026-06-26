/* ============================================================================
   lib/courseData.ts — the hierarchical COURSE tree the student course browser
   rides on: subject → term / periodic → chapter → topic, derived from the SAME
   SEED_ONTOLOGY every other surface reads, so the browser is never a parallel
   hardcoded list.

   Mapping the seed to the v2 course-flow shape:
     · subject  → the seed Subject (Mathematics, Physics) for the current grade.
     · term     → the seed Unit (a unit is the periodic/term band in the catalogue).
     · chapter  → the seed Chapter.
     · topic    → the seed Topic (the leaf the learner opens).

   Each topic carries its sub-lesson TYPES — the three ways into it, matching the
   v2 "Teacher-Shared-Material / Learn / Practice" set:
     · material  → /student/topic/[id]  (the shared material + evidence read)
     · learn     → /student/learn       (pose → struggle → reveal)
     · practice  → /student/practice    (adaptive, mistake-based)

   CONFIDENTIALITY: opaque seed ids only, no PII, neutral example board.
   ============================================================================ */

import { SEED_ONTOLOGY, SEED_ONTOLOGY_IDS } from '@classess/contracts';
import type { SubjectAccent } from '@classess/design-system';
import { topicInfo, MATH_SUBJECT_ID, PHYS_SUBJECT_ID, subjectCode } from './loopData';

export type SubLessonType = 'material' | 'learn' | 'practice';

export interface CourseTopic {
  id: string;
  name: string;
  /** Sequence within the chapter (the catalogue number). */
  sequence: number;
}

export interface CourseChapter {
  id: string;
  name: string;
  /** Display number within the term. */
  number: number;
  topics: CourseTopic[];
}

export interface CourseTerm {
  id: string;
  name: string;
  chapters: CourseChapter[];
  /** Total topics under this term — a calm count, not a score. */
  topicCount: number;
}

export interface CourseSubject {
  id: string;
  name: string;
  code: string;
  accent: SubjectAccent;
  terms: CourseTerm[];
  topicCount: number;
}

const SUBJECT_ACCENT: Record<string, SubjectAccent> = {
  [SEED_ONTOLOGY_IDS.subjMath]: 'cobalt',
  [SEED_ONTOLOGY_IDS.subjPhys]: 'emerald',
};

/** The grade-10 subjects the current student is enrolled in. */
const ENROLLED_SUBJECTS = [MATH_SUBJECT_ID, PHYS_SUBJECT_ID];

/**
 * Build the full course tree for the enrolled subjects, derived once from the
 * seed. Pure + deterministic — every surface gets the identical structure.
 */
export function studentCourseTree(): CourseSubject[] {
  const unitsBySubject = new Map<string, typeof SEED_ONTOLOGY.units>();
  for (const u of SEED_ONTOLOGY.units) {
    const list = unitsBySubject.get(u.subject_id) ?? [];
    list.push(u);
    unitsBySubject.set(u.subject_id, list);
  }
  const chaptersByUnit = new Map<string, typeof SEED_ONTOLOGY.chapters>();
  for (const c of SEED_ONTOLOGY.chapters) {
    const list = chaptersByUnit.get(c.unit_id) ?? [];
    list.push(c);
    chaptersByUnit.set(c.unit_id, list);
  }
  const topicsByChapter = new Map<string, typeof SEED_ONTOLOGY.topics>();
  for (const t of SEED_ONTOLOGY.topics) {
    const list = topicsByChapter.get(t.chapter_id) ?? [];
    list.push(t);
    topicsByChapter.set(t.chapter_id, list);
  }

  const subjectById = new Map(SEED_ONTOLOGY.subjects.map((s) => [s.id, s]));

  return ENROLLED_SUBJECTS.filter((id) => subjectById.has(id)).map((subjectId) => {
    const subject = subjectById.get(subjectId)!;
    const units = (unitsBySubject.get(subjectId) ?? []).slice().sort((a, b) => a.sequence - b.sequence);

    let subjectTopicCount = 0;
    const terms: CourseTerm[] = units.map((unit) => {
      const chapters = (chaptersByUnit.get(unit.id) ?? [])
        .slice()
        .sort((a, b) => a.sequence - b.sequence);
      let termTopicCount = 0;
      const courseChapters: CourseChapter[] = chapters.map((chapter, ci) => {
        const topics = (topicsByChapter.get(chapter.id) ?? [])
          .slice()
          .sort((a, b) => a.sequence - b.sequence)
          .map<CourseTopic>((t) => ({ id: t.id, name: t.name, sequence: t.sequence + 1 }));
        termTopicCount += topics.length;
        return { id: chapter.id, name: chapter.name, number: ci + 1, topics };
      });
      subjectTopicCount += termTopicCount;
      return { id: unit.id, name: unit.name, chapters: courseChapters, topicCount: termTopicCount };
    });

    return {
      id: subjectId,
      name: subject.name,
      code: subjectCode(subjectId),
      accent: SUBJECT_ACCENT[subjectId] ?? 'cobalt',
      terms,
      topicCount: subjectTopicCount,
    };
  });
}

/** The href for a sub-lesson type on a topic — the three ways in. */
export function subLessonHref(type: SubLessonType, topicId: string): string {
  switch (type) {
    case 'material':
      return `/student/topic/${topicId}`;
    case 'learn':
      return '/student/learn';
    case 'practice':
      return '/student/practice';
  }
}

export const SUB_LESSON_LABEL: Record<SubLessonType, string> = {
  material: 'Shared material',
  learn: 'Learn',
  practice: 'Practice',
};

export const SUB_LESSON_BLURB: Record<SubLessonType, string> = {
  material: 'Notes and resources your teacher has shared, with where you stand.',
  learn: 'Meet the idea, try it, then see it revealed.',
  practice: 'Short, adaptive practice — a miss repeats the idea.',
};

// Re-export so the browser can label a topic with its subject accent etc.
export { topicInfo };
