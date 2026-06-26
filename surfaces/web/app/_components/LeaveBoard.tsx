'use client';

import { useState } from 'react';
import { Button, Icon, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { StatCell } from './StatCell';
import { BottomSheet } from './BottomSheet';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { ReadSource } from '@/lib/vizData';
import {
  LEAVE_KIND_LABEL,
  LEAVE_TIER_LABEL,
  canDecideLeave,
  leaveCounts,
  type LeaveBoard as LeaveBoardData,
  type LeaveRequest,
  type LeaveStatus,
} from '@/lib/opsData';

/* ============================================================================
   LeaveBoard — the v2 Leave Management screen, in the v3 permission ladder.

   Counts (pending / flagged / approved / declined) as a count-up matrix, a calm
   request list, and a DETAIL DRAWER (BottomSheet) that carries the leave
   details + requester info + the approve / reject controls. The ladder gates
   the controls: a coordinator may clear a short leave; an overlapping / long one
   is held for the principal, and the surface disables the control when the
   caller's role is not on the tier's decider list. Nothing auto-approves — the
   approve/reject is a human's explicit act, and the decision persists upward.

   v3 grammar: evidence-first (an EvidenceDrawer on the flagged read), bands /
   plain language not raw scores, one cool accent, depth = hairline + tonal,
   NO shadow, reduced-motion safe.
   ============================================================================ */

const STATUS_TONE: Record<LeaveStatus, 'info' | 'warning' | 'success' | 'neutral'> = {
  pending: 'info',
  flagged: 'warning',
  approved: 'success',
  declined: 'neutral',
};

const STATUS_LABEL: Record<LeaveStatus, string> = {
  pending: 'Awaiting a decision',
  flagged: 'Needs a closer look',
  approved: 'Approved',
  declined: 'Declined',
};

export interface LeaveBoardProps {
  data: LeaveBoardData;
  source?: ReadSource;
  /** The caller's role — gates the approve/reject control via the ladder. */
  role?: string;
}

export function LeaveBoard({ data, source = 'fallback', role }: LeaveBoardProps) {
  // Local decision overlay — a real human action, optimistically reflected. In
  // production this persists through the wall; here it mutates the local read.
  const [decisions, setDecisions] = useState<Record<string, LeaveStatus>>({});
  const [openId, setOpenId] = useState<string | null>(null);

  const statusOf = (r: LeaveRequest): LeaveStatus => decisions[r.id] ?? r.status;
  const requests = data.requests.map((r) => ({ ...r, status: statusOf(r) }));
  const counts = leaveCounts({ ...data, requests });

  const open = openId ? requests.find((r) => r.id === openId) ?? null : null;
  const canDecide = open ? canDecideLeave(open.tier, role) : false;
  const isOpen = open != null && (open.status === 'pending' || open.status === 'flagged');

  function decide(id: string, status: LeaveStatus) {
    setDecisions((prev) => ({ ...prev, [id]: status }));
    setOpenId(null);
  }

  // Sort: things needing action first (flagged, then pending), then the rest.
  const order: Record<LeaveStatus, number> = { flagged: 0, pending: 1, approved: 2, declined: 3 };
  const sorted = [...requests].sort((a, b) => order[a.status] - order[b.status]);

  return (
    <div className="stack" style={{ gap: 'var(--space-5)' }}>
      <Matrix columns={4}>
        <StatCell label="Awaiting you" value={counts.pending} delta="held at the gate" tone={counts.pending > 0 ? 'down' : 'flat'} />
        <StatCell label="Needs a look" value={counts.flagged} delta="flagged, not blocked" tone={counts.flagged > 0 ? 'down' : 'flat'} />
        <StatCell label="Approved" value={counts.approved} delta="by a human" tone="up" />
        <StatCell label="Declined" value={counts.declined} delta="recorded" tone="flat" />
      </Matrix>

      <div className="stack" style={{ gap: 'var(--space-3)' }}>
        {sorted.map((r) => {
          const actionable = r.status === 'pending' || r.status === 'flagged';
          return (
            <SpotlightCard key={r.id} className={r.status === 'flagged' ? 'is-selected' : undefined}>
              <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
                <div>
                  <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center', flexWrap: 'wrap' }}>
                    <h3 className="body-lg" style={{ margin: 0 }}>{r.requester}</h3>
                    <Tag tone="neutral">{LEAVE_KIND_LABEL[r.kind]}</Tag>
                    <span className="caption muted">{r.span} · {r.days} {r.days === 1 ? 'day' : 'days'}</span>
                  </div>
                  <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>{r.reason}</p>
                  <p className="caption quiet" style={{ marginTop: 'var(--space-1)' }}>{LEAVE_TIER_LABEL[r.tier]}</p>
                </div>
                <Tag tone={STATUS_TONE[r.status]} dot>{STATUS_LABEL[r.status]}</Tag>
              </div>

              {r.flagNote ? (
                <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
                  <span className="quiet">Why flagged. </span>{r.flagNote}
                </p>
              ) : null}

              <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                <Button variant={actionable ? 'secondary' : 'ghost'} size="sm" onClick={() => setOpenId(r.id)}>
                  {actionable ? 'Review and decide' : 'View detail'}
                </Button>
                {!actionable && r.decidedBy ? (
                  <span className="caption muted">{r.status === 'approved' ? 'Approved' : 'Declined'} by {r.decidedBy}</span>
                ) : null}
              </div>
            </SpotlightCard>
          );
        })}
      </div>

      <p className="caption quiet" style={{ margin: 0 }}>
        Nothing approves on its own. Each decision is a human action gated by the permission ladder —
        a coordinator clears a short leave; an overlapping or long one is held for the principal.
      </p>

      <SourceNote source={source} />

      {/* The detail drawer — leave details + requester + approve/reject. */}
      <BottomSheet
        open={open != null}
        onClose={() => setOpenId(null)}
        eyebrow="Leave request"
        title={open?.requester ?? 'Leave request'}
        description={open ? `${LEAVE_KIND_LABEL[open.kind]} leave · ${open.span} · ${open.days} ${open.days === 1 ? 'day' : 'days'}` : undefined}
        data-testid="leave-detail-drawer"
        footer={
          open && isOpen ? (
            canDecide ? (
              <>
                <Button variant="accent" size="sm" onClick={() => decide(open.id, 'approved')} data-testid="leave-approve">
                  <Icon name="check" size="sm" />
                  Approve
                </Button>
                <Button variant="ghost" size="sm" onClick={() => decide(open.id, 'declined')} data-testid="leave-decline">
                  Decline
                </Button>
              </>
            ) : (
              <span className="caption muted" role="status">
                {LEAVE_TIER_LABEL[open.tier]} — your role cannot decide this tier. It stays held for them.
              </span>
            )
          ) : (
            <span className="caption muted">
              {open?.status === 'approved' ? 'Approved' : 'Declined'}
              {open?.decidedBy ? ` by ${open.decidedBy}` : ''} — recorded.
            </span>
          )
        }
      >
        {open ? (
          <div className="stack" style={{ gap: 'var(--space-4)' }}>
            <div className="stack" style={{ gap: 'var(--space-2)' }}>
              <p className="overline" style={{ margin: 0 }}>Requester</p>
              <p className="body-sm" style={{ margin: 0 }}>
                {open.requester} · {open.who === 'staff' ? 'Staff' : 'Student'}
              </p>
            </div>
            <div className="stack" style={{ gap: 'var(--space-2)' }}>
              <p className="overline" style={{ margin: 0 }}>Reason</p>
              <p className="body-sm" style={{ margin: 0 }}>{open.reason}</p>
            </div>
            {open.who === 'staff' ? (
              <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                <Icon name={open.coverArranged ? 'check' : 'clock'} size="sm" style={{ color: open.coverArranged ? 'var(--success)' : 'var(--text-tertiary)' }} />
                <span className="body-sm">{open.coverArranged ? 'Cover is already arranged.' : 'Cover is not arranged yet — worth checking before approving.'}</span>
              </div>
            ) : null}
            {open.flagNote ? (
              <SpotlightCard>
                <p className="overline" style={{ margin: 0 }}>Flagged for a look</p>
                <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>{open.flagNote}</p>
                <EvidenceDrawer
                  evidence={[
                    'Flagged from the calendar overlap and the requester’s timetable — surfaced, never blocked.',
                    'A flag is a prompt to check cover, not a reason to decline; the decision stays yours.',
                  ]}
                  whySeeing="A flag surfaces an operational clash early so you decide with the full picture — it never decides for you."
                />
              </SpotlightCard>
            ) : null}
            <p className="caption quiet" style={{ margin: 0 }}>{LEAVE_TIER_LABEL[open.tier]}.</p>
          </div>
        ) : null}
      </BottomSheet>
    </div>
  );
}
