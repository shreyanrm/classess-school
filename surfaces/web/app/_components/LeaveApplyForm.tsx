'use client';

/* ============================================================================
   LeaveApplyForm — the REQUESTER side of leave (teacher / student).

   The admin already has the approval QUEUE (LeaveBoard, lib/opsData). This is
   the other half: a calm form a teacher or student fills to APPLY for leave,
   which routes to that queue via the permission ladder. It never decides
   anything — it records what was asked for (kind, span, days, reason), persists
   it to the store (submitLeaveApplication), and shows the requester their own
   applications with a plain "awaiting a decision" status.

   v3 grammar: chip selects (no raw form-feel), a calm reason field, evidence of
   WHERE it routed (the ladder names who decides), no auto-anything, five states
   designed (empty / drafting / submitting / submitted+listed / declined-by-rule
   when the form is incomplete), one cool accent, hairline + tonal, NO shadow,
   reduced-motion safe.
   ============================================================================ */

import { useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import { useStore } from '@/lib/useStore';
import {
  submitLeaveApplication,
  withdrawLeaveApplication,
  type LeaveApplication,
  type LeaveApplicationKind,
} from '@/lib/store';

const KIND_LABEL: Record<LeaveApplicationKind, string> = {
  casual: 'Casual',
  sick: 'Sick',
  duty: 'On duty',
  family: 'Family',
};

const KIND_OPTIONS: LeaveApplicationKind[] = ['casual', 'sick', 'duty', 'family'];

/** Day-span chips → a plain "from -> to" token + a working-day count. */
const SPAN_OPTIONS: Array<{ id: string; label: string; span: string; days: number }> = [
  { id: 'half', label: 'Half day', span: 'one half day', days: 1 },
  { id: 'one', label: 'One day', span: 'one day', days: 1 },
  { id: 'two', label: 'Two days', span: 'two days', days: 2 },
  { id: 'three', label: 'Three days', span: 'three days', days: 3 },
  { id: 'week', label: 'A week', span: 'about a week', days: 5 },
];

export interface LeaveApplyFormProps {
  /** Who is applying — drives the routing copy and the persisted `who`. */
  who: 'staff' | 'student';
}

export function LeaveApplyForm({ who }: LeaveApplyFormProps) {
  const { leaveApplications } = useStore();
  const mine = leaveApplications ?? [];

  const [kind, setKind] = useState<LeaveApplicationKind | null>(null);
  const [spanId, setSpanId] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  // A brief, plain confirmation after a submit — the calm "it's at the gate" beat.
  const [justSent, setJustSent] = useState<LeaveApplication | null>(null);

  const spanOpt = SPAN_OPTIONS.find((o) => o.id === spanId) ?? null;
  const ready = kind != null && spanOpt != null && reason.trim().length >= 4;

  function submit() {
    if (!ready || !kind || !spanOpt) return;
    const application = submitLeaveApplication({
      who,
      kind,
      span: spanOpt.span,
      days: spanOpt.days,
      reason: reason.trim(),
    });
    setJustSent(application);
    setKind(null);
    setSpanId(null);
    setReason('');
  }

  return (
    <div className="stack" style={{ gap: 'var(--space-5)' }}>
      {/* ── The application form ─────────────────────────────────────────── */}
      <SpotlightCard>
        <div className="sec-head" style={{ marginBottom: 'var(--space-3)' }}>
          <h3 className="h4" style={{ margin: 0 }}>Apply for leave</h3>
          <span className="overline">routes to approval</span>
        </div>

        <div className="stack" style={{ gap: 'var(--space-4)' }}>
          <div className="stack" style={{ gap: 'var(--space-2)' }}>
            <span className="field-label" id="leave-kind-label">Kind of leave</span>
            <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }} role="radiogroup" aria-labelledby="leave-kind-label">
              {KIND_OPTIONS.map((k) => (
                <Button
                  key={k}
                  variant={kind === k ? 'primary' : 'secondary'}
                  size="sm"
                  role="radio"
                  aria-checked={kind === k}
                  data-testid="leave-kind-option"
                  onClick={() => setKind(k)}
                >
                  {KIND_LABEL[k]}
                </Button>
              ))}
            </div>
          </div>

          <div className="stack" style={{ gap: 'var(--space-2)' }}>
            <span className="field-label" id="leave-span-label">How long</span>
            <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }} role="radiogroup" aria-labelledby="leave-span-label">
              {SPAN_OPTIONS.map((o) => (
                <Button
                  key={o.id}
                  variant={spanId === o.id ? 'primary' : 'secondary'}
                  size="sm"
                  role="radio"
                  aria-checked={spanId === o.id}
                  data-testid="leave-span-option"
                  onClick={() => setSpanId(o.id)}
                >
                  {o.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="stack" style={{ gap: 'var(--space-2)' }}>
            <label className="field-label" htmlFor="leave-reason">A short reason</label>
            <textarea
              id="leave-reason"
              className="notes-textarea"
              style={{ minHeight: 88 }}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="In your own words — for example, a family event out of town."
              data-testid="leave-reason"
              aria-describedby="leave-reason-help"
            />
            <p className="caption quiet" id="leave-reason-help" style={{ margin: 0 }}>
              Your words, kept as-is. No personal details are needed — only what helps the decision.
            </p>
          </div>

          <div className="rec-actions" style={{ alignItems: 'center' }}>
            <Button variant="accent" size="sm" disabled={!ready} onClick={submit} data-testid="leave-submit">
              <Icon name="check" size="sm" />
              Send to approval
            </Button>
            {!ready ? (
              <span className="caption muted" role="status">
                Pick a kind, a length, and add a short reason to send.
              </span>
            ) : (
              <span className="caption muted">
                {spanOpt?.days} {spanOpt && spanOpt.days === 1 ? 'day' : 'days'} · held for a human to decide
              </span>
            )}
          </div>
        </div>
      </SpotlightCard>

      {/* ── The "it's at the gate" confirmation (drops away on next action) ── */}
      {justSent ? (
        <SpotlightCard className="is-selected" data-testid="leave-sent">
          <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
            <Icon name="check" size="sm" style={{ color: 'var(--accent)' }} />
            <span className="body-sm" style={{ fontWeight: 500 }}>Your application is at the approval gate.</span>
          </div>
          <p className="caption" style={{ marginTop: 'var(--space-2)' }}>
            {KIND_LABEL[justSent.kind]} leave · {justSent.span}. It is now in the approval queue, awaiting a
            decision. Nothing is approved on its own — you will see the outcome here.
          </p>
          <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
            <Button variant="ghost" size="sm" onClick={() => setJustSent(null)}>Dismiss</Button>
          </div>
        </SpotlightCard>
      ) : null}

      {/* ── The requester's own applications, with status ──────────────────── */}
      <div className="stack" style={{ gap: 'var(--space-3)' }}>
        <div className="sec-head">
          <h3 className="h4" style={{ margin: 0 }}>Your applications</h3>
          <span className="overline">{mine.length} sent</span>
        </div>

        {mine.length === 0 ? (
          <div className="panel" style={{ textAlign: 'center', padding: 'var(--space-6)' }} data-testid="leave-empty">
            <Icon name="calendar" size="md" style={{ color: 'var(--text-tertiary)' }} />
            <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>You have not applied for any leave yet.</p>
            <p className="caption quiet" style={{ marginTop: 'var(--space-1)' }}>
              When you send one, it appears here with its status.
            </p>
          </div>
        ) : (
          mine.map((a) => (
            <SpotlightCard key={a.id} data-testid="leave-row">
              <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
                <div style={{ minWidth: 0 }}>
                  <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
                    <h4 className="body-lg" style={{ margin: 0 }}>{KIND_LABEL[a.kind]} leave</h4>
                    <span className="caption muted">{a.span} · {a.days} {a.days === 1 ? 'day' : 'days'}</span>
                  </div>
                  <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>{a.reason}</p>
                </div>
                <Tag tone="info" dot>Awaiting a decision</Tag>
              </div>
              <div className="rec-actions" style={{ marginTop: 'var(--space-3)', alignItems: 'center' }}>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => withdrawLeaveApplication(a.id)}
                  data-testid="leave-withdraw"
                >
                  Withdraw
                </Button>
                <span className="caption quiet">You can withdraw it any time before it is decided.</span>
              </div>
            </SpotlightCard>
          ))
        )}
      </div>

      {/* ── Where it routes — the permission ladder, named ──────────────────── */}
      <SpotlightCard>
        <div className="sec-head" style={{ marginBottom: 'var(--space-2)' }}>
          <h4 className="h4" style={{ margin: 0 }}>Where this goes</h4>
          <Tag tone="info" dot>prepare → approve</Tag>
        </div>
        <p className="body-sm" style={{ margin: 0 }}>
          A short leave is cleared by a coordinator; a longer or overlapping one is held for the
          principal. {who === 'staff' ? 'You may be asked whether cover is arranged.' : 'A guardian request stands behind a student leave.'} Nothing is
          approved automatically — the decision is a human’s, and you will see the outcome here.
        </p>
        <EvidenceDrawer
          evidence={[
            'Your application is queued for the approval ladder — it is recorded, never auto-decided.',
            who === 'staff'
              ? 'A coordinator clears a short leave; a long or overlapping one is held for the principal, who also checks cover.'
              : 'A coordinator clears a short student leave; a longer one is held for the principal.',
          ]}
          whySeeing="Leave routes through the permission ladder so a human always decides, with the full picture — the platform only prepares and queues your request."
        />
      </SpotlightCard>
    </div>
  );
}
