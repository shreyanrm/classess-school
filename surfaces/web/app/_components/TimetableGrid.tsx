'use client';

import { useMemo } from 'react';
import { SourceNote } from './SourceNote';
import type { Timetable, TimetableBlock, ReadSource } from '@/lib/vizData';

/* ============================================================================
   TimetableGrid — a weekly day × period grid. The v2 timetable, carried into
   the v3 grammar: subjects on the cool accent palette (a subject-tinted block
   per period, never coral), free slots read as calm empty cells, depth =
   hairline + tonal step, NO shadow, reduced-motion safe. Pure + data-driven
   (takes a Timetable prop). Used across Teacher / Student / Parent role views.
   ============================================================================ */

export interface TimetableGridProps {
  timetable: Timetable;
  source?: ReadSource;
  /** Highlight a day column (0-based) — e.g. "today" on a role surface. */
  highlightDay?: number;
}

export function TimetableGrid({ timetable, source = 'fallback', highlightDay }: TimetableGridProps) {
  const { dayLabels, periodLabels, blocks } = timetable;

  // Index blocks by "day:period" so each cell resolves in O(1).
  const byCell = useMemo(() => {
    const map = new Map<string, TimetableBlock>();
    for (const b of blocks) map.set(`${b.day}:${b.period}`, b);
    return map;
  }, [blocks]);

  const cols = dayLabels.length;

  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-4)' }}>
      <div className="sec-head">
        <h4 className="h4" style={{ margin: 0 }}>This week</h4>
        <span className="overline">timetable</span>
      </div>

      <div
        className="tt-grid"
        role="grid"
        aria-label="Weekly timetable"
        style={{ ['--tt-cols' as string]: cols } as React.CSSProperties}
      >
        {/* Header row: a blank corner + each day. */}
        <div className="tt-corner" role="columnheader" aria-hidden="true" />
        {dayLabels.map((d, di) => (
          <div
            className={`tt-dayhead${highlightDay === di ? ' tt-today' : ''}`}
            role="columnheader"
            key={d}
          >
            {d}
          </div>
        ))}

        {/* One row per period: the time label + each day's block (or a free slot). */}
        {periodLabels.map((time, pi) => (
          <div className="tt-row" role="row" key={time} style={{ display: 'contents' }}>
            <div className="tt-time" role="rowheader">{time}</div>
            {dayLabels.map((_, di) => {
              const block = byCell.get(`${di}:${pi}`);
              if (!block) {
                return (
                  <div className={`tt-cell tt-free${highlightDay === di ? ' tt-today-col' : ''}`} role="gridcell" key={di}>
                    <span className="caption quiet">Free</span>
                  </div>
                );
              }
              return (
                <div
                  className={`tt-cell tt-block subject-tinted${highlightDay === di ? ' tt-today-col' : ''}`}
                  data-subject={block.subject}
                  role="gridcell"
                  key={di}
                >
                  <span className="tt-block-subject">{block.label}</span>
                  {block.detail ? <span className="caption muted tt-block-detail">{block.detail}</span> : null}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      <SourceNote source={source} />
    </div>
  );
}
