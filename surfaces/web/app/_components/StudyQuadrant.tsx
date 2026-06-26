'use client';

import { useState } from 'react';
import { Button, SpotlightCard, Tag } from '@classess/design-system';
import {
  QUADRANT_META,
  bandOf,
  quadrantGroups,
  type QuadrantBand,
  type QuadrantPoint,
} from '@/lib/adminData';
import { EvidenceDrawer } from './EvidenceDrawer';

/* ============================================================================
   StudyQuadrant — star / emerging / potential / at-risk grouping + the
   intervention launcher (component library § StudyQuadrant). The two axes are
   independence (x) and consistency (y); each learner is a point. Tapping a band
   reveals its group and the suggested set, and offers a real "Start the set"
   action that hands off to grouping/remedial. Drawn from the plain-language
   mastery read — never a raw score, never a formula. v4.1 tokens; no shadow.
   ============================================================================ */

/** A stable 0..1 pseudo-jitter from a point id + salt — deterministic per render. */
function hashJitter(id: string, salt: number): number {
  let h = 2166136261 ^ salt;
  for (let i = 0; i < id.length; i += 1) {
    h ^= id.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 1000) / 1000;
}

const BAND_AT: Record<QuadrantBand, { x: 'left' | 'right'; y: 'top' | 'bottom' }> = {
  // y is independence-consistency; high consistency sits at the top.
  star: { x: 'right', y: 'top' },
  emerging: { x: 'right', y: 'bottom' },
  potential: { x: 'left', y: 'top' },
  'at-risk': { x: 'left', y: 'bottom' },
};

export interface StudyQuadrantProps {
  points?: QuadrantPoint[];
  /** Launch the remedial/grouping set for a band (the drill that acts). */
  onStartSet?: (band: QuadrantBand, group: QuadrantPoint[]) => void;
}

export function StudyQuadrant({ points, onStartSet }: StudyQuadrantProps) {
  const groups = quadrantGroups(points);
  const [active, setActive] = useState<QuadrantBand | null>(null);
  const all = points ?? Object.values(groups).flat();

  return (
    <div className="stack" style={{ gap: 'var(--space-4)' }}>
      <div
        className="quadrant"
        role="group"
        aria-label="Study quadrant: independence by consistency"
      >
        <span className="quadrant-axis quadrant-axis-x" aria-hidden="true">
          Independence →
        </span>
        <span className="quadrant-axis quadrant-axis-y" aria-hidden="true">
          Consistency →
        </span>

        {(Object.keys(QUADRANT_META) as QuadrantBand[]).map((band) => {
          const meta = QUADRANT_META[band];
          const at = BAND_AT[band];
          const on = active === band;
          return (
            <button
              key={band}
              type="button"
              className={`quadrant-band quadrant-${at.x} quadrant-${at.y}${on ? ' active' : ''}`}
              data-tone={meta.tone}
              aria-pressed={on}
              onClick={() => setActive(on ? null : band)}
            >
              <span className="overline" style={{ margin: 0 }}>
                {meta.label}
              </span>
              <span className="quadrant-count">{groups[band].length}</span>
            </button>
          );
        })}

        {all.map((p) => {
          const meta = QUADRANT_META[bandOf(p)];
          // Inset to 6–94% so a learner sitting at 0 or 100 on either axis still
          // reads as a whole dot, never half-clipped by the quadrant border.
          // A small DETERMINISTIC jitter (keyed off the id) fans out learners who
          // share the same read so the cluster is legible — it never moves a
          // point across the band boundary, so the grouping stays truthful.
          const jx = (hashJitter(p.id, 1) - 0.5) * 11;
          const jy = (hashJitter(p.id, 2) - 0.5) * 11;
          const xr = Math.max(0, Math.min(100, p.independence));
          const yr = Math.max(0, Math.min(100, p.consistency));
          const x = Math.max(3, Math.min(97, 6 + (xr / 100) * 88 + jx));
          const y = Math.max(3, Math.min(97, 6 + (yr / 100) * 88 + jy));
          return (
            <span
              key={p.id}
              className="quadrant-point"
              data-tone={meta.tone}
              style={{ left: `${x}%`, bottom: `${y}%` }}
              title={`${p.label} · ${p.section}`}
              aria-hidden="true"
            />
          );
        })}
      </div>

      {active ? (
        <SpotlightCard>
          <div className="row-between" style={{ alignItems: 'flex-start' }}>
            <div>
              <p className="overline" style={{ margin: 0 }}>
                {QUADRANT_META[active].label}
              </p>
              <h3 className="body-lg" style={{ margin: '4px 0 0' }}>
                {groups[active].length} learners
              </h3>
            </div>
            <Tag tone={QUADRANT_META[active].tone} dot>
              {active === 'star' ? 'Stretch' : active === 'at-risk' ? 'Support' : 'Steer'}
            </Tag>
          </div>

          <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
            <span className="quiet">Suggested. </span>
            {QUADRANT_META[active].suggestion}
          </p>

          {groups[active].length > 0 ? (
            <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap', marginTop: 'var(--space-3)' }}>
              {groups[active].map((p) => (
                <Tag key={p.id} tone="neutral">
                  {p.label} · {p.section}
                </Tag>
              ))}
            </div>
          ) : (
            <p className="caption muted" style={{ marginTop: 'var(--space-3)' }}>
              No learners sit in this band right now.
            </p>
          )}

          <EvidenceDrawer
            evidence={[
              'Each learner is placed by their independence (share of attempts done unprompted) against the consistency of that independence over the fortnight.',
              'The placement is read from the mastery model — a direction, not a grade; no raw score is shown.',
            ]}
            whySeeing="The quadrant groups learners so you can target teaching by exception — stretch those working on their own, support those who need a routine."
          />

          {groups[active].length > 0 ? (
            <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
              <Button
                variant="accent"
                size="sm"
                onClick={() => onStartSet?.(active, groups[active])}
              >
                Start the suggested set for these {groups[active].length}
              </Button>
            </div>
          ) : null}
        </SpotlightCard>
      ) : (
        <p className="caption muted">Tap a band to see its group and the suggested set.</p>
      )}
    </div>
  );
}
