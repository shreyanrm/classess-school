'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button, ConfidenceBand, Icon, SpotlightCard } from '@classess/design-system';
import type { Briefing } from '@/lib/mock';
import { EvidenceDrawer } from './EvidenceDrawer';

export interface BriefingCardProps {
  briefing: Briefing;
}

/**
 * The Today unit. One attention item: title, the one next action, time
 * estimate, why it is recommended, the progress it creates. Action button plus
 * defer. One screen, one intention, one next action.
 */
export function BriefingCard({ briefing }: BriefingCardProps) {
  const [deferred, setDeferred] = useState(false);

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
      <h3 className="body-lg" style={{ margin: 0 }}>
        {briefing.title}
      </h3>

      <div className="row" style={{ marginTop: 'var(--space-3)', color: 'var(--text-secondary)' }}>
        <span className="row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="clock" size="sm" />
          <span className="caption">{briefing.minutes} min</span>
        </span>
      </div>

      <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
        <span className="quiet">Why. </span>
        {briefing.why}
      </p>
      <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
        <span className="quiet">Builds. </span>
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
