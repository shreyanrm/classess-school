'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Button, ConfidenceBand, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { ChildSwitcher } from '../_components/ChildSwitcher';
import { ConsentGated } from '../_components/ConsentGated';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import {
  DEFAULT_CHILD_ID,
  findChild,
  selectChildData,
  TONE_TAG,
  type ParentBriefing,
} from '@/lib/parentData';

/**
 * The Parent Today — three actions that need attention this week, in the
 * parent's language. Calm, never a dashboard, never surveillance. The Child
 * switcher re-renders the whole view for the selected child; a child whose view
 * is not consented shows the consent-gated state instead of data.
 */
export default function ParentTodayPage() {
  const [childId, setChildId] = useState(DEFAULT_CHILD_ID);
  const child = findChild(childId);
  const data = useMemo(() => selectChildData(childId), [childId]);

  return (
    <SurfaceShell
      eyebrow="This week"
      title="Welcome. Here is a calm look at this week."
      dockIntro="This is a calm view for your family. Ask how a child is doing, what to support at home, or to see a recent win."
      dockChips={['How is my child this week', 'What needs attention', 'Show a recent win']}
    >
      <section className="stack">
        <p className="overline">Whose week are we looking at</p>
        <ChildSwitcher selectedId={childId} onSelect={setChildId} />
      </section>

      {!child || !data ? (
        <ConsentGated label={child?.label} />
      ) : (
        <>
          <section className="stack">
            <p className="overline">Three things this week</p>
            <p className="caption quiet">
              A short, honest list for {child.label}. Nothing here is urgent or alarming — it is
              where a little attention helps most.
            </p>
            {data.briefings.map((b) => (
              <ParentBriefingCard key={b.id} briefing={b} />
            ))}
          </section>

          <section className="stack">
            <p className="overline">Where to go next</p>
            <div className="parent-links">
              <Link href="/parent/child" className="card parent-link c-spot">
                <Icon name="chart" size="md" />
                <div>
                  <div className="body">The child view</div>
                  <div className="caption muted">Progress, strengths and support areas</div>
                </div>
                <Icon name="chevron-right" size="sm" />
              </Link>
              <Link href="/parent/reports" className="card parent-link c-spot">
                <Icon name="book" size="md" />
                <div>
                  <div className="body">Reports and feedback</div>
                  <div className="caption muted">Celebration points and next steps</div>
                </div>
                <Icon name="chevron-right" size="sm" />
              </Link>
              <Link href="/parent/together" className="card parent-link c-spot">
                <Icon name="spark" size="md" />
                <div>
                  <div className="body">Learn alongside and PTM</div>
                  <div className="caption muted">Activities for home and meeting prep</div>
                </div>
                <Icon name="chevron-right" size="sm" />
              </Link>
            </div>
          </section>

          <section className="stack">
            <p className="caption quiet row" style={{ gap: 'var(--space-2)' }}>
              <Icon name="info" size="sm" />
              You see only what {child.label}&apos;s school has chosen to share with you. This is a
              partnership, not a watch list.
            </p>
          </section>
        </>
      )}
    </SurfaceShell>
  );
}

/** A single Today item, in the parent's language. Supportive, never an order. */
function ParentBriefingCard({ briefing }: { briefing: ParentBriefing }) {
  const [deferred, setDeferred] = useState(false);

  if (deferred) {
    return (
      <SpotlightCard>
        <div className="row-between">
          <span className="muted body-sm">Set aside — {briefing.title}</span>
          <Button variant="ghost" size="sm" onClick={() => setDeferred(false)}>
            Bring back
          </Button>
        </div>
      </SpotlightCard>
    );
  }

  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <h3 className="body-lg" style={{ margin: 0 }}>
          {briefing.title}
        </h3>
        <Tag tone={TONE_TAG[briefing.tone]}>
          {briefing.tone === 'celebrate'
            ? 'A win'
            : briefing.tone === 'support'
              ? 'A little help'
              : 'On track'}
        </Tag>
      </div>

      <div className="row" style={{ marginTop: 'var(--space-3)', color: 'var(--text-secondary)' }}>
        <span className="row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="clock" size="sm" />
          <span className="caption">About {briefing.minutes} min</span>
        </span>
      </div>

      <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
        <span className="quiet">Why. </span>
        {briefing.why}
      </p>
      <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
        <span className="quiet">It helps build. </span>
        {briefing.builds}
      </p>

      <div className="rec-meta">
        <div>
          <div className="k">Confidence</div>
          <div className="v">
            <ConfidenceBand level={briefing.confidence} />
          </div>
        </div>
        <div>
          <div className="k">Owner</div>
          <div className="v">{briefing.owner}</div>
        </div>
        <div>
          <div className="k">Best by</div>
          <div className="v">{briefing.due}</div>
        </div>
        <div>
          <div className="k">If left</div>
          <div className="v">{briefing.consequence}</div>
        </div>
      </div>

      <EvidenceDrawer evidence={briefing.evidence} whySeeing={briefing.whySeeing} />

      <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
        <Link href={briefing.target} className="btn btn-primary btn-sm row" style={{ gap: 'var(--space-2)' }}>
          {briefing.nextAction}
          <Icon name="arrow-right" size="sm" />
        </Link>
        <Button variant="ghost" size="sm" onClick={() => setDeferred(true)}>
          Set aside
        </Button>
      </div>
    </SpotlightCard>
  );
}
