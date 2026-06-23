'use client';

import type { MasteryDimensions } from '@classess/contracts';

/**
 * The six explicit mastery dimensions, rendered as labelled bars. This is the
 * teacher/diagnostic view — it makes the reasoning visible (never collapsed to
 * one opaque number), with Independence marked as the keystone. Learners never
 * see this; they see plain language. The raw composite is never shown here.
 */

const DIMENSION_ORDER: ReadonlyArray<{ key: keyof MasteryDimensions; label: string; keystone?: boolean }> = [
  { key: 'performance', label: 'Performance' },
  { key: 'reliability', label: 'Reliability' },
  { key: 'independence', label: 'Independence', keystone: true },
  { key: 'difficulty', label: 'Difficulty' },
  { key: 'recency', label: 'Recency' },
  { key: 'consistency', label: 'Consistency' },
];

/** Plain-language gloss per dimension — so the bar is explainable, not a score. */
const DIMENSION_GLOSS: Record<keyof MasteryDimensions, string> = {
  performance: 'how correct the work is',
  reliability: 'how dependable across attempts',
  independence: 'how much was done alone, not with help',
  difficulty: 'how hard the items succeeded on were',
  recency: 'how fresh the evidence is',
  consistency: 'how steady the work is over time',
};

export interface DimensionBarsProps {
  dimensions: MasteryDimensions;
  /** Show the one-line gloss under each label. Off by default to stay calm. */
  showGloss?: boolean;
}

export function DimensionBars({ dimensions, showGloss }: DimensionBarsProps) {
  return (
    <div className="dims">
      {DIMENSION_ORDER.map(({ key, label, keystone }) => {
        const value = dimensions[key];
        const pct = Math.round(value * 100);
        return (
          <div className={`dim${keystone ? ' keystone' : ''}`} key={key}>
            <div className="dim-label">
              {label}
              {showGloss ? <div className="caption quiet">{DIMENSION_GLOSS[key]}</div> : null}
            </div>
            <div
              className="dim-track"
              role="meter"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={pct}
              aria-label={`${label}: ${DIMENSION_GLOSS[key]}`}
            >
              <div className="dim-fill" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
