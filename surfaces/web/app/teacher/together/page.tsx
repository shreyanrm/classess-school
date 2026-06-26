'use client';

import { useEffect, useMemo } from 'react';
import { Icon, Matrix, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { ReadStates } from '../../_components/ReadStates';
import { PtmManager } from '../../_components/PtmManager';
import { useVizData } from '@/lib/useVizData';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { CLASS_LABEL } from '@/lib/loopData';

/**
 * Teacher-side parent-teacher-meeting management — the counterpart to the
 * parent's /parent/together. The teacher publishes a day's SLOTS with their
 * availability, reads incoming parent QUERIES (each with a prepared,
 * evidence-first talking point), and keeps calm meeting SUMMARIES with agreed
 * next steps.
 *
 * v3 grammar: a slot is held only when the teacher confirms a request — nothing
 * is auto-booked; queries are paired with prepared points so a meeting starts
 * from a shared read, not a defensive number; summaries are plain language,
 * never a raw score. Reads gateway-first (seed fallback) with a SourceNote;
 * all five designed states ship.
 */
export default function TeacherTogetherPage() {
  const viz = useVizData(['teacherPtm']);
  const { emit } = useEmit();
  const ptm = viz.data.teacherPtm;

  const counts = useMemo(() => {
    const open = ptm.slots.filter((s) => s.status === 'open').length;
    const requested = ptm.slots.filter((s) => s.status === 'requested').length;
    const booked = ptm.slots.filter((s) => s.status === 'booked').length;
    return { open, requested, booked, queries: ptm.queries.length };
  }, [ptm]);

  useEffect(() => {
    if (viz.phase === 'ready') {
      emit({
        type: 'surface.viewed',
        purpose: EVENT_PURPOSE.teaching,
        payload: { surface: 'teacher.together', source: viz.source, queries: counts.queries },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viz.phase]);

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Parent meetings"
      breadcrumb={[
        { label: 'School', href: '/' },
        { label: 'Grade 10', href: '/teacher' },
        { label: 'Parent meetings' },
      ]}
      meta={[
        { value: counts.requested || '—', label: counts.requested === 1 ? 'request waiting' : 'requests waiting' },
        { value: counts.queries || '—', label: 'parent queries' },
        { label: 'nothing is auto-booked' },
      ]}
      tabs={[
        { label: 'Overview', href: '/teacher' },
        { label: 'Class insights', href: '/teacher/insights' },
        { label: 'Evaluation', href: '/teacher/evaluate' },
        { label: 'Parent meetings', active: true },
      ]}
      dockIntro="The day's slots, the parent questions waiting, and your past meeting summaries. Confirm a requested slot to hold it — nothing books on its own. Ask me to draft a talking point for any query, or to summarise a meeting."
      dockChips={['Draft a point for the science query', 'Who is still waiting on a slot', 'Summarise the last meeting']}
      aside={
        viz.phase !== 'ready' ? null : (
          <>
            <div className="ignite-card reveal reveal-2">
              <div className="row-between" style={{ marginBottom: 14 }}>
                <span className="overline">This day</span>
                <Icon name="calendar" size="md" style={{ color: 'var(--accent)' }} />
              </div>
              <div className="who">{ptm.day}</div>
              <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                {counts.booked} held, {counts.open} open. Each conversation starts from a shared,
                evidence-first read — not a defensive number.
              </p>
            </div>

            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>The day, in plain language</h4>
              </div>
              <div className="sched" style={{ borderBottom: '0.5px solid var(--border)' }}>
                <Tag tone="success">{counts.booked}</Tag>
                <p className="caption" style={{ margin: 0, alignSelf: 'center' }}>slots held</p>
              </div>
              <div className="sched" style={{ borderBottom: '0.5px solid var(--border)' }}>
                <Tag tone="warning">{counts.requested}</Tag>
                <p className="caption" style={{ margin: 0, alignSelf: 'center' }}>requested, awaiting your confirm</p>
              </div>
              <div className="sched" style={{ borderBottom: 0 }}>
                <Tag tone="info">{counts.open}</Tag>
                <p className="caption" style={{ margin: 0, alignSelf: 'center' }}>still open</p>
              </div>
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                a slot is held only when you confirm it — never auto-booked
              </p>
            </div>
          </>
        )
      }
    >
      {viz.phase !== 'ready' ? (
        <ReadStates phase={viz.phase} onRetry={viz.refresh} />
      ) : (
        <>
          <Matrix columns={4} className="reveal reveal-1">
            <StatCell label="Slots open" value={counts.open} delta="ready to be requested" tone="flat" />
            <StatCell label="Requested" value={counts.requested} delta="awaiting your confirm" tone={counts.requested > 0 ? 'down' : 'flat'} />
            <StatCell label="Booked" value={counts.booked} delta="held for a parent" tone="up" />
            <StatCell label="Parent queries" value={counts.queries} delta="prepare a point for each" tone="flat" />
          </Matrix>

          <PtmManager data={ptm} source={viz.sourceByKind.teacherPtm} />
        </>
      )}
    </SurfaceShell>
  );
}
