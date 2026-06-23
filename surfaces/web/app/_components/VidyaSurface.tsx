'use client';

/* ============================================================================
   app/_components/VidyaSurface.tsx — Vidya's operable generative surface.

   When the orchestrator returns a compose_surface spec (a quiz-builder, a
   class-view, a plan-board, a report-card), the orb renders it HERE as a real,
   interactive panel INSIDE the conversation — not a flat read-only card. The
   teacher can read and EDIT a quiz item in place, scan a class-view, work a
   plan-board; a parent reads a report-card.

   The PERMISSION LADDER holds end-to-end: a CONSEQUENTIAL affordance (publish a
   quiz, adopt a plan) NEVER fires from inside the surface. Pressing it returns a
   requires_approval intent (calmly surfaced, with the real review route), and
   the human acts on the dedicated page. The surface only ever PREPARES.

   v4 brand: calm, per-surface accent, no shadows, sharp corners, plain language,
   no emoji, no exclamation. Edits are local to the thread (ephemeral) — the
   source of truth is set only on the review page, behind approval.

   data-testids: vidya-surface, vidya-surface-publish, vidya-surface-approval.
   ============================================================================ */

import { useState } from 'react';
import Link from 'next/link';
import { Icon, Input, Textarea, Tag } from '@classess/design-system';
import type {
  SurfaceSpec,
  QuizBuilderSurface,
  ClassViewSurface,
  PlanBoardSurface,
  ReportCardSurface,
  QuizItem,
  SurfaceAction,
} from '@/lib/vidya';

export interface VidyaSurfaceProps {
  spec: SurfaceSpec;
  /** Follow the review route for a consequential affordance (router.push). */
  onOpenHref?: (href: string) => void;
}

/**
 * The consequential control inside a surface. It NEVER executes — pressing it
 * surfaces a calm requires_approval note and the single control that routes the
 * human to the real review page. The permission ladder is visible, not implied.
 */
function ApprovalControl({
  action,
  onOpenHref,
}: {
  action: SurfaceAction;
  onOpenHref?: (href: string) => void;
}) {
  const [asked, setAsked] = useState(false);
  return (
    <div className="vidya-surface-foot">
      {!asked ? (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          data-testid="vidya-surface-publish"
          onClick={() => setAsked(true)}
        >
          {action.label}
        </button>
      ) : (
        <div className="vidya-surface-approval" data-testid="vidya-surface-approval" role="status">
          <p className="body-sm muted" style={{ margin: 0 }}>
            This needs your approval. Vidya has prepared it; you set it live on the review page.
          </p>
          <Link
            href={action.openHref}
            className="btn btn-secondary btn-sm row"
            style={{ gap: 'var(--space-2)' }}
            data-testid="vidya-surface-review"
            onClick={(e) => {
              if (onOpenHref) {
                e.preventDefault();
                onOpenHref(action.openHref);
              }
            }}
          >
            {action.label}
            <Icon name="arrow-up-right" size="sm" />
          </Link>
        </div>
      )}
    </div>
  );
}

/** A WORKING quiz builder — items are editable in place; publish only prepares. */
function QuizBuilder({ spec, onOpenHref }: { spec: QuizBuilderSurface; onOpenHref?: (h: string) => void }) {
  // Edits are LOCAL/ephemeral: the source of truth is set on the review page,
  // behind approval. We keep a working copy so the teacher can refine in the orb.
  const [items, setItems] = useState<QuizItem[]>(spec.items);

  function updatePrompt(i: number, prompt: string) {
    setItems((prev) => prev.map((it, n) => (n === i ? { ...it, prompt } : it)));
  }

  return (
    <div className="vidya-surface" data-testid="vidya-surface" data-surface-kind="quiz-builder">
      <div className="vidya-surface-head">
        <span className="overline">
          <Icon name="spark" size="sm" /> Quick check
        </span>
        <h4 className="body-lg" style={{ margin: '4px 0 0' }}>
          {spec.title}
        </h4>
        <p className="body-sm muted" style={{ margin: '2px 0 0' }}>
          On {spec.topic}. Edit any question here; setting it live needs your approval.
        </p>
      </div>
      <ol className="vidya-surface-items">
        {items.map((it, i) => (
          <li key={i} className="vidya-surface-item">
            <span className="vidya-surface-index" aria-hidden="true">
              {i + 1}
            </span>
            <div className="vidya-surface-item-body">
              <Input
                aria-label={`Question ${i + 1}`}
                data-testid="vidya-surface-item-input"
                value={it.prompt}
                onChange={(e) => updatePrompt(i, e.target.value)}
              />
              {it.options && it.options.length > 0 ? (
                <ul className="vidya-surface-options">
                  {it.options.map((opt, k) => (
                    <li key={k} className="body-sm muted">
                      {opt}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
      <ApprovalControl action={spec.publish} onOpenHref={onOpenHref} />
    </div>
  );
}

/** A read-only class view — generic labels + plain bands, never a raw score. */
function ClassView({ spec }: { spec: ClassViewSurface }) {
  return (
    <div className="vidya-surface" data-testid="vidya-surface" data-surface-kind="class-view">
      <div className="vidya-surface-head">
        <span className="overline">
          <Icon name="spark" size="sm" /> Class view
        </span>
        <h4 className="body-lg" style={{ margin: '4px 0 0' }}>
          {spec.title}
        </h4>
        {spec.summary ? (
          <p className="body-sm muted" style={{ margin: '2px 0 0' }}>
            {spec.summary}
          </p>
        ) : null}
      </div>
      <ul className="vidya-surface-rows">
        {spec.rows.map((r, i) => (
          <li key={i} className="vidya-surface-row">
            <span className="body-sm">{r.label}</span>
            <span className="row" style={{ gap: 'var(--space-2)' }}>
              <span className="body-sm muted">{r.band}</span>
              {r.needsAttention ? <Tag tone="warning">worth a look</Tag> : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A lesson-plan board — read/scan columns; adopt only prepares. */
function PlanBoard({ spec, onOpenHref }: { spec: PlanBoardSurface; onOpenHref?: (h: string) => void }) {
  return (
    <div className="vidya-surface" data-testid="vidya-surface" data-surface-kind="plan-board">
      <div className="vidya-surface-head">
        <span className="overline">
          <Icon name="spark" size="sm" /> Lesson plan
        </span>
        <h4 className="body-lg" style={{ margin: '4px 0 0' }}>
          {spec.title}
        </h4>
        <p className="body-sm muted" style={{ margin: '2px 0 0' }}>
          A draft for {spec.topic}. Adopting it needs your approval.
        </p>
      </div>
      <div className="vidya-surface-board">
        {spec.columns.map((col, i) => (
          <div key={i} className="vidya-surface-col">
            <span className="overline" style={{ margin: 0 }}>
              {col.heading}
            </span>
            <ul className="stack" style={{ margin: 'var(--space-2) 0 0', listStyle: 'none', padding: 0 }}>
              {col.cards.map((card, k) => (
                <li key={k} className="vidya-surface-card body-sm">
                  {card}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <ApprovalControl action={spec.adopt} onOpenHref={onOpenHref} />
    </div>
  );
}

/** A read-only, plain-language report card for a parent. No raw scores. */
function ReportCard({ spec }: { spec: ReportCardSurface }) {
  return (
    <div className="vidya-surface" data-testid="vidya-surface" data-surface-kind="report-card">
      <div className="vidya-surface-head">
        <span className="overline">
          <Icon name="spark" size="sm" /> How your child is doing
        </span>
        <h4 className="body-lg" style={{ margin: '4px 0 0' }}>
          {spec.title}
        </h4>
        <p className="body-sm muted" style={{ margin: '2px 0 0' }}>
          For {spec.childLabel}, in plain language.
        </p>
      </div>
      <ul className="stack" style={{ margin: 0, paddingLeft: '1.1rem' }}>
        {spec.highlights.map((h, i) => (
          <li key={i} className="body-sm">
            {h}
          </li>
        ))}
      </ul>
      {spec.nextStep ? (
        <p className="body-sm vidya-surface-next">Next: {spec.nextStep}</p>
      ) : null}
    </div>
  );
}

/**
 * Render the composed surface as a real, interactive panel inside the orb
 * conversation. Unknown kinds never reach here (sanitised upstream in lib/vidya).
 */
export function VidyaSurface({ spec, onOpenHref }: VidyaSurfaceProps) {
  switch (spec.kind) {
    case 'quiz-builder':
      return <QuizBuilder spec={spec} onOpenHref={onOpenHref} />;
    case 'class-view':
      return <ClassView spec={spec} />;
    case 'plan-board':
      return <PlanBoard spec={spec} onOpenHref={onOpenHref} />;
    case 'report-card':
      return <ReportCard spec={spec} />;
    default:
      return null;
  }
}
