'use client';

import { useEffect, useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ChildSwitcher } from '../../_components/ChildSwitcher';
import { ConsentGated } from '../../_components/ConsentGated';
import { ReadStates } from '../../_components/ReadStates';
import { useParentRead } from '@/lib/useParentRead';
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
 * Learn-alongside and PTM prep. Activities you can do together at home, in
 * plain language, each tied to a real next step for the child; and a calm
 * preparation list for the parent-teacher meeting. Partnership and pride.
 */
export default function ParentTogetherPage() {
  const [childId, setChildId] = useState(DEFAULT_CHILD_ID);
  const child = findChild(childId);
  // Gateway-first governed read; the mock bundle answers on degrade. Switching
  // child re-reads. Five designed states via the hook.
  const { phase, data, source } = useParentRead(childId);
  const { emit } = useEmit();
  const { t } = useT();

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

  return (
    <SurfaceShell
      eyebrow={child ? child.section : t('parent.together.eyebrow')}
      title={child ? t('parent.together.titleChild', { child: child.label }) : t('parent.together.title')}
      dockIntro={t('parent.together.dockIntro')}
      dockChips={[t('parent.together.chip1'), t('parent.together.chip2'), t('parent.together.chip3')]}
    >
      <section className="stack">
        <p className="overline">{t('parent.together.choose')}</p>
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
          <section className="stack">
            <p className="overline">{t('parent.together.atHome')}</p>
            <p className="caption quiet">
              {t('parent.together.atHomeNote', { child: child.label })}
            </p>
            {data.learnAlongside.length === 0 ? (
              <p className="body-sm muted">{t('parent.together.noActivities')}</p>
            ) : (
              <div className="parent-links">
                {data.learnAlongside.map((a) => (
                  <LearnAlongsideCard key={a.id} activity={a} />
                ))}
              </div>
            )}
          </section>

          <section className="stack">
            <p className="overline">{t('parent.together.ptm')}</p>
            <PtmCard ptm={data.ptm} childLabel={child.label} childId={childId} />
          </section>

          <p className="caption quiet row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="info" size="sm" />
            {t('parent.together.note', { child: child.label })}
          </p>
        </>
      )}
    </SurfaceShell>
  );
}

function LearnAlongsideCard({ activity }: { activity: LearnAlongside }) {
  const { t } = useT();
  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <h3 className="body-lg" style={{ margin: 0 }}>
          {activity.title}
        </h3>
        <span className="row caption muted" style={{ gap: 'var(--space-2)' }}>
          <Icon name="clock" size="sm" />
          {t('parent.together.about', { minutes: activity.minutes })}
        </span>
      </div>
      <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
        <span className="quiet">{t('parent.together.togetherLabel')} </span>
        {activity.how}
      </p>
      <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
        <span className="quiet">{t('parent.together.whyHelps')} </span>
        {activity.why}
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

  // GAP#12 — booking/requesting a PTM is a REAL write now. It prepares a booking
  // through the wall (communication.ptm -> ptm.PtmService.request_booking, a
  // PROPOSED booking awaiting a human confirm — the permission ladder) and a
  // clean attributed ptm.requested event is persisted; the surface also emits an
  // attributed parent event. On a degrade the request still records locally so
  // the surface never breaks.
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
        <Button
          variant="primary"
          size="sm"
          onClick={() => downloadMeetingIcs(ptm, childLabel)}
        >
          {t('parent.together.ptmCalendar')}
          <Icon name="arrow-right" size="sm" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={requesting}
          onClick={() => {
            // A reschedule is a fresh booking REQUEST through the wall (it never
            // auto-rebooks — the teacher confirms). Real write + emit, then the
            // local note confirms it was recorded.
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
