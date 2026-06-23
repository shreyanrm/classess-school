'use client';

import { useMemo, useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ChildSwitcher } from '../../_components/ChildSwitcher';
import { ConsentGated } from '../../_components/ConsentGated';
import {
  DEFAULT_CHILD_ID,
  findChild,
  selectChildData,
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
  const data = useMemo(() => selectChildData(childId), [childId]);

  return (
    <SurfaceShell
      eyebrow={child ? child.section : 'Together'}
      title={child ? `Learning alongside ${child.label}` : 'Learn alongside and PTM'}
      dockIntro="Ask for a short activity to do together, or help preparing for the parent-teacher meeting."
      dockChips={['A 10-minute activity', 'Help me prepare for the meeting', 'What to ask the teacher']}
    >
      <section className="stack">
        <p className="overline">Choose a child</p>
        <ChildSwitcher selectedId={childId} onSelect={setChildId} />
      </section>

      {!child || !data ? (
        <ConsentGated label={child?.label} />
      ) : (
        <>
          <section className="stack">
            <p className="overline">Do this together at home</p>
            <p className="caption quiet">
              Short, warm activities — each tied to where {child.label} is growing right now. No
              pressure, just time together.
            </p>
            {data.learnAlongside.length === 0 ? (
              <p className="body-sm muted">New activities will appear here as topics move on.</p>
            ) : (
              <div className="parent-links">
                {data.learnAlongside.map((a) => (
                  <LearnAlongsideCard key={a.id} activity={a} />
                ))}
              </div>
            )}
          </section>

          <section className="stack">
            <p className="overline">Parent-teacher meeting</p>
            <PtmCard ptm={data.ptm} childLabel={child.label} />
          </section>

          <p className="caption quiet row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="info" size="sm" />
            These suggestions come from {child.label}&apos;s shared learning. You decide what to do
            and when — nothing is set for you.
          </p>
        </>
      )}
    </SurfaceShell>
  );
}

function LearnAlongsideCard({ activity }: { activity: LearnAlongside }) {
  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <h3 className="body-lg" style={{ margin: 0 }}>
          {activity.title}
        </h3>
        <span className="row caption muted" style={{ gap: 'var(--space-2)' }}>
          <Icon name="clock" size="sm" />
          About {activity.minutes} min
        </span>
      </div>
      <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
        <span className="quiet">Together. </span>
        {activity.how}
      </p>
      <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
        <span className="quiet">Why it helps. </span>
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

function PtmCard({ ptm, childLabel }: { ptm: PtmMeeting; childLabel: string }) {
  const [requested, setRequested] = useState(false);
  const [rescheduling, setRescheduling] = useState(false);

  if (!ptm.scheduled) {
    return (
      <SpotlightCard hero padLg>
        <div className="empty" style={{ padding: 'var(--space-4) 0' }}>
          <Icon name="calendar" size="lg" className="glyph" />
          <h4 className="body">No meeting scheduled yet</h4>
          <p>
            There is nothing urgent for {childLabel}. You can request a meeting with the teacher
            whenever it suits you, and a prep list will be ready here.
          </p>
        </div>
        <div className="rec-actions">
          {requested ? (
            <>
              <Tag tone="success">Request sent</Tag>
              <span className="caption muted">
                The teacher will propose a time. You will see it here, and a prep list will be ready.
              </span>
            </>
          ) : (
            <Button variant="primary" size="sm" onClick={() => setRequested(true)}>
              Request a meeting
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
        <Tag tone="info">Scheduled</Tag>
      </div>

      <p className="overline" style={{ marginTop: 'var(--space-5)' }}>
        Bring these to the meeting
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
          Add to your calendar
          <Icon name="arrow-right" size="sm" />
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setRescheduling((v) => !v)}>
          Reschedule
        </Button>
      </div>
      {rescheduling ? (
        <p className="caption muted" style={{ marginTop: 'var(--space-3)' }}>
          A reschedule request has been noted. The teacher will propose a new time and it will
          appear here.
        </p>
      ) : null}
    </SpotlightCard>
  );
}
