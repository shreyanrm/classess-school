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
          return (
            <span
              key={p.id}
              className="quadrant-point"
              data-tone={meta.tone}
              style={{
                left: `${p.independence}%`,
                bottom: `${p.consistency}%`,
              }}
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
