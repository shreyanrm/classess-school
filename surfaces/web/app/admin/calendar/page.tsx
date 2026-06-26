'use client';

import Link from 'next/link';
import { Button, ConfidenceBand, Icon, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { CalendarGrid } from '../../_components/CalendarGrid';
import { TimetableGrid } from '../../_components/TimetableGrid';
import { AcademicPlanner } from '../../_components/AcademicPlanner';
import { SCHEDULE_ALTERNATIVES, SUBSTITUTION_NEED } from '@/lib/mock';
import { useAdminConfig } from '@/lib/adminConfig';
import { useVizData } from '@/lib/useVizData';
import { ACADEMIC_PLANNER_FALLBACK } from '@/lib/opsData';

type Decision = 'pending' | 'approved' | 'declined';
type View = 'calendar' | 'timetable' | 'planner' | 'cover';

/**
 * Calendar and timetable (admin) — recomposed to the sample-page bar and
 * deepened to the full v2 calendar engine, in the v3 grammar. Four views ride a
 * tab strip, the active one persisting through the wall:
 *
 *   · Calendar — a monthly event grid (cool/brand-coded event types) + an
 *     upcoming list (CalendarGrid, gateway-first via useVizData).
 *   · Timetable — the weekly day × period grid (TimetableGrid).
 *   · Academic planner — the year × month subject Gantt (AcademicPlanner).
 *   · Cover — the substitution flow: SCORED ALTERNATIVES with a plain-language
 *     fit + tradeoff, each behind an Approval control; nothing auto-commits.
 *
 * Event types use the cool accent palette only — never coral. Each viz carries a
 * SourceNote so the gateway-vs-fallback seam stays honest.
 */
export default function AdminCalendarPage() {
  const surface = useAdminConfig('calendar');
  const viz = useVizData(['calendar', 'timetable'], 'school-north');

  const savedView = surface.config.view;
  const view: View =
    savedView === 'timetable' || savedView === 'planner' || savedView === 'cover' || savedView === 'calendar'
      ? (savedView as View)
      : 'calendar';
  const setView = (v: View) => {
    void surface.set('view', v);
  };

  const savedChosen = typeof surface.config.chosen === 'string' ? surface.config.chosen : null;
  const savedDecision =
    surface.config.decision === 'approved' || surface.config.decision === 'declined'
      ? (surface.config.decision as Decision)
      : 'pending';
  const chosen = savedChosen;
  const decision: Decision = savedDecision;
  const choose = (id: string) => {
    void surface.set('chosen', id);
    void surface.set('decision', 'pending');
  };
  const setDecision = (d: Decision) => {
    void surface.set('decision', d);
  };

  const strongFits = SCHEDULE_ALTERNATIVES.filter((a) => a.fit === 'high').length;
  const calendar = viz.data.calendar;
  const timetable = viz.data.timetable;
  const exams = calendar.events.filter((e) => e.type === 'exam').length;
  const ptms = calendar.events.filter((e) => e.type === 'ptm').length;

  const dock: Record<View, { intro: string; chips: string[] }> = {
    calendar: {
      intro:
        'This is the academic calendar — every event on one calm month grid, colour-coded by type. Ask me what is coming up, or to schedule a holiday or a parent meeting; I prepare it and hold it for your approval.',
      chips: ['What is coming up this month', 'Schedule a parent-teacher meeting', 'Add the mid-term holiday'],
    },
    timetable: {
      intro:
        'This is the weekly timetable — every period for the week, subjects on the cool palette, free slots reading as calm empty cells. Ask me to generate a fresh timetable; I prepare it for you to approve.',
      chips: ['Generate a fresh timetable', 'Where are the free slots', 'Balance the load across days'],
    },
    planner: {
      intro:
        'This is the academic planner — a year of units laid out month by month, by subject. Ask me to pace a unit or reflow the plan when a section falls behind; I prepare the change for your approval.',
      chips: ['Pace the trigonometry unit', 'What runs in the exam months', 'Reflow the plan for a behind section'],
    },
    cover: {
      intro:
        'A teacher in Section 10-B is on approved leave on Thursday. I have scored three alternatives. Pick one and approve it; I will not commit anything on my own.',
      chips: ['Why is option one the best fit', 'Show the full week', 'Generate a fresh timetable'],
    },
  };

  return (
    <SurfaceShell
      eyebrow="Calendar and timetable"
      title="The school calendar"
      breadcrumb={[{ label: 'School', href: '/' }, { label: 'Calendar' }]}
      meta={[
        { value: calendar.events.length, label: `events in ${calendar.label}` },
        { value: exams, label: 'assessments' },
        { value: ptms, label: 'parent meetings' },
        { label: 'nothing auto-commits' },
      ]}
      tabs={[
        { label: 'Calendar', active: view === 'calendar', onClick: () => setView('calendar') },
        { label: 'Timetable', active: view === 'timetable', onClick: () => setView('timetable') },
        { label: 'Academic planner', active: view === 'planner', onClick: () => setView('planner') },
        { label: 'Cover a slot', active: view === 'cover', onClick: () => setView('cover') },
      ]}
      actions={
        <Link href="/admin/exams" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="calendar" size="sm" />
          Exam operations
        </Link>
      }
      dockIntro={dock[view].intro}
      dockChips={dock[view].chips}
      aside={
        surface.phase !== 'ready' ? null : (
          <>
            {view === 'cover' ? (
              <>
                <div className="ignite-card reveal reveal-2">
                  <div className="row-between" style={{ marginBottom: 14 }}>
                    <span className="overline">Yours to decide</span>
                    <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
                  </div>
                  <div className="who">{SCHEDULE_ALTERNATIVES.length} scored options, zero auto-commits</div>
                  <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                    Each alternative carries a plain-language fit and the tradeoff it costs. The platform
                    proposes; you approve.
                  </p>
                </div>

                <div className="panel">
                  <div className="sec-head" style={{ marginBottom: 8 }}>
                    <h4 className="h4" style={{ margin: 0 }}>
                      Thursday, Section 10-B
                    </h4>
                    <span className="overline">affected day</span>
                  </div>
                  {[
                    { t: '09:00', subject: 'Mathematics', note: 'Ratios sequence — on plan.' },
                    { t: '11:30', subject: 'Open slot', note: 'Assigned teacher on approved leave.' },
                    { t: '14:00', subject: 'Science', note: 'Practical — may shift with option 2.' },
                  ].map((s) => (
                    <div className="sched" key={s.t}>
                      <span className="t">{s.t}</span>
                      <div>
                        <div className="body-sm" style={{ fontWeight: 500 }}>
                          {s.subject}
                        </div>
                        <p className="caption">{s.note}</p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="panel" style={{ padding: '18px 20px' }}>
                  <p className="handnote" style={{ fontSize: 22 }}>
                    keep the ratios sequence intact — option one costs the least
                  </p>
                </div>
              </>
            ) : (
              <>
                <div className="ignite-card reveal reveal-2">
                  <div className="row-between" style={{ marginBottom: 14 }}>
                    <span className="overline">Coming up</span>
                    <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
                  </div>
                  <div className="who">{exams} assessment{exams === 1 ? '' : 's'} in {calendar.label}</div>
                  <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                    The calendar is one calm month grid. Assessments, parent meetings, holidays and
                    homework deadlines read by their own cool hue.
                  </p>
                </div>

                <div className="panel">
                  <div className="sec-head" style={{ marginBottom: 8 }}>
                    <h4 className="h4" style={{ margin: 0 }}>One calendar engine</h4>
                    <Tag tone="info" dot>four views</Tag>
                  </div>
                  <p className="caption" style={{ marginBottom: 12 }}>
                    The month grid, the weekly timetable, the year planner and slot cover all read one
                    source. A change in one is reflected across the rest.
                  </p>
                  {[
                    { t: 'Calendar', note: 'Every dated event, by type.' },
                    { t: 'Timetable', note: 'The weekly period grid.' },
                    { t: 'Planner', note: 'The year of units, month by month.' },
                  ].map((s) => (
                    <div className="sched" key={s.t}>
                      <span className="t">{s.t}</span>
                      <div>
                        <p className="caption">{s.note}</p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="panel" style={{ padding: '18px 20px' }}>
                  <p className="handnote" style={{ fontSize: 22 }}>
                    plan the year, then protect it — a slip caught in a month is small
                  </p>
                </div>
              </>
            )}
          </>
        )
      }
    >
      {surface.phase !== 'ready' ? (
        <ReadStates phase={surface.phase} onRetry={surface.refresh} />
      ) : view === 'calendar' ? (
        <>
          <Matrix columns={3} className="reveal reveal-1">
            <StatCell label="Events this month" value={calendar.events.length} delta={calendar.label} tone="flat" />
            <StatCell label="Assessments" value={exams} delta="on the calendar" tone="flat" />
            <StatCell label="Parent meetings" value={ptms} delta="scheduled" tone="up" />
          </Matrix>
          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>Academic calendar</h3>
              <span className="overline">monthly grid · event types</span>
            </div>
            <CalendarGrid month={calendar} source={viz.sourceByKind.calendar ?? viz.source} />
          </section>
        </>
      ) : view === 'timetable' ? (
        <>
          <Matrix columns={3} className="reveal reveal-1">
            <StatCell label="Days" value={timetable.dayLabels.length} delta="in the week" tone="flat" />
            <StatCell label="Periods a day" value={timetable.periodLabels.length} delta="time bands" tone="flat" />
            <StatCell label="Scheduled blocks" value={timetable.blocks.length} delta="across the week" tone="up" />
          </Matrix>
          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>Weekly timetable</h3>
              <span className="overline">day × period</span>
            </div>
            <TimetableGrid timetable={timetable} source={viz.sourceByKind.timetable ?? viz.source} />
          </section>
        </>
      ) : view === 'planner' ? (
        <>
          <Matrix columns={3} className="reveal reveal-1">
            <StatCell label="Subjects" value={new Set(ACADEMIC_PLANNER_FALLBACK.units.map((u) => u.subjectName)).size} delta="planned" tone="flat" />
            <StatCell label="Units" value={ACADEMIC_PLANNER_FALLBACK.units.length} delta="across the year" tone="flat" />
            <StatCell label="In delivery now" value={ACADEMIC_PLANNER_FALLBACK.units.filter((u) => u.current).length} delta="this month" tone="up" />
          </Matrix>
          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>Academic planner</h3>
              <span className="overline">year × month Gantt</span>
            </div>
            <AcademicPlanner data={ACADEMIC_PLANNER_FALLBACK} source={surface.source} />
          </section>
        </>
      ) : (
        <>
          <Matrix columns={3} className="reveal reveal-1">
            <StatCell label="Open slot" value={1} delta="Thursday, third period" tone="down" />
            <StatCell label="Alternatives scored" value={SCHEDULE_ALTERNATIVES.length} delta="ranked by fit" tone="flat" />
            <StatCell label="Strong fits" value={strongFits} delta="no clash, subject-matched" tone="up" />
          </Matrix>

          <SpotlightCard>
            <p className="overline">The need</p>
            <p className="body" style={{ marginTop: 'var(--space-2)' }}>
              {SUBSTITUTION_NEED.context}
            </p>
          </SpotlightCard>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Scored alternatives
              </h3>
              <span className="overline">ranked by fit</span>
            </div>
            <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
              Selecting one stages it; it is committed only when you approve.{' '}
              {surface.source === 'gateway'
                ? 'Your selection and approval are read back from the event store.'
                : 'Your selection and approval record to the event store when it is reachable.'}
            </p>
            <div className="stack" style={{ gap: 'var(--space-3)' }}>
              {SCHEDULE_ALTERNATIVES.map((alt, i) => {
                const selected = chosen === alt.id;
                return (
                  <SpotlightCard key={alt.id} padLg className={selected ? 'is-selected' : undefined}>
                    <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
                      <h3 className="body-lg" style={{ margin: 0 }}>
                        <span className="quiet">Option {i + 1}. </span>
                        {alt.summary}
                      </h3>
                      <ConfidenceBand
                        level={alt.fit}
                        label={`${alt.fit === 'high' ? 'Strong' : alt.fit === 'middle' ? 'Workable' : 'Weak'} fit`}
                      />
                    </div>

                    <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
                      <span className="quiet">Why it fits. </span>
                      {alt.fitNote}
                    </p>
                    <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
                      <span className="quiet">Tradeoff. </span>
                      {alt.tradeoff}
                    </p>

                    <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                      <Button
                        variant={selected ? 'primary' : 'secondary'}
                        size="sm"
                        onClick={() => choose(alt.id)}
                      >
                        {selected ? (
                          <>
                            <Icon name="check" size="sm" />
                            Selected
                          </>
                        ) : (
                          'Select this option'
                        )}
                      </Button>
                    </div>
                  </SpotlightCard>
                );
              })}
            </div>
          </section>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Approval
              </h3>
              <Tag tone={decision === 'approved' ? 'success' : decision === 'declined' ? 'neutral' : 'info'} dot>
                {decision === 'approved' ? 'Approved' : decision === 'declined' ? 'Declined' : chosen ? 'Awaiting you' : 'Pick an option'}
              </Tag>
            </div>
            <SpotlightCard padLg>
              {!chosen ? (
                <p className="body-sm muted" style={{ margin: 0 }}>
                  Select an option above to review it for approval. Nothing is committed until you
                  approve.
                </p>
              ) : decision === 'pending' ? (
                <>
                  <p className="body-sm" style={{ margin: 0 }}>
                    You are about to approve{' '}
                    <strong>{SCHEDULE_ALTERNATIVES.find((a) => a.id === chosen)?.summary}</strong>. This
                    updates the timetable for the affected sections and notifies the staff involved.
                  </p>
                  <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                    <Button variant="accent" size="sm" onClick={() => setDecision('approved')}>
                      Approve and apply
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setDecision('declined')}>
                      Decline
                    </Button>
                  </div>
                </>
              ) : (
                <p className="body-sm" style={{ margin: 0 }}>
                  {decision === 'approved'
                    ? 'Approved. The change is prepared to apply and the staff involved will be notified.'
                    : 'Declined. The slot stays open; you can pick another option.'}
                </p>
              )}
            </SpotlightCard>
          </section>

          <SourceNote source={surface.source} />
        </>
      )}
    </SurfaceShell>
  );
}
