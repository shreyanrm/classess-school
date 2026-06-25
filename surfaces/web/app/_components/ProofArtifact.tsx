'use client';

import { useState } from 'react';
import { Button, CrystallizeNode, Icon, SpotlightCard, Tag } from '@classess/design-system';
import type { ProofArtifact as ProofArtifactData } from '@/lib/parentData';

export interface ProofArtifactProps {
  proof: ProofArtifactData;
  /**
   * Whether sharing is offered. Sharing is a deliberate, parent-initiated action
   * — it never auto-fires. Defaults to true on the parent surface.
   */
  shareable?: boolean;
  /**
   * Whose voice the copy speaks in. 'parent' (default) reads third-person about
   * the child; 'self' reads first-person for the learner's own portfolio, so a
   * student never sees themselves described in the third person.
   */
  voice?: 'parent' | 'self';
}

/**
 * The Proof artifact (parent) — a beautiful, shareable moment drawn from the
 * child's own learning. Child-triggerable ("show what I just cracked"). It is
 * pride, not surveillance: it celebrates one concrete thing the child can now
 * do on their own.
 *
 * The ignite signature lights only when the moment crossed into independent —
 * the one mastery moment ultramarine is reserved for. Sharing is an explicit
 * parent action; nothing leaves the surface on its own (consequential actions
 * never auto-fire).
 *
 * v4: sharp corners, no shadow, calm and spacious, one vivid accent.
 */
export function ProofArtifact({ proof, shareable = true, voice = 'parent' }: ProofArtifactProps) {
  const [shared, setShared] = useState(false);
  const self = voice === 'self';

  function shareMoment() {
    const text = `“${proof.headline}” — ${proof.topic}. ${proof.whatChanged}`;
    // A real share: the native share sheet where available, clipboard otherwise.
    const nav = typeof navigator !== 'undefined' ? navigator : undefined;
    if (nav?.share) {
      void nav.share({ title: 'A proud moment', text }).catch(() => {});
    } else if (nav?.clipboard?.writeText) {
      void nav.clipboard.writeText(text).catch(() => {});
    }
    setShared(true);
  }

  return (
    <SpotlightCard padLg className="proof-artifact" data-subject={proof.subject}>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <span className="overline">A proud moment</span>
        {proof.independent ? (
          <span className="ignite-row" aria-label="Now independent">
            <CrystallizeNode variant="b" inline resolved label="Now independent" />
          </span>
        ) : null}
      </div>

      <blockquote className="proof-headline display-sm" style={{ margin: 'var(--space-4) 0 0' }}>
        “{proof.headline}”
      </blockquote>

      <div className="row" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-4)' }}>
        <Tag tone="neutral">{proof.topic}</Tag>
        {proof.independent ? (
          <Tag tone="success">{self ? 'On your own' : 'On their own'}</Tag>
        ) : null}
      </div>

      <p className="body-sm" style={{ marginTop: 'var(--space-4)' }}>
        <span className="quiet">What changed. </span>
        {proof.whatChanged}
      </p>
      <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
        {proof.when}
      </p>

      {shareable ? (
        <div className="rec-actions" style={{ marginTop: 'var(--space-5)' }}>
          {shared ? (
            <span className="row body-sm" style={{ gap: 'var(--space-2)', color: 'var(--text-secondary)' }}>
              <Icon name="check" size="sm" />
              Shared. The moment is ready to send wherever you choose.
            </span>
          ) : (
            <Button variant="primary" size="sm" onClick={shareMoment}>
              Share this moment
              <Icon name="send" size="sm" />
            </Button>
          )}
        </div>
      ) : null}

      <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
        Drawn from {self ? 'your' : 'their'} own learning. Nothing is shared until you choose to.
      </p>
    </SpotlightCard>
  );
}
