'use client';

import { useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { issueCredential, type CredentialView } from '@/lib/portfolioData';
import { EvidenceDrawer } from './EvidenceDrawer';

const STATE_TONE = {
  draft: 'neutral',
  verified: 'success',
  revoked: 'warning',
} as const;

export interface CredentialItemProps {
  credential: CredentialView;
}

/**
 * One verifiable credential. A credential is `verified` (tamper-evident) only
 * when actually signed; a draft is explicitly NOT verifiable — never faked.
 * Issuing is CONSEQUENTIAL and permission-laddered: a draft offers an explicit
 * issue act that the learner confirms, and it only becomes verified when a
 * signing key is configured. Plain language throughout.
 */
export function CredentialItem({ credential }: CredentialItemProps) {
  const [view, setView] = useState<CredentialView>(credential);
  const [confirming, setConfirming] = useState(false);

  function confirmIssue() {
    setView((v) => issueCredential(v));
    setConfirming(false);
  }

  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
        <div>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {view.title}
          </h3>
          <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
            {view.topicNames.join(' · ')}
          </p>
        </div>
        <Tag tone={STATE_TONE[view.state]}>{view.stateLabel}</Tag>
      </div>

      <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
        {view.claim}
      </p>
      <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
        {view.issued}
      </p>

      <div style={{ marginTop: 'var(--space-3)' }}>
        <EvidenceDrawer
          evidence={view.evidence}
          whySeeing={
            view.verifiable
              ? 'This credential is signed and tamper-evident — anyone you share it with can verify it independently.'
              : 'A credential is only verifiable once it is signed. Until you issue it, it stays a draft — a signature is never faked.'
          }
        />
      </div>

      {view.state === 'verified' ? (
        <div className="row caption" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-3)', color: 'var(--text-secondary)' }}>
          <Icon name="check" size="sm" />
          Verifiable and tamper-evident
        </div>
      ) : null}

      {view.state === 'draft' ? (
        <>
          <div className="divider" />
          {confirming ? (
            <div className="rec-actions">
              <Button variant="accent" size="sm" onClick={confirmIssue}>
                Yes, issue it
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setConfirming(false)}>
                Not now
              </Button>
              <span className="caption muted">Issuing is your decision — it is held until you confirm.</span>
            </div>
          ) : (
            <div className="rec-actions">
              <Button variant="primary" size="sm" onClick={() => setConfirming(true)}>
                Issue this credential
                <Icon name="arrow-right" size="sm" />
              </Button>
              <span className="caption muted">You will be asked to confirm — nothing issues on its own.</span>
            </div>
          )}
        </>
      ) : null}
    </SpotlightCard>
  );
}
