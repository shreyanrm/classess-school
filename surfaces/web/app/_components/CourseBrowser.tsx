'use client';

/* ============================================================================
   CourseBrowser — the hierarchical course-content browser for the student:
   subject → term/periodic → chapter → topic, expandable, with the three
   sub-lesson ways into each topic (Shared material / Learn / Practice).

   Reads the derived course tree (lib/courseData → SEED_ONTOLOGY), so it never
   drifts from the rest of the platform. Plain language only — a topic is a place
   to go, never a mark.

   v3 GRAMMAR:
     · The subject band is the one hit of cool pigment (subject accent).
     · Hairline + tonal disclosure; NEVER a shadow.
     · Fully keyboard-operable disclosure (native <button> headers, aria-expanded).
     · Reduced-motion: rows simply appear (no height animation depended upon).
   ============================================================================ */

import { useState } from 'react';
import Link from 'next/link';
import { Icon } from '@classess/design-system';
import {
  studentCourseTree,
  subLessonHref,
  SUB_LESSON_LABEL,
  SUB_LESSON_BLURB,
  type CourseSubject,
  type CourseTerm,
  type CourseChapter,
  type SubLessonType,
} from '@/lib/courseData';

const SUB_TYPES: SubLessonType[] = ['material', 'learn', 'practice'];

export function CourseBrowser({ defaultOpenSubject }: { defaultOpenSubject?: string }) {
  const tree = studentCourseTree();
  const first = defaultOpenSubject ?? tree[0]?.id;
  const [openSubject, setOpenSubject] = useState<string | null>(first ?? null);

  return (
    <div className="course-browser">
      {tree.map((subject) => (
        <SubjectNode
          key={subject.id}
          subject={subject}
          open={openSubject === subject.id}
          onToggle={() => setOpenSubject((cur) => (cur === subject.id ? null : subject.id))}
        />
      ))}
    </div>
  );
}

function SubjectNode({
  subject,
  open,
  onToggle,
}: {
  subject: CourseSubject;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <section className="course-subject" data-accent={subject.accent}>
      <button
        type="button"
        className="course-subject-head"
        onClick={onToggle}
        aria-expanded={open}
        style={{ ['--subject-hue' as string]: `var(--${subject.accent})` }}
      >
        <span className="course-subject-band" aria-hidden="true">
          {subject.code}
        </span>
        <span className="course-subject-lead">
          <span className="body-lg" style={{ fontWeight: 500 }}>
            {subject.name}
          </span>
          <span className="caption muted">
            {subject.terms.length} terms · {subject.topicCount} topics
          </span>
        </span>
        <Icon name="chevron-down" size="sm" className={`course-caret${open ? ' open' : ''}`} />
      </button>

      {open ? (
        <div className="course-terms">
          {subject.terms.map((term) => (
            <TermNode key={term.id} term={term} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

function TermNode({ term }: { term: CourseTerm }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="course-term">
      <button
        type="button"
        className="course-term-head"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <Icon name="chevron-right" size="sm" className={`course-caret${open ? ' open' : ''}`} />
        <span className="overline" style={{ margin: 0 }}>
          {term.name}
        </span>
        <span className="caption muted">{term.topicCount} topics</span>
      </button>
      {open ? (
        <div className="course-chapters">
          {term.chapters.map((chapter) => (
            <ChapterNode key={chapter.id} chapter={chapter} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ChapterNode({ chapter }: { chapter: CourseChapter }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="course-chapter">
      <button
        type="button"
        className="course-chapter-head"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <Icon name="chevron-right" size="sm" className={`course-caret${open ? ' open' : ''}`} />
        <span className="course-chapter-num" aria-hidden="true">
          {chapter.number}
        </span>
        <span className="body-sm" style={{ fontWeight: 500 }}>
          {chapter.name}
        </span>
        <span className="caption muted">
          {chapter.topics.length} {chapter.topics.length === 1 ? 'topic' : 'topics'}
        </span>
      </button>
      {open ? (
        <ul className="course-topics">
          {chapter.topics.map((topic) => (
            <li key={topic.id} className="course-topic">
              <div className="course-topic-lead">
                <span className="course-topic-dot" aria-hidden="true" />
                <Link href={`/student/topic/${topic.id}`} className="course-topic-name">
                  {topic.name}
                </Link>
              </div>
              <div className="course-sublessons" role="group" aria-label={`Ways into ${topic.name}`}>
                {SUB_TYPES.map((type) => (
                  <Link
                    key={type}
                    href={subLessonHref(type, topic.id)}
                    className="sublesson-chip"
                    title={SUB_LESSON_BLURB[type]}
                  >
                    <Icon
                      name={type === 'material' ? 'book' : type === 'learn' ? 'spark' : 'target'}
                      size="sm"
                    />
                    {SUB_LESSON_LABEL[type]}
                  </Link>
                ))}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
