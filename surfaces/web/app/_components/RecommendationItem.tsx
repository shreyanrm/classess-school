'use client';

import { useState } from 'react';
import { Button, ConfidenceBand, CrystallizeNode, SpotlightCard, Tag } from '@classess/design-system';
import type { Recommendation } from '@/lib/mock';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import type { Decision } from '@/lib/useProactive';
import { EvidenceDrawer } from './EvidenceDrawer';
import { ApprovalControl } from './ApprovalControl';

type Phase = 'pending' | 'approving' | 'adjusting' | 'committed' | 'resolved' | 'declined';

export interface RecommendationItemProps {
  rec: Recommendation;
  /**
   * Commit the human decision through the proactive loop (the wall authorizes,
   * the route records the outcome). Provided by the surface that owns the feed
   * hook (lib/useProactive). When absent the card runs in a local-only preview.
   */
  onActioned?: (id: string, decision: Decision, consequential?: boolean) => Promise<{
    committed: boolean;
    denied?: boolean;
    outcome?: string;
  }>;
}

/**
 * The manage-by-exception primitive — the proactive loop made tappable (spec 13
 * b11, the permission ladder 11). Evidence summary, ConfidenceBand, owner, due,
 * consequence of ignoring, a "why am I seeing this" EvidenceDrawer, and a real
 * Approve / Adjust / Decline control that calls the recommend/approve/execute
 * endpoints:
 *
 *   - CONSEQUENTIAL actions (send/submit/publish/delete/charge/grade) raise the
 *     ApprovalControl and commit ONLY on Approve (the wall enforces the ladder).
 *   - REVERSIBLE / safe-automatic actions execute directly and offer an UNDO
 *     toast — nothing here is irreversible without a human approval step.
 *   - When executing closes a learner's gap into INDEPENDENT MASTERY, the
 *     CrystallizeNode moment plays and a `gap.resolved` line appears.
 *
 * Every commit emits the attributed, consent-stamped `recommendation.actioned`
 * audit event. Tokens only; no shadow.
 */
export function RecommendationItem({ rec, onActioned }: RecommendationItemProps) {
  const { emit } = useEmit();
  const [phase, setPhase] = useState<Phase>('pending');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The attributed, consent-stamped audit event for a committed decision. The
  // outcome closes the loop (observe -> ... -> outcome -> learn). Never PII.
  async function recordOutcome(decision: Decision) {
    await emit({
      type: 'recommendation.actioned',
      purpose: EVENT_PURPOSE.teaching,
      payload: { recommendationId: rec.id, decision, gapType: rec.gapType },
    });
  }

  // Reversible / safe-automatic path: execute directly, offer undo. Consequential
  // actions never reach here — they go through the ApprovalControl below.
  async function executeReversible() {
    setBusy(true);
    setError(null);
    const result = onActioned
      ? await onActioned(rec.id, 'execute', false)
      : { committed: true };
    setBusy(false);
    if (!result.committed) {
      setError('That did not go through. Nothing was changed — try again.');
      return;
    }
    await recordOutcome('execute');
    setPhase(rec.crystallizes ? 'resolved' : 'committed');
  }

  async function decline() {
    setBusy(true);
    if (onActioned) await onActioned(rec.id, 'decline', rec.consequential);
    setBusy(false);
    setPhase('declined');
  }

  function undo() {
    setPhase('pending');
    setError(null);
  }

  // The consequential path is the ApprovalControl itself — it owns Approve /
  // Adjust / Decline, raises the prepared action, and commits only on Approve.
  if (rec.consequential && phase === 'approving') {
    return (
      <ApprovalControl
        kind={`${rec.gapType.replace('-', ' ')} gap · prepared`}
        summary={rec.title}
        consequence={rec.consequence}
        evidence={rec.evidence}
        whySeeing={rec.whySeeing}
        eventType="recommendation.actioned"
        purpose={EVENT_PURPOSE.teaching}
        payload={{ recommendationId: rec.id, decision: 'approve', gapType: rec.gapType }}
        approveLabel={rec.actionLabel}
        onApprove={async () => {
          // The REAL execute outcome drives the UI: a wall deny / unresolved
          // consequential op (committed:false) surfaces needs-approval, never a
          // false "Done". Only a committed loop shows resolved/committed.
          const result = onActioned
            ? await onActioned(rec.id, 'approve', true)
            : { committed: true };
          if (!result.committed) {
            setError('That needs approval to go through. Nothing was sent — try again.');
            setPhase('pending');
            return;
          }
          setError(null);
          setPhase(rec.crystallizes ? 'resolved' : 'committed');
        }}
        onAdjust={() => setPhase('pending')}
        onDecline={() => decline()}
      />
    );
  }

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

      {phase === 'pending' || phase === 'adjusting' ? (
        <>
          <div className="rec-actions">
            <Button
              variant="accent"
              size="sm"
              disabled={busy}
              onClick={() => (rec.consequential ? setPhase('approving') : executeReversible())}
            >
              {busy ? 'Working…' : rec.actionLabel}
            </Button>
            <Button variant="secondary" size="sm" disabled={busy} onClick={() => setPhase('adjusting')}>
              Adjust
            </Button>
            <Button variant="ghost" size="sm" disabled={busy} onClick={decline}>
              Decline
            </Button>
            {rec.consequential ? (
              <span className="caption muted">
                Consequential — this raises an approval step. Nothing fires until you approve.
              </span>
            ) : (
              <span className="caption muted">Reversible — you can undo it right after.</span>
            )}
          </div>
          {phase === 'adjusting' ? (
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              Adjust the plan in the conversation, then run it when it fits.
            </p>
          ) : null}
          {error ? (
            <p className="field-error" style={{ marginTop: 'var(--space-2)' }} role="alert">
              {error}
            </p>
          ) : null}
        </>
      ) : phase === 'resolved' ? (
        // The CrystallizeNode moment — a learner reached independent mastery.
        <div className="rec-resolved" role="status">
          <CrystallizeNode variant="b" inline resolved label={rec.crystallizes} />
          <div>
            <p className="body-sm" style={{ margin: 0 }}>
              <strong>Gap resolved. </strong>
              {rec.crystallizes}
            </p>
            <p className="caption muted" style={{ margin: '2px 0 0' }}>
              Done. An outcome was recorded — Vidya keeps watching to confirm it holds.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={undo}>
            Undo
          </Button>
        </div>
      ) : phase === 'committed' ? (
        <div className="rec-actions">
          <Tag tone="success">Done</Tag>
          <span className="body-sm">
            Prepared and waiting for you on the page — nothing was sent on its own.
          </span>
          <Button variant="ghost" size="sm" onClick={undo}>
            Undo
          </Button>
        </div>
      ) : (
        <div className="rec-actions">
          <span className="body-sm">Declined. This recommendation has been set aside.</span>
          <Button variant="ghost" size="sm" onClick={undo}>
            Undo
          </Button>
        </div>
      )}
    </SpotlightCard>
  );
}
