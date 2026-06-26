'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ChildSwitcher } from '../../_components/ChildSwitcher';
import { ConsentGated } from '../../_components/ConsentGated';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { LanguageBadge } from '../../_components/LanguageBadge';
import { useParentRead } from '@/lib/useParentRead';
import { useReaderText } from '@/lib/useReaderText';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { requestPtm } from '@/lib/commData';
import { useT } from '@/lib/i18n';
import {
  DEFAULT_CHILD_ID,
  findChild,
  type LearnAlongside,
  type PtmMeeting,
} from '@/lib/parentData';

/**
 * Learn-alongside and PTM prep — recomposed to the sample-page bar. A stat
 * matrix (activities, minutes together, prep points, PTM status), then a .cols
 * layout:
 *   · main — the at-home activities as designed, subject-coloured cards (each a
 *     real next step), and the PTM card with a real booking REQUEST + an ICS add.
 *   · aside — a partnership ignite-card, a "your time together this week"
 *     timetable-style panel, and a Caveat handnote.
 *
 * Gateway-first read; mock bundle on degrade; SourceNote degrades honestly.
 * Activity copy renders into the parent's language through tx(). A PTM is never
 * auto-booked (the teacher confirms). All five designed states ship.
 */
export default function ParentTogetherPage() {
  const [childId, setChildId] = useState(DEFAULT_CHILD_ID);
  const child = findChild(childId);
  const { phase, data, source } = useParentRead(childId);
  const { emit } = useEmit();
  const { t } = useT();

  const activities = useMemo(() => data?.learnAlongside ?? [], [data]);
  const { tx, rendering, rendered, locale } = useReaderText(
    activities.flatMap((a) => [a.title, a.how, a.why]),
  );

  useEffect(() => {
    if (phase === 'ready') {
      emit({
        type: 'surface.viewed',
        purpose: EVENT_PURPOSE.learning,
        payload: { surface: 'parent.together', child: childId, source },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, childId]);

  const counts = useMemo(() => {
    if (!data) return { activities: 0, minutes: 0, prep: 0, scheduled: 0 };
    return {
      activities: data.learnAlongside.length,
      minutes: data.learnAlongside.reduce((s, a) => s + a.minutes, 0),
      prep: data.ptm.prep.length,
      scheduled: data.ptm.scheduled ? 1 : 0,
    };
  }, [data]);

  return (
    <SurfaceShell
      eyebrow={child ? child.section : t('parent.together.eyebrow')}
      title={child ? t('parent.together.titleChild', { child: child.label }) : t('parent.together.title')}
      breadcrumb={[
        { label: 'Family', href: '/parent' },
        { label: t('parent.together.eyebrow') },
      ]}
      meta={[
        { value: counts.activities || '—', label: 'activities for home' },
        { value: counts.minutes || '—', label: 'minutes together' },
        { label: 'partnership and pride' },
      ]}
      tabs={[
        { label: 'This week', href: '/parent' },
        { label: 'The child', href: '/parent/child' },
        { label: 'Reports', href: '/parent/reports' },
        { label: 'Together', active: true },
      ]}
      dockIntro={t('parent.together.dockIntro')}
      dockChips={[t('parent.together.chip1'), t('parent.together.chip2'), t('parent.together.chip3')]}
      aside={
        phase !== 'ready' || !child || !data ? null : (
          <>
            <div className="ignite-card reveal reveal-2">
              <div className="row-between" style={{ marginBottom: 14 }}>
                <span className="overline">Together</span>
                <Icon name="spark" size="md" style={{ color: 'var(--accent)' }} />
              </div>
              <div className="who">
                {counts.minutes} minutes, this week
              </div>
              <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                Short, warm time at home — each tied to where {child.label} is growing right now.
              </p>
            </div>

            {data.learnAlongside.length > 0 ? (
              <div className="panel reveal reveal-3">
                <div className="sec-head" style={{ marginBottom: 8 }}>
                  <h4 className="h4" style={{ margin: 0 }}>
                    Your time together
                  </h4>
                  <span className="overline">this week</span>
                </div>
                {data.learnAlongside.map((a) => (
                  <div className="sched" key={a.id}>
                    <span className="t">{a.minutes}m</span>
                    <div>
                      <div className="body-sm" style={{ fontWeight: 500 }}>
                        {tx(a.title)}
                      </div>
                      <p className="caption">{tx(a.why)}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="panel reveal reveal-4" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                no pressure — ten warm minutes beats an hour of pushing
              </p>
            </div>
          </>
        )
      }
    >
      <section className="stack">
        <div
          className="row-between"
          style={{ alignItems: 'flex-end', gap: 'var(--space-3)', flexWrap: 'wrap' }}
        >
          <p className="overline" style={{ margin: 0 }}>
            {t('parent.together.choose')}
          </p>
          <LanguageBadge locale={locale} rendering={rendering} rendered={rendered} />
        </div>
        <ChildSwitcher selectedId={childId} onSelect={setChildId} />
      </section>

      {phase === 'permission-denied' ? (
        <ConsentGated label={child?.label} />
      ) : phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : !child || !data ? (
        <ConsentGated label={child?.label} />
      ) : (
        <>
          <TogetherMatrix counts={counts} />

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                {t('parent.together.atHome')}
              </h3>
              <span className="overline">each tied to a real next step</span>
            </div>
            <p className="caption quiet">{t('parent.together.atHomeNote', { child: child.label })}</p>
            {data.learnAlongside.length === 0 ? (
              <p className="body-sm muted">{t('parent.together.noActivities')}</p>
            ) : (
              <div className="parent-links">
                {data.learnAlongside.map((a) => (
                  <LearnAlongsideCard key={a.id} activity={a} tx={tx} />
                ))}
              </div>
            )}
          </section>

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                {t('parent.together.ptm')}
              </h3>
              <span className="overline">your choice, never required</span>
            </div>
            <PtmCard ptm={data.ptm} childLabel={child.label} childId={childId} />
          </section>

          <p className="caption quiet row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="info" size="sm" />
            {t('parent.together.note', { child: child.label })}
          </p>
          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}

/** The plain-language count matrix for Together. */
function TogetherMatrix({
  counts,
}: {
  counts: { activities: number; minutes: number; prep: number; scheduled: number };
}) {
  const cells: Array<{ label: string; value: string; delta: string; tone: 'up' | 'flat' }> = [
    { label: 'Activities for home', value: String(counts.activities), delta: 'short and warm', tone: 'flat' },
    { label: 'Minutes together', value: String(counts.minutes), delta: 'suggested this week', tone: 'flat' },
    { label: 'Meeting prep', value: String(counts.prep), delta: 'points ready for you', tone: 'flat' },
    {
      label: 'Meeting',
      value: counts.scheduled ? 'Set' : 'Open',
      delta: counts.scheduled ? 'a time is held' : 'request whenever it suits',
      tone: counts.scheduled ? 'up' : 'flat',
    },
  ];
  return (
    <div className="matrix reveal reveal-1" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
      {cells.map((c) => (
        <div className="cell" key={c.label}>
          <div className="cell-label">{c.label}</div>
          <div className="cell-value">
            <span>{c.value}</span>
          </div>
          <div className={`cell-delta ${c.tone}`}>{c.delta}</div>
        </div>
      ))}
    </div>
  );
}

function LearnAlongsideCard({
  activity,
  tx,
}: {
  activity: LearnAlongside;
  /** Render generated text into the reader's language (falls back to original). */
  tx: (text: string) => string;
}) {
  const { t } = useT();
  return (
    <SpotlightCard padLg data-subject={activity.subject}>
      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center' }}>
        <span
          className="report-subject-chip"
          style={
            {
              '--subject': `var(--${activity.subject})`,
              '--subject-ink': `var(--${activity.subject}-ink)`,
            } as React.CSSProperties
          }
        >
          {activity.subject.slice(0, 3).toUpperCase()}
        </span>
        <div className="row-between" style={{ flex: 1, alignItems: 'flex-start', gap: 'var(--space-4)' }}>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {tx(activity.title)}
          </h3>
          <span className="row caption muted" style={{ gap: 'var(--space-2)' }}>
            <Icon name="clock" size="sm" />
            {t('parent.together.about', { minutes: activity.minutes })}
          </span>
        </div>
      </div>
      <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
        <span className="quiet">{t('parent.together.togetherLabel')} </span>
        {tx(activity.how)}
      </p>
      <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
        <span className="quiet">{t('parent.together.whyHelps')} </span>
        {tx(activity.why)}
      </p>
    </SpotlightCard>
  );
}

function downloadMeetingIcs(ptm: PtmMeeting, childLabel: string) {
  const stamp = new Date().toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
  const ics = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Classess//PTM//EN',
    'BEGIN:VEVENT',
    `UID:ptm-${childLabel.replace(/\s+/g, '-')}-${stamp}@classess`,
    `DTSTAMP:${stamp}`,
    `SUMMARY:Parent-teacher meeting — ${childLabel}`,
    `DESCRIPTION:${(ptm.when ?? '').replace(/,/g, '\\,')} with ${ptm.with}`,
    'END:VEVENT',
    'END:VCALENDAR',
  ].join('\r\n');
  const blob = new Blob([ics], { type: 'text/calendar' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'parent-teacher-meeting.ics';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function PtmCard({ ptm, childLabel, childId }: { ptm: PtmMeeting; childLabel: string; childId: string }) {
  const [requested, setRequested] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [rescheduling, setRescheduling] = useState(false);
  const { emit } = useEmit();
  const { t } = useT();

  async function request(starts?: string, windowLabel?: string) {
    setRequesting(true);
    await requestPtm({
      parentRef: childId,
      childContextRef: childId,
      windowLabel,
      startsAt: starts,
      childBrief: `A short, shared conversation about how to support ${childLabel} together.`,
      consentRef: childId,
    });
    await emit({
      type: 'ptm.requested',
      purpose: EVENT_PURPOSE.learning,
      payload: { surface: 'parent.together', child: childId, window: windowLabel ?? null },
      canonicalUuid: childId,
    });
    setRequesting(false);
    setRequested(true);
  }

  if (!ptm.scheduled) {
    return (
      <SpotlightCard hero padLg>
        <div className="empty" style={{ padding: 'var(--space-4) 0' }}>
          <Icon name="calendar" size="lg" className="glyph" />
          <h4 className="body">{t('parent.together.ptmNone')}</h4>
          <p>{t('parent.together.ptmNoneNote', { child: childLabel })}</p>
        </div>
        <div className="rec-actions">
          {requested ? (
            <>
              <Tag tone="success">{t('parent.together.ptmRequested')}</Tag>
              <span className="caption muted">{t('parent.together.ptmRequestedNote')}</span>
            </>
          ) : (
            <Button variant="primary" size="sm" disabled={requesting} onClick={() => request()}>
              {requesting ? t('parent.together.ptmRequesting') : t('parent.together.ptmRequest')}
              <Icon name="arrow-right" size="sm" />
            </Button>
          )}
        </div>
      </SpotlightCard>
    );
  }

  return (
    <SpotlightCard hero padLg>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <div>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {ptm.when}
          </h3>
          <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
            With {ptm.with}
          </p>
        </div>
        <Tag tone="info">{t('parent.together.ptmScheduled')}</Tag>
      </div>

      <p className="overline" style={{ marginTop: 'var(--space-5)' }}>
        {t('parent.together.ptmBring')}
      </p>
      <ul className="parent-ptm-list">
        {ptm.prep.map((item) => (
          <li key={item.id} className="parent-ptm-item">
            <Icon name="check" size="sm" />
            <div>
              <div className="body-sm">{item.point}</div>
              <div className="caption muted" style={{ marginTop: 2 }}>
                {item.context}
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div className="rec-actions" style={{ marginTop: 'var(--space-5)' }}>
        <Button variant="primary" size="sm" onClick={() => downloadMeetingIcs(ptm, childLabel)}>
          {t('parent.together.ptmCalendar')}
          <Icon name="arrow-right" size="sm" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={requesting}
          onClick={() => {
            void request(undefined, ptm.when ?? undefined).then(() => setRescheduling(true));
          }}
        >
          {requesting ? t('parent.together.ptmRequesting') : t('parent.together.ptmReschedule')}
        </Button>
      </div>
      {rescheduling ? (
        <p className="caption muted" style={{ marginTop: 'var(--space-3)' }}>
          {t('parent.together.ptmRescheduleNote')}
        </p>
      ) : null}
    </SpotlightCard>
  );
}
