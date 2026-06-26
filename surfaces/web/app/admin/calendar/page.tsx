'use client';

import Link from 'next/link';
import { Button, ConfidenceBand, Icon, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { SCHEDULE_ALTERNATIVES, SUBSTITUTION_NEED } from '@/lib/mock';
import { useAdminConfig } from '@/lib/adminConfig';

type Decision = 'pending' | 'approved' | 'declined';

/**
 * Calendar and timetable — recomposed to the sample-page bar. When a slot needs
 * cover, the platform proposes SCORED ALTERNATIVES with a plain-language fit and
 * tradeoff. A page-head with a mono meta line + tab strip, a count-up stat matrix
 * (open slot / alternatives / best fit), then cols: the need + the scored
 * alternatives + the approval control on the main; the affected-day timetable
 * (.sched) and a handnote on the 320px aside. Each alternative carries an
 * Approval control — it never auto-commits; the human picks and approves. The
 * choice and decision persist through the wall.
 */
export default function AdminCalendarPage() {
  const surface = useAdminConfig('calendar');
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

  return (
    <SurfaceShell
      eyebrow="Calendar and timetable"
      title="Cover for an open slot"
      breadcrumb={[{ label: 'School', href: '/' }, { label: 'Calendar' }]}
      meta={[
        { value: 1, label: 'open slot' },
        { value: SCHEDULE_ALTERNATIVES.length, label: 'alternatives scored' },
        { value: strongFits, label: 'strong fits' },
        { label: 'nothing auto-commits' },
      ]}
      tabs={[
        { label: 'Cover', active: true },
        { label: 'Exams', href: '/admin/exams' },
        { label: 'Curriculum', href: '/admin/curriculum' },
        { label: 'Briefing', href: '/admin' },
      ]}
      actions={
        <Link href="/admin/exams" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="calendar" size="sm" />
          Exam operations
        </Link>
      }
      dockIntro="A teacher in Section 10-B is on approved leave on Thursday. I have scored three alternatives. Pick one and approve it; I will not commit anything on my own."
      dockChips={['Why is option one the best fit', 'Show the full week', 'Generate a fresh timetable']}
      aside={
        surface.phase !== 'ready' ? null : (
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
        )
      }
    >
      {surface.phase !== 'ready' ? (
        <ReadStates phase={surface.phase} onRetry={surface.refresh} />
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
