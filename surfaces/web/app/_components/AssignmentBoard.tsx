'use client';

import { useMemo, useState } from 'react';
import { Icon, Tag } from '@classess/design-system';
import { SourceNote } from './SourceNote';
import type {
  AssignmentBoard as AssignmentBoardData,
  AssignmentKind,
  AssignmentRow,
  AssignmentStatus,
  ReadSource,
} from '@/lib/vizData';

/* ============================================================================
   AssignmentBoard — the v2 "Assignments by chapter" tracker, in v3.

   A Homework / Quiz / Project tab strip, then the assignments grouped by
   chapter, each row carrying a submissions % built from PLAIN COUNTS (never a
   single opaque figure), a due token, and a calm status. Selecting a row calls
   `onOpen` so the host surface can open the per-assignment read (the project
   rubric, the question review). Bands of completion, never a raw mark.

   v3 grammar: subjects on the cool accent palette (never coral), depth =
   hairline + tonal step, NO shadow, reduced-motion safe. Pure + data-driven.
   ============================================================================ */

const KIND_TABS: { id: AssignmentKind | 'all'; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'homework', label: 'Homework' },
  { id: 'quiz', label: 'Quiz' },
  { id: 'project', label: 'Projects' },
];

const KIND_LABEL: Record<AssignmentKind, string> = {
  homework: 'Homework',
  quiz: 'Quiz',
  project: 'Project',
};

const STATUS_META: Record<AssignmentStatus, { label: string; tone: 'neutral' | 'info' | 'success' }> = {
  awaiting: { label: 'Scheduled', tone: 'neutral' },
  'in-window': { label: 'Open', tone: 'info' },
  closed: { label: 'Closed', tone: 'success' },
};

export interface AssignmentBoardProps {
  data: AssignmentBoardData;
  source?: ReadSource;
  /** Open one assignment (e.g. into the project rubric or the question review). */
  onOpen?: (assignment: AssignmentRow) => void;
  /** Lock the tab strip to one kind (e.g. the host shows only projects). */
  only?: AssignmentKind;
}

export function AssignmentBoard({ data, source = 'fallback', onOpen, only }: AssignmentBoardProps) {
  const [kind, setKind] = useState<AssignmentKind | 'all'>(only ?? 'all');

  const chapters = useMemo(() => {
    const active = only ?? kind;
    return data.chapters
      .map((ch) => ({
        ...ch,
        assignments: ch.assignments.filter((a) => active === 'all' || a.kind === active),
      }))
      .filter((ch) => ch.assignments.length > 0);
  }, [data.chapters, kind, only]);

  const visibleCount = chapters.reduce((s, ch) => s + ch.assignments.length, 0);

  return (
    <div className="stack" style={{ gap: 'var(--space-4)' }}>
      {only ? null : (
        <div className="segmented" role="tablist" aria-label="Assignment type">
          {KIND_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={kind === t.id}
              className={kind === t.id ? 'active' : ''}
              onClick={() => setKind(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {visibleCount === 0 ? (
        <div className="empty">
          <Icon name="book" size="lg" className="glyph" />
          <h4 className="body">Nothing in this group yet</h4>
          <p>No assignments of this type are published for {data.classLabel}. Switch tabs to see the rest.</p>
        </div>
      ) : (
        <div className="stack" style={{ gap: 'var(--space-5)' }}>
          {chapters.map((ch) => (
            <div className="stack" style={{ gap: 'var(--space-3)' }} key={ch.chapter}>
              <div className="sec-head">
                <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                  <span className="subject-dot" style={{ background: `var(--${ch.subject})` }} aria-hidden="true" />
                  <p className="overline" style={{ margin: 0 }}>{ch.chapter}</p>
                </div>
                <span className="caption quiet">{ch.assignments.length} assigned</span>
              </div>

              <ul className="assign-list">
                {ch.assignments.map((a) => {
                  const pct = a.total > 0 ? Math.round((a.submitted / a.total) * 100) : 0;
                  const st = STATUS_META[a.status];
                  const interactive = Boolean(onOpen);
                  const Row = interactive ? 'button' : 'div';
                  return (
                    <li key={a.id}>
                      <Row
                        type={interactive ? 'button' : undefined}
                        className={`assign-row subject-tinted${interactive ? ' assign-row-link' : ''}`}
                        data-subject={a.subject}
                        onClick={interactive ? () => onOpen!(a) : undefined}
                      >
                        <div className="assign-row-main">
                          <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
                            <span className="body-sm" style={{ fontWeight: 500 }}>{a.title}</span>
                            <Tag tone="neutral">{KIND_LABEL[a.kind]}</Tag>
                          </div>
                          <p className="caption quiet" style={{ margin: '4px 0 0' }}>
                            {a.published} · {a.due}
                          </p>
                        </div>
                        <div className="assign-row-meta">
                          <div className="assign-pct">
                            <div
                              className="progress"
                              style={{ ['--bar' as string]: `var(--${a.subject})`, width: 88 } as React.CSSProperties}
                            >
                              <span style={{ width: `${pct}%`, background: `var(--${a.subject})` }} />
                            </div>
                            <span className="caption muted">{a.submitted}/{a.total} · {pct}%</span>
                          </div>
                          <Tag tone={st.tone}>{st.label}</Tag>
                          {interactive ? <Icon name="arrow-right" size="sm" /> : null}
                        </div>
                      </Row>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}

      <SourceNote source={source} />
    </div>
  );
}
