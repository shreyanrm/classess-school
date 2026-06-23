'use client';

import { useEffect, useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { InboxItem } from '../../_components/InboxItem';
import { openVidya } from '../../_components/VidyaOrb';
import { useStore } from '@/lib/useStore';
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

/**
 * Student work (d9) — the assignment inbox and the group-project view. The inbox
 * lists assigned checks, homework, and projects with due dates and status; the
 * submit step is permission-laddered and never auto-fires. A check the teacher
 * approves in /teacher/assign appears here through the shared work list. The
 * group view shows a balanced team, milestones, and each member's contribution.
 */
export function StudentWork() {
  const { state } = useStore();
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
    // Re-read when a teacher-assigned check is pushed to the shared list.
    return subscribeWork(refresh);
  }, [state]);

  return (
    <SurfaceShell
      eyebrow="Your work"
      title="Assignments and projects"
      dockIntro="Here is what is assigned to you. I can explain a task, or help you get started — but submitting is always your decision."
      dockChips={['What is due first', 'Help me start the trig check', 'Explain this homework']}
    >
      <section className="stack">
        <div className="segmented" role="group" aria-label="View">
          <button type="button" className={tab === 'inbox' ? 'active' : ''} onClick={() => setTab('inbox')}>
            Inbox
          </button>
          <button type="button" className={tab === 'project' ? 'active' : ''} onClick={() => setTab('project')}>
            Group project
          </button>
        </div>
      </section>

      {load === 'loading' ? (
        <section className="stack" aria-busy="true" aria-label="Loading your work">
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
            <p>When your teacher assigns a check or homework, it will appear here. Until then, you can keep your streak going.</p>
            <Button variant="secondary" size="sm" onClick={() => openVidya('What can I practise right now')}>
              <Icon name="spark" size="sm" /> Try with Vidya
            </Button>
          </div>
        ) : (
          <section className="stack">
            {inbox.map((item) => (
              <InboxItem key={item.id} item={item} />
            ))}
          </section>
        )
      ) : project ? (
        <GroupProjectView project={project} />
      ) : null}
    </SurfaceShell>
  );
}

function GroupProjectView({ project }: { project: GroupProject }) {
  return (
    <section className="stack">
      <SpotlightCard padLg>
        <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
          <div>
            <h3 className="body-lg" style={{ margin: 0 }}>
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
        <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
          {project.balanceNote}
        </p>
      </SpotlightCard>

      <div>
        <p className="overline">Who is doing what</p>
        <div className="stack">
          {project.members.map((m) => (
            <SpotlightCard key={m.label} padLg>
              <div className="row-between" style={{ alignItems: 'center' }}>
                <span className="body">{m.label}</span>
                {m.isYou ? <Tag tone="info">You</Tag> : null}
              </div>
              <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
                {m.contribution}
              </p>
            </SpotlightCard>
          ))}
        </div>
      </div>

      <div>
        <p className="overline">Milestones</p>
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
      </div>
    </section>
  );
}
