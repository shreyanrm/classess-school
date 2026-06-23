'use client';

import { useState } from 'react';
import { Button, ConfidenceBand, SpotlightCard, Tag } from '@classess/design-system';
import type { Recommendation } from '@/lib/mock';
import { EvidenceDrawer } from './EvidenceDrawer';

type Decision = 'pending' | 'approved' | 'adjusting' | 'declined';

const DECISION_COPY: Record<Exclude<Decision, 'pending' | 'adjusting'>, string> = {
  approved: 'Approved. This is prepared and waiting for you to run it — nothing was sent on its own.',
  declined: 'Declined. This recommendation has been set aside.',
};

export interface RecommendationItemProps {
  rec: Recommendation;
}

/**
 * The manage-by-exception primitive. Evidence summary, confidence band, owner,
 * due date, consequence of ignoring, and an Approve / Adjust / Decline control.
 * The control NEVER auto-fires — human authority is preserved (the permission
 * ladder sits at Prepare; Execute happens only on explicit approval).
 */
export function RecommendationItem({ rec }: RecommendationItemProps) {
  const [decision, setDecision] = useState<Decision>('pending');

  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start' }}>
        <h3 className="body-lg" style={{ margin: 0 }}>
          {rec.title}
        </h3>
        <Tag tone="info">{rec.gapType.replace('-', ' ')} gap</Tag>
      </div>

      <p className="muted body-sm" style={{ marginTop: 'var(--space-3)' }}>
        {rec.evidenceSummary}
      </p>

      <div className="rec-meta">
        <div>
          <div className="k">Confidence</div>
          <div className="v">
            <ConfidenceBand level={rec.confidence} />
          </div>
        </div>
        <div>
          <div className="k">Owner</div>
          <div className="v">{rec.owner}</div>
        </div>
        <div>
          <div className="k">Due</div>
          <div className="v">{rec.due}</div>
        </div>
        <div>
          <div className="k">If ignored</div>
          <div className="v">{rec.consequence}</div>
        </div>
      </div>

      <EvidenceDrawer evidence={rec.evidence} whySeeing={rec.whySeeing} />

      <div className="divider" />

      {decision === 'pending' || decision === 'adjusting' ? (
        <div className="rec-actions">
          <Button variant="accent" size="sm" onClick={() => setDecision('approved')}>
            Approve
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setDecision('adjusting')}>
            Adjust
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setDecision('declined')}>
            Decline
          </Button>
          {decision === 'adjusting' ? (
            <span className="caption muted">
              Adjust the plan in the conversation, then approve when it fits.
            </span>
          ) : null}
        </div>
      ) : (
        <div className="rec-actions">
          <span className="body-sm">{DECISION_COPY[decision]}</span>
          <Button variant="ghost" size="sm" onClick={() => setDecision('pending')}>
            Undo
          </Button>
        </div>
      )}
    </SpotlightCard>
  );
}
