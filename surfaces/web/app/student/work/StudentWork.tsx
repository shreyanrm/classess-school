'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button, Icon, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { InboxItem } from '../../_components/InboxItem';
import { SourceNote } from '../../_components/SourceNote';
import { openVidya } from '../../_components/VidyaOrb';
import {
  StatMatrix,
  Panel,
  FlagRow,
  HandnotePanel,
  SecHead,
  type FlagModel,
} from '../../_components/StudentComposed';
import { useStore } from '@/lib/useStore';
import { useOnline } from '@/lib/useOnline';
import { useEmit } from '@/lib/useEmit';
import { useGatewaySource } from '@/lib/useGatewaySource';
import { CURRENT_STUDENT } from '@/lib/loopData';
import { EVENT_PURPOSE } from '@/lib/events';
import {
  MILESTONE_LABEL,
  loadInbox,
  loadProject,
  subscribeWork,
  type AssignmentView,
  type GroupProject,
} from '@/lib/workData';

type Tab = 'inbox' | 'project';
type LoadState = 'loading' | 'ready' | 'error';

const MILESTONE_TONE = {
  done: 'success',
  active: 'info',
  upcoming: 'neutral',
} as const;

const KIND_ICON = {
  'quick-check': 'check',
  homework: 'book',
  project: 'user',
} as const;

/**
 * Student work — the assignment inbox and the group-project view, composed dense.
 * A four-up read of the inbox up top, then the assignments themselves (each with
 * the permission-laddered, never-auto submit), and an aside for what is due first.
 * A check the teacher approves in /teacher/assign appears here through the shared
 * work list. The group view shows a balanced team, milestones, and contributions.
 */
export function StudentWork() {
  const { state } = useStore();
  const online = useOnline();
  const { emit } = useEmit();
  const { source } = useGatewaySource('learning', { subject: CURRENT_STUDENT.ref });
  const [tab, setTab] = useState<Tab>('inbox');
  const [load, setLoad] = useState<LoadState>('loading');
  const [inbox, setInbox] = useState<AssignmentView[]>([]);
  const [project, setProject] = useState<GroupProject | null>(null);

  useEffect(() => {
    function refresh() {
      try {
        setInbox(loadInbox(state));
        setProject(loadProject());
        setLoad('ready');
      } catch {
        setLoad('error');
      }
    }
    refresh();
    return subscribeWork(refresh);
  }, [state]);

  useEffect(() => {
    if (load === 'ready') emit({ type: 'surface.viewed', purpose: EVENT_PURPOSE.learning, payload: { surface: 'student.work' } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  const counts = useMemo(() => {
    const todo = inbox.filter((i) => i.status === 'todo').length;
    const active = inbox.filter((i) => i.status === 'in-progress').length;
    const returned = inbox.filter((i) => i.status === 'returned').length;
    return { todo, active, returned };
  }, [inbox]);

  // The "what is due first" flags — the next few unstarted/active items.
  const dueFlags: FlagModel[] = useMemo(
    () =>
      inbox
        .filter((i) => i.status === 'todo' || i.status === 'in-progress')
        .slice(0, 3)
        .map((i) => ({
          icon: KIND_ICON[i.kind],
          title: i.title,
          caption: `${i.subjectName} · ${i.due}`,
        })),
    [inbox],
  );

  const activeMilestone = project?.milestones.find((m) => m.state === 'active');

  return (
    <SurfaceShell
      breadcrumb={[{ label: 'Learning', href: '/student' }, { label: 'Work' }]}
      eyebrow="Your work"
      title="Assignments and projects"
      meta={[
        { value: inbox.length, label: 'assigned to you' },
        { value: counts.todo, label: 'to start' },
        { label: 'you decide when to submit' },
      ]}
      tabs={[
        { label: 'Inbox', active: tab === 'inbox', onClick: () => setTab('inbox') },
        { label: 'Group project', active: tab === 'project', onClick: () => setTab('project') },
      ]}
      dockIntro="Here is what is assigned to you. I can explain a task, or help you get started — but submitting is always your decision."
      dockChips={['What is due first', 'Help me start the trig check', 'Explain this homework']}
      aside={
        load === 'ready' ? (
          <>
            {tab === 'inbox' ? (
              <>
                <Panel title="Due first" meta={<Tag tone="info"><span className="dot" />{dueFlags.length}</Tag>}>
                  {dueFlags.length === 0 ? (
                    <p className="caption">Nothing waiting — you are clear.</p>
                  ) : (
                    dueFlags.map((f, i) => <FlagRow key={i} flag={f} />)
                  )}
                </Panel>
                <HandnotePanel>start does not submit — nothing leaves your hands until you say so</HandnotePanel>
              </>
            ) : project ? (
              <>
                <Panel title="The team" meta={<Tag tone={project.balanced ? 'success' : 'warning'}>{project.balanced ? 'Balanced' : 'Balancing'}</Tag>}>
                  <p className="caption" style={{ marginBottom: 8 }}>
                    {project.balanceNote}
                  </p>
                </Panel>
                {activeMilestone ? (
                  <Panel title="Right now" meta={<span className="overline">this week</span>}>
                    <FlagRow
                      flag={{ icon: 'target', title: activeMilestone.title, caption: activeMilestone.due }}
                    />
                  </Panel>
                ) : null}
                <HandnotePanel>a balanced team means no one carries it alone</HandnotePanel>
              </>
            ) : undefined}
          </>
        ) : undefined
      }
    >
      {load === 'loading' ? (
        <section className="stack" aria-busy="true" aria-label="Loading your work">
          <div className="skeleton" style={{ height: 96 }} />
          <div className="skeleton" style={{ height: 140 }} />
          <div className="skeleton" style={{ height: 140 }} />
        </section>
      ) : load === 'error' ? (
        <div className="empty">
          <Icon name="search" size="lg" className="glyph" />
          <h4 className="body">Your work could not be read</h4>
          <p>Something went wrong loading your assignments. Try again in a moment.</p>
        </div>
      ) : tab === 'inbox' ? (
        inbox.length === 0 ? (
          <div className="empty">
            <Icon name="check" size="lg" className="glyph" />
            <h4 className="body">Nothing assigned right now</h4>
            <p>When your teacher assigns a check or homework, it will appear here. Until then, you can keep practising what you are working on.</p>
            <Button variant="secondary" size="sm" onClick={() => openVidya('What can I practise right now')}>
              <Icon name="spark" size="sm" /> Try with Vidya
            </Button>
          </div>
        ) : (
          <>
            <StatMatrix
              stats={[
                { label: 'To start', value: counts.todo, delta: counts.todo ? 'waiting on you' : 'all clear', deltaDir: 'flat' },
                { label: 'In progress', value: counts.active, delta: 'on the go', deltaDir: counts.active ? 'up' : 'flat' },
                { label: 'Returned', value: counts.returned, delta: counts.returned ? 'feedback to read' : 'none', deltaDir: 'flat' },
                { label: 'Assigned', value: inbox.length, delta: 'in your inbox', deltaDir: 'flat' },
              ]}
            />

            <section className="reveal reveal-3">
              <SecHead title="Your inbox" meta={<span className="overline">submitting is your choice</span>} />
              <div className="stack">
                {inbox.map((item) => (
                  <InboxItem key={item.id} item={item} />
                ))}
              </div>
            </section>
          </>
        )
      ) : project ? (
        <GroupProjectView project={project} />
      ) : (
        <div className="empty">
          <Icon name="user" size="lg" className="glyph" />
          <h4 className="body">No group project right now</h4>
          <p>
            When you are part of a group project, you will see your team, your part, and the shared
            milestones here.
          </p>
          <Button variant="secondary" size="sm" onClick={() => openVidya('What group work do I have')}>
            <Icon name="spark" size="sm" /> Ask Vidya
          </Button>
        </div>
      )}

      {load === 'ready' ? <SourceNote source={source} /> : null}
    </SurfaceShell>
  );
}

function GroupProjectView({ project }: { project: GroupProject }) {
  const done = project.milestones.filter((m) => m.state === 'done').length;
  return (
    <>
      <StatMatrix
        stats={[
          { label: 'Team', value: project.members.length, delta: 'people, balanced', deltaDir: 'flat' },
          { label: 'Milestones', value: project.milestones.length, delta: 'in the plan', deltaDir: 'flat' },
          { label: 'Done', value: done, delta: 'so far', deltaDir: done ? 'up' : 'flat' },
          { label: 'Your part', value: <span style={{ fontSize: 15 }}>Write-up</span>, delta: 'your strength', deltaDir: 'flat' },
        ]}
      />

      <section className="next-step-hero reveal reveal-3">
        <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
          <div>
            <p className="overline" style={{ margin: 0 }}>
              Group project
            </p>
            <h3 className="display-sm" style={{ margin: '6px 0 0', fontSize: 24 }}>
              {project.title}
            </h3>
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              {project.due}
            </p>
          </div>
          <Tag tone={project.balanced ? 'success' : 'warning'}>
            {project.balanced ? 'Balanced team' : 'Team being balanced'}
          </Tag>
        </div>
        <p className="body-sm muted" style={{ marginTop: 'var(--space-3)', maxWidth: 560 }}>
          {project.balanceNote}
        </p>
      </section>

      <section>
        <SecHead title="Who is doing what" meta={<span className="overline">contributions</span>} />
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Member</th>
                <th>Carrying</th>
                <th className="num">Role</th>
              </tr>
            </thead>
            <tbody>
              {project.members.map((m) => (
                <tr key={m.label}>
                  <td>
                    <div className="row" style={{ gap: 'var(--space-2)' }}>
                      <span className="avatar avatar-sm">{initials(m.label)}</span>
                      {m.label}
                    </div>
                  </td>
                  <td className="muted">{m.contribution}</td>
                  <td className="num">{m.isYou ? <Tag tone="info">You</Tag> : <span className="data">Member</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <SecHead title="Milestones" meta={<span className="overline">{done} of {project.milestones.length} done</span>} />
        <div className="parent-timeline">
          {project.milestones.map((ms) => (
            <div className="parent-timeline-row" key={ms.id}>
              <div className="parent-timeline-marker">
                <span className="dot" aria-hidden="true" />
              </div>
              <div>
                <div className="row-between" style={{ alignItems: 'center' }}>
                  <span className="body">{ms.title}</span>
                  <Tag tone={MILESTONE_TONE[ms.state]}>{MILESTONE_LABEL[ms.state]}</Tag>
                </div>
                <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                  {ms.due}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function initials(label: string): string {
  if (label === 'You') return 'Y';
  const parts = label.split(' ');
  return parts.map((p) => p[0]).join('').slice(0, 2).toUpperCase();
}
