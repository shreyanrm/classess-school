'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Icon, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { TimetableGrid } from '../../_components/TimetableGrid';
import { CalendarGrid } from '../../_components/CalendarGrid';
import { AttendanceHeatmap } from '../../_components/AttendanceHeatmap';
import { Panel, FlagRow, HandnotePanel, SchedRow } from '../../_components/StudentComposed';
import { useVizData } from '@/lib/useVizData';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { CURRENT_STUDENT } from '@/lib/loopData';

/**
 * Timetable, calendar and attendance — the student's own week, the month ahead,
 * and a calm attendance read. The v2 student "Planner / Timetable" + "Calendar"
 * + "Attendance Tracker" screens, carried into the v3 grammar: one shell, three
 * page-head tabs, the shared cool-accent viz (TimetableGrid / CalendarGrid /
 * AttendanceHeatmap). Read GATEWAY-FIRST through the governed viz seam; the
 * PII-free seed answers only on degrade, surfaced honestly via SourceNote.
 *
 * Attendance is a calm pattern to notice, never a judgement — absent reads as a
 * tonal step, never an alarming wash. All five designed states ship.
 */

type Tab = 'timetable' | 'calendar' | 'attendance';

// Today's column on the weekly grid (0=Mon..5=Sat) — highlighted, never alarming.
function todayColumn(): number {
  const d = new Date().getDay(); // 0=Sun..6=Sat
  return d === 0 ? -1 : d - 1; // Sun has no column; Mon..Sat -> 0..5
}

export default function StudentTimetablePage() {
  const subject = CURRENT_STUDENT.ref;
  const viz = useVizData(['timetable', 'calendar', 'attendance'], subject);
  const [tab, setTab] = useState<Tab>('timetable');
  const { emit } = useEmit();

  const phase = viz.phase;
  const today = todayColumn();

  // Today's classes — the calm "your day" list the aside leads on.
  const todaysBlocks = useMemo(
    () =>
      viz.data.timetable.blocks
        .filter((b) => b.day === today)
        .sort((a, b) => a.period - b.period),
    [viz.data.timetable, today],
  );

  useEffect(() => {
    if (phase === 'ready')
      emit({
        type: 'surface.viewed',
        purpose: EVENT_PURPOSE.learning,
        payload: { surface: 'student.timetable', source: viz.source, tab },
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const att = viz.data.attendance;
  const attPct =
    att.counts.schoolDays > 0
      ? Math.round(((att.counts.present + att.counts.half * 0.5) / att.counts.schoolDays) * 100)
      : 0;

  return (
    <SurfaceShell
      breadcrumb={[{ label: 'Learning', href: '/student' }, { label: 'Timetable' }]}
      eyebrow="Your week"
      title="Timetable and attendance"
      meta={[
        { value: viz.data.timetable.blocks.length, label: 'classes this week' },
        { value: viz.data.calendar.events.length, label: 'things coming up' },
        { label: 'a calm read, never a judgement' },
      ]}
      tabs={[
        { label: 'Timetable', active: tab === 'timetable', onClick: () => setTab('timetable') },
        { label: 'Calendar', active: tab === 'calendar', onClick: () => setTab('calendar') },
        { label: 'Attendance', active: tab === 'attendance', onClick: () => setTab('attendance') },
      ]}
      dockIntro="Your week, the month ahead, and how your attendance is reading. Ask me what is on today, what is coming up, or to plan around a free slot."
      dockChips={['What is on today', 'What is coming up this week', 'When is my next assessment']}
      aside={
        phase === 'ready' ? (
          <>
            <Panel
              title="Today"
              meta={
                <Tag tone="info">
                  <span className="dot" />
                  {todaysBlocks.length || 0}
                </Tag>
              }
            >
              {today < 0 ? (
                <p className="caption">No classes today — a clear day to bring back a fading topic.</p>
              ) : todaysBlocks.length === 0 ? (
                <p className="caption">Nothing timetabled today. A good day to practise on your own.</p>
              ) : (
                todaysBlocks.map((b, i) => (
                  <SchedRow
                    key={i}
                    row={{
                      t: viz.data.timetable.periodLabels[b.period] ?? '',
                      title: b.label,
                      caption: b.detail ?? 'In your timetable.',
                    }}
                  />
                ))
              )}
            </Panel>

            <Panel title="Your attendance" meta={<span className="overline">a pattern, not a mark</span>}>
              <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'baseline' }}>
                <span className="display-sm" style={{ fontSize: 30, margin: 0 }}>
                  {attPct}
                  <span style={{ fontSize: 16 }}>%</span>
                </span>
                <span className="caption muted">present this term</span>
              </div>
              <p className="caption" style={{ marginTop: 'var(--space-2)' }}>
                {att.counts.present} present · {att.counts.half} half · {att.counts.leave} leave ·{' '}
                {att.counts.absent} absent
              </p>
              <button
                type="button"
                className="btn btn-secondary btn-sm btn-block"
                style={{ marginTop: 'var(--space-3)' }}
                onClick={() => setTab('attendance')}
              >
                See the full grid
              </button>
            </Panel>

            <Panel title="Coming up" meta={<span className="overline">next</span>}>
              {[...viz.data.calendar.events]
                .sort((a, b) => a.day - b.day)
                .slice(0, 3)
                .map((e, i) => (
                  <FlagRow
                    key={i}
                    flag={{
                      icon: e.type === 'exam' ? 'target' : e.type === 'homework' ? 'check' : 'calendar',
                      title: `${viz.data.calendar.label.slice(0, 3)} ${e.day} · ${e.label}`,
                      caption:
                        e.type === 'exam'
                          ? 'An assessment — your mocks mirror the real paper.'
                          : e.type === 'homework'
                            ? 'Something is due — submitting is your choice.'
                            : 'On the calendar.',
                    }}
                  />
                ))}
            </Panel>

            <HandnotePanel>your timetable shows where to be — your attendance is just a pattern to notice</HandnotePanel>
          </>
        ) : undefined
      }
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : (
        <>
          {tab === 'timetable' ? (
            <section className="stack">
              <TimetableGrid
                timetable={viz.data.timetable}
                source={viz.sourceByKind.timetable}
                highlightDay={today >= 0 ? today : undefined}
              />
              <p className="body-sm muted" style={{ maxWidth: 560 }}>
                Free slots are calm space, not gaps to fill — they are where you can practise on your
                own, or bring back a topic that is fading. Tap{' '}
                <Link href="/student/progress" style={{ color: 'var(--accent)', textDecoration: 'underline', textUnderlineOffset: 2 }}>
                  Your progress
                </Link>{' '}
                to see what to focus on.
              </p>
            </section>
          ) : null}

          {tab === 'calendar' ? (
            <section className="stack">
              <CalendarGrid month={viz.data.calendar} source={viz.sourceByKind.calendar} />
              <p className="body-sm muted" style={{ maxWidth: 560 }}>
                Assessments here mirror the real paper —{' '}
                <Link href="/student/mocks" style={{ color: 'var(--accent)', textDecoration: 'underline', textUnderlineOffset: 2 }}>
                  your mocks
                </Link>{' '}
                are shaped to match. Homework dates are a heads-up; whether you submit is your choice.
              </p>
            </section>
          ) : null}

          {tab === 'attendance' ? (
            <section className="stack">
              <div className="sec-head">
                <h3 className="h3" style={{ margin: 0 }}>
                  Your attendance
                </h3>
                <span className="overline">month by day · plain counts</span>
              </div>
              <div className="viz-card">
                <AttendanceHeatmap record={viz.data.attendance} source={viz.sourceByKind.attendance} />
              </div>
              <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                <Icon name="info" size="sm" className="quiet" />
                <p className="caption muted" style={{ margin: 0 }}>
                  This is a calm read of a pattern, never a judgement — half days count as half a day
                  present, and holidays sit outside the count.
                </p>
              </div>
            </section>
          ) : null}

          <SourceNote source={viz.source} />
        </>
      )}
    </SurfaceShell>
  );
}
