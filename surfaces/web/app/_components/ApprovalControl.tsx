'use client';

import { useState } from 'react';
import { Button, SpotlightCard, Tag } from '@classess/design-system';
import { useEmit } from '@/lib/useEmit';
import { useStore } from '@/lib/useStore';
import { EVENT_PURPOSE, type EventPurpose } from '@/lib/events';
import { EvidenceDrawer } from './EvidenceDrawer';

/* ============================================================================
   ApprovalControl — the permission ladder made visible (component library §
   ApprovalControl, invariant 8).

   Wraps anything consequential — send / submit / publish / delete / charge /
   GRADE. The action is PREPARED, not fired; nothing consequential happens until
   the human approves. On approval it:
     - emits a clean, attributed, consent-stamped audit event (who + when, via
       the opaque account id), and
     - records who approved + when on the card, to audit.

   v4.1 tokens only; no shadow. Reused across the teacher loop surfaces.
   ============================================================================ */

export interface ApprovalControlProps {
  /** Eyebrow — what kind of consequential action this is. */
  kind: string;
  /** One-line summary of the PREPARED action. */
  summary: string;
  /** The consequence of approving — what actually happens to whom. */
  consequence: string;
  /** Evidence lines for the EvidenceDrawer (why this is prepared this way). */
  evidence?: string[];
  /** Plain-language "why you are seeing this". */
  whySeeing?: string;
  /** The audit event type, e.g. 'score', 'plan.submitted', 'assignment.created'. */
  eventType: string;
  /** The purpose the audit event serves (gates the governed write). */
  purpose?: EventPurpose;
  /** Extra, non-PII payload for the audit event. */
  payload?: Record<string, unknown>;
  /** The approve button label. */
  approveLabel?: string;
  /** Called AFTER the human approves and the audit event is emitted. */
  onApprove?: () => void;
  /** Called when the teacher chooses Adjust (route back to compose). */
  onAdjust?: () => void;
  /** Called when the teacher declines. */
  onDecline?: () => void;
}

type Decision = 'pending' | 'approved' | 'declined';

export function ApprovalControl({
  kind,
  summary,
  consequence,
  evidence,
  whySeeing,
  eventType,
  purpose = EVENT_PURPOSE.teaching,
  payload,
  approveLabel = 'Approve',
  onApprove,
  onAdjust,
  onDecline,
}: ApprovalControlProps) {
  const { account } = useStore();
  const { emit } = useEmit();
  const [decision, setDecision] = useState<Decision>('pending');
  const [approvedAt, setApprovedAt] = useState<string | null>(null);

  async function approve() {
    const when = new Date();
    // The audit event: attributed (opaque account id), consent-stamped (purpose).
    await emit({
      type: eventType,
      purpose,
      payload: { ...payload, approved: true, approvedAtMs: when.getTime() },
    });
    setApprovedAt(when.toLocaleString());
    setDecision('approved');
    onApprove?.();
  }

  const approver = account?.role ? `You (${account.role})` : 'You';

  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start' }}>
        <div>
          <p className="overline" style={{ margin: 0 }}>
            {kind}
          </p>
          <h3 className="body-lg" style={{ margin: '4px 0 0' }}>
            {summary}
          </h3>
        </div>
        <Tag tone={decision === 'approved' ? 'success' : decision === 'declined' ? 'neutral' : 'info'}>
          {decision === 'approved'
            ? 'Approved'
            : decision === 'declined'
              ? 'Declined'
              : 'Prepared — awaiting approval'}
        </Tag>
      </div>

      <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
        <strong>If approved: </strong>
        {consequence}
      </p>

      {evidence && evidence.length > 0 ? (
        <EvidenceDrawer evidence={evidence} whySeeing={whySeeing} />
      ) : null}

      <div className="divider" />

      {decision === 'pending' ? (
        <div className="rec-actions">
          <Button variant="accent" size="sm" onClick={approve}>
            {approveLabel}
          </Button>
          {onAdjust ? (
            <Button variant="secondary" size="sm" onClick={onAdjust}>
              Adjust
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setDecision('declined');
              onDecline?.();
            }}
          >
            Decline
          </Button>
          <span className="caption muted">
            Nothing fires until you approve. You hold the authority — this is the permission ladder.
          </span>
        </div>
      ) : decision === 'approved' ? (
        <div className="rec-actions">
          <Tag tone="success">Approved</Tag>
          <span className="caption muted">
            {approver}, {approvedAt}. An audit event was recorded.
          </span>
          <Button variant="ghost" size="sm" onClick={() => setDecision('pending')}>
            Undo
          </Button>
        </div>
      ) : (
        <div className="rec-actions">
          <span className="body-sm">Declined. Nothing was sent.</span>
          <Button variant="ghost" size="sm" onClick={() => setDecision('pending')}>
            Undo
          </Button>
        </div>
      )}
    </SpotlightCard>
  );
}
