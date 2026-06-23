'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button, ConfidenceBand, Icon, SpotlightCard, Tag } from '@classess/design-system';
import type { AdminBriefing } from '@/lib/mock';
import { EvidenceDrawer } from './EvidenceDrawer';

const TONE_TAG: Record<AdminBriefing['tone'], { tone: 'info' | 'warning' | 'danger' | 'success'; label: string }> = {
  info: { tone: 'info', label: 'For your support' },
  warning: { tone: 'warning', label: 'Needs attention' },
  danger: { tone: 'danger', label: 'Acting now' },
  success: { tone: 'success', label: 'Improved' },
};

export interface AdminBriefingCardProps {
  briefing: AdminBriefing;
}

/**
 * The admin Today unit — a single attention item rendered for review. It states
 * what needs attention, who owns it, and the one next action. It never acts on
 * its own; the action opens the relevant view where a human decides.
 */
export function AdminBriefingCard({ briefing }: AdminBriefingCardProps) {
  const [deferred, setDeferred] = useState(false);
  const tag = TONE_TAG[briefing.tone];

  if (deferred) {
    return (
      <SpotlightCard>
        <div className="row-between">
          <span className="muted body-sm">Deferred — {briefing.title}</span>
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
        <Tag tone={tag.tone} dot>
          {tag.label}
        </Tag>
      </div>

      <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
        {briefing.detail}
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
          <div className="k">Due</div>
          <div className="v">{briefing.due}</div>
        </div>
        <div>
          <div className="k">If ignored</div>
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
          Defer
        </Button>
      </div>
    </SpotlightCard>
  );
}
