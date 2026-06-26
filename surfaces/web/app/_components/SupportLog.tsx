'use client';

import { useState } from 'react';
import { Button, Icon, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { StatCell } from './StatCell';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { ReadSource } from '@/lib/vizData';
import {
  SUPPORT_STATUS_LABEL,
  SUPPORT_STATUS_TONE,
  supportCounts,
  type SupportLog as SupportLogData,
  type SupportStatus,
} from '@/lib/opsData';

/* ============================================================================
   SupportLog — the v2 Discipline Log, re-expressed NON-PUNITIVELY.

   Not a tally of punishments: a calm "support log" of patterns to notice, each
   routing to a human with a PREPARED restorative step that waits for approval —
   never an auto-applied consequence, never a score. The counts read as "needs a
   look" / "being supported" / "resolved" (and a quiet "repeated" signal), never
   "offenders". The prepared step is held behind the permission ladder; a human
   confirms it.

   v3 grammar: evidence-first (an EvidenceDrawer on the read), plain language,
   one cool accent, depth = hairline + tonal, NO shadow, reduced-motion safe.
   ============================================================================ */

export interface SupportLogProps {
  data: SupportLogData;
  source?: ReadSource;
}

export function SupportLog({ data, source = 'fallback' }: SupportLogProps) {
  // Local "confirmed the prepared step" overlay — a human action.
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const counts = supportCounts(data);

  // Order: needs a look first, then being supported, then resolved.
  const order: Record<SupportStatus, number> = { 'needs-look': 0, supporting: 1, resolved: 2 };
  const sorted = [...data.entries].sort((a, b) => order[a.status] - order[b.status]);

  if (data.entries.length === 0) {
    return (
      <div className="stack" style={{ gap: 'var(--space-4)' }}>
        <div className="empty">
          <Icon name="success" size="lg" className="glyph" />
          <h4 className="body">Nothing needs a look</h4>
          <p>No patterns are open in the support log right now. This is a calm record, kept ready in case one recurs.</p>
        </div>
        <SourceNote source={source} />
      </div>
    );
  }

  return (
    <div className="stack" style={{ gap: 'var(--space-5)' }}>
      <Matrix columns={4}>
        <StatCell label="Needs a look" value={counts.needsLook} delta="surfaced, not judged" tone={counts.needsLook > 0 ? 'down' : 'flat'} />
        <StatCell label="Being supported" value={counts.supporting} delta="a human is on it" tone="flat" />
        <StatCell label="Repeated" value={counts.repeated} delta="a pattern, not a verdict" tone={counts.repeated > 0 ? 'down' : 'flat'} />
        <StatCell label="Resolved" value={counts.resolved} delta="closed for now" tone="up" />
      </Matrix>

      <div className="stack" style={{ gap: 'var(--space-3)' }}>
        {sorted.map((e) => {
          const isConfirmed = confirmed[e.id] ?? false;
          const actionable = e.status !== 'resolved';
          return (
            <SpotlightCard key={e.id}>
              <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
                <div>
                  <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
                    <h3 className="body-lg" style={{ margin: 0 }}>{e.learner}</h3>
                    {e.repeated ? <Tag tone="warning">Repeated</Tag> : null}
                  </div>
                  <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>{e.pattern}</p>
                </div>
                <Tag tone={SUPPORT_STATUS_TONE[e.status]} dot>{SUPPORT_STATUS_LABEL[e.status]}</Tag>
              </div>

              <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
                <span className="quiet">Prepared step. </span>{e.preparedStep}
              </p>
              <p className="caption muted" style={{ marginTop: 'var(--space-1)' }}>Held by {e.heldBy}</p>

              {actionable ? (
                <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                  {isConfirmed ? (
                    <span className="body-sm row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                      <Icon name="check" size="sm" style={{ color: 'var(--success)' }} />
                      Step confirmed — {e.heldBy} will follow it through.
                    </span>
                  ) : (
                    <>
                      <Button variant="accent" size="sm" onClick={() => setConfirmed((p) => ({ ...p, [e.id]: true }))}>
                        Confirm the prepared step
                      </Button>
                      <span className="caption muted">It waits for you — nothing is applied on its own.</span>
                    </>
                  )}
                </div>
              ) : null}

              <EvidenceDrawer
                evidence={[
                  'Drawn from engagement and attendance signals against this learner’s own baseline — a pattern to notice, never a label.',
                  'The step is restorative and prepared, not a punishment; it routes to a human and waits for approval.',
                ]}
                whySeeing="Behaviour is read calmly and non-punitively: the aim is to understand and support early, never to tally or penalise."
              />
            </SpotlightCard>
          );
        })}
      </div>

      <p className="caption quiet" style={{ margin: 0 }}>
        This is a support log, not a punishment record. Every step is restorative, routes to a human,
        and waits for approval. Nothing is applied automatically.
      </p>

      <SourceNote source={source} />
    </div>
  );
}
