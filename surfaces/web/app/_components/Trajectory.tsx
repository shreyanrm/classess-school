'use client';

import type { TrajectorySeries } from '@/lib/adminData';
import { EvidenceDrawer } from './EvidenceDrawer';

/* ============================================================================
   Trajectory — the actual-solid / predicted-dotted independence trend
   (component library § Trajectory). A chart survives here because a human reads
   its SHAPE: where the line is heading. The solid stroke is the readings to
   date; the dotted stroke is the predicted continuation, recalculated as time
   and weightage change. A direction, never a grade; the accent is the surface's
   single accent. v4.1 tokens; no shadow.
   ============================================================================ */

const W = 640;
const H = 200;
const PAD = 16;

function project(values: number[], offset: number, total: number): string {
  // x spans the full series (actual + predicted share one axis); y is 0..100.
  return values
    .map((v, i) => {
      const x = PAD + ((offset + i) / (total - 1)) * (W - PAD * 2);
      const y = H - PAD - (v / 100) * (H - PAD * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

export interface TrajectoryProps {
  series: TrajectorySeries;
}

export function Trajectory({ series }: TrajectoryProps) {
  const { actual, predicted } = series;
  // The predicted line begins at the last actual point so the two join cleanly.
  const total = actual.length + predicted.length - 1;
  const actualPts = project(actual, 0, total);
  const predictedPts = project(predicted, actual.length - 1, total);

  return (
    <div className="stack" style={{ gap: 'var(--space-3)' }}>
      <div className="trajectory" role="img" aria-label={`${series.topic}. ${series.read}`}>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="trajectory-svg">
          {/* hairline baseline + midline — depth via hairline, never a shadow */}
          <line x1={PAD} y1={H - PAD} x2={W - PAD} y2={H - PAD} className="trajectory-grid" />
          <line x1={PAD} y1={H / 2} x2={W - PAD} y2={H / 2} className="trajectory-grid" />
          <polyline points={actualPts} className="trajectory-actual" />
          <polyline points={predictedPts} className="trajectory-predicted" />
        </svg>
      </div>

      <div className="row" style={{ gap: 'var(--space-4)', flexWrap: 'wrap' }}>
        <span className="caption muted row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
          <span className="trajectory-key trajectory-key-actual" aria-hidden="true" /> Actual to date
        </span>
        <span className="caption muted row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
          <span className="trajectory-key trajectory-key-predicted" aria-hidden="true" /> Predicted
        </span>
      </div>

      <p className="body-sm">{series.read}</p>

      <EvidenceDrawer
        evidence={[
          'The solid line is the share of the cohort working on their own at each reading, drawn from the mastery model.',
          'The dotted line projects the same trend forward; it recalculates as time passes and weightage shifts — a probability, not a promise.',
        ]}
        whySeeing="Reading the shape tells you whether a cohort is on track to reach independence by term end, and what recovering the behind sections would do to the tail."
      />
    </div>
  );
}
