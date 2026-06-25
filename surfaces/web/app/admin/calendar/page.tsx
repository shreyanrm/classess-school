'use client';

import { useState } from 'react';
import { Button, ConfidenceBand, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SCHEDULE_ALTERNATIVES, SUBSTITUTION_NEED } from '@/lib/mock';
import { useSurfaceState } from '@/lib/useSurfaceState';

type Decision = 'pending' | 'approved' | 'declined';

/**
 * Calendar and timetable — generation and substitution. When a slot needs
 * cover, the platform proposes SCORED ALTERNATIVES with a plain-language fit and
 * tradeoff. Each carries an Approval control: it never auto-commits. The human
 * picks and approves; only then is the change prepared to run.
 */
export default function AdminCalendarPage() {
  const [chosen, setChosen] = useState<string | null>(null);
  const [decision, setDecision] = useState<Decision>('pending');
  const surface = useSurfaceState();

  return (
    <SurfaceShell
      eyebrow="Calendar and timetable"
      title="Cover for an open slot"
      dockIntro="A teacher in Section 10-B is on approved leave on Thursday. I have scored three alternatives. Pick one and approve it; I will not commit anything on my own."
      dockChips={['Why is option one the best fit', 'Show the full week', 'Generate a fresh timetable']}
    >
      {surface.phase !== 'ready' ? (
        <ReadStates phase={surface.phase} onRetry={surface.refresh} />
      ) : (
      <>
      <SpotlightCard>
        <p className="overline">The need</p>
        <p className="body" style={{ marginTop: 'var(--space-2)' }}>
          {SUBSTITUTION_NEED.context}
        </p>
      </SpotlightCard>

      <section className="stack">
        <p className="overline">Scored alternatives</p>
        <p className="caption quiet">
          Ranked by fit. Selecting one stages it; it is committed only when you approve.
        </p>

        {SCHEDULE_ALTERNATIVES.map((alt, i) => {
          const selected = chosen === alt.id;
          return (
            <SpotlightCard key={alt.id} padLg className={selected ? 'is-selected' : undefined}>
              <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
                <h3 className="body-lg" style={{ margin: 0 }}>
                  <span className="quiet">Option {i + 1}. </span>
                  {alt.summary}
                </h3>
                <ConfidenceBand level={alt.fit} label={`${alt.fit === 'high' ? 'Strong' : alt.fit === 'middle' ? 'Workable' : 'Weak'} fit`} />
              </div>

              <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
                <span className="quiet">Why it fits. </span>
                {alt.fitNote}
              </p>
              <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
                <span className="quiet">Tradeoff. </span>
                {alt.tradeoff}
              </p>

              <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                <Button
                  variant={selected ? 'primary' : 'secondary'}
                  size="sm"
                  onClick={() => {
                    setChosen(alt.id);
                    setDecision('pending');
                  }}
                >
                  {selected ? (
                    <>
                      <Icon name="check" size="sm" />
                      Selected
                    </>
                  ) : (
                    'Select this option'
                  )}
                </Button>
              </div>
            </SpotlightCard>
          );
        })}
      </section>

      <section>
        <SpotlightCard padLg>
          <p className="overline">Approval</p>
          {!chosen ? (
            <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
              Select an option above to review it for approval. Nothing is committed until you approve.
            </p>
          ) : decision === 'pending' ? (
            <>
              <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
                You are about to approve{' '}
                <strong>{SCHEDULE_ALTERNATIVES.find((a) => a.id === chosen)?.summary}</strong>. This
                updates the timetable for the affected sections and notifies the staff involved.
              </p>
              <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                <Button variant="accent" size="sm" onClick={() => setDecision('approved')}>
                  Approve and apply
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setDecision('declined')}>
                  Decline
                </Button>
              </div>
            </>
          ) : (
            <div className="row-between" style={{ marginTop: 'var(--space-2)' }}>
              <span className="body-sm">
                {decision === 'approved'
                  ? 'Approved. The change is prepared to apply and the staff involved will be notified.'
                  : 'Declined. The slot stays open; you can pick another option.'}
              </span>
              <Tag tone={decision === 'approved' ? 'success' : 'neutral'} dot>
                {decision === 'approved' ? 'Approved' : 'Declined'}
              </Tag>
            </div>
          )}
        </SpotlightCard>
      </section>
      </>
      )}
    </SurfaceShell>
  );
}
