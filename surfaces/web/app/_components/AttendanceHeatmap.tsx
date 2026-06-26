'use client';

import { useMemo } from 'react';
import { Icon } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { AttendanceRecord, AttendanceState, ReadSource } from '@/lib/vizData';

/* ============================================================================
   AttendanceHeatmap — a month x day grid (SVG-free, CSS-grid cells) reading the
   per-day attendance state in COOL / brand hues. The v2 monthly heatmap, carried
   into the v3 grammar: calm + non-punitive (absent is a tonal step + a hairline
   mark, never an alarming wash), per-row % from PLAIN COUNTS (never an opaque
   figure), a legend, evidence lineage on the conclusion, and a SourceNote so the
   gateway-vs-fallback seam stays honest.

   Pure + data-driven: it takes an AttendanceRecord prop and the read source.
   Depth = hairline + tonal step only. No shadow. Reduced-motion safe (the cells
   carry no motion). Cool ultramarine/brand only; no coral, no warm-orange.
   ============================================================================ */

const STATE_LABEL: Record<AttendanceState, string> = {
  present: 'Present',
  half: 'Half day',
  leave: 'Leave',
  absent: 'Absent',
  holiday: 'Holiday',
  weekend: 'Weekend',
  future: 'Upcoming',
  none: '—',
};

/** The legend order — only the states a reader needs to decode. */
const LEGEND: AttendanceState[] = ['present', 'half', 'leave', 'absent', 'holiday'];

export interface AttendanceHeatmapProps {
  record: AttendanceRecord;
  /** Which source answered — drives the honest SourceNote. */
  source?: ReadSource;
  /** Hide the per-month grids and show only the summary row (compact embeds). */
  compact?: boolean;
}

export function AttendanceHeatmap({ record, source = 'fallback', compact }: AttendanceHeatmapProps) {
  const { present, half, leave, absent, schoolDays } = record.counts;

  // The per-row % is built from plain counts: a half day reads as half a day
  // present. Never a single opaque figure — the parts are always visible.
  const pct = useMemo(() => {
    if (schoolDays <= 0) return 0;
    return Math.round(((present + half * 0.5) / schoolDays) * 100);
  }, [present, half, schoolDays]);

  return (
    <div className="att-heatmap" role="group" aria-label={`Attendance for ${record.rowLabel}`}>
      <div className="att-summary">
        <div className="att-summary-pct">
          <span className="att-pct-value">{pct}</span>
          <span className="att-pct-unit">%</span>
        </div>
        <div className="att-summary-detail">
          <p className="body-sm" style={{ margin: 0, fontWeight: 'var(--fw-medium)' as React.CSSProperties['fontWeight'] }}>
            {record.rowLabel} · present
          </p>
          <p className="caption muted" style={{ margin: '2px 0 0' }}>
            {present} present · {half} half · {leave} leave · {absent} absent · of {schoolDays} school days
          </p>
        </div>
      </div>

      {compact ? null : (
        <div className="att-months">
          {record.months.map((month) => (
            <div className="att-month" key={month.label}>
              <p className="overline att-month-label">{month.label}</p>
              <div
                className="att-grid"
                role="img"
                aria-label={`${month.label}: ${month.days.length} days`}
              >
                {/* Leading blanks so day 1 lands under its weekday column. */}
                {Array.from({ length: month.startWeekday }).map((_, i) => (
                  <span className="att-cell att-cell-pad" key={`pad-${i}`} aria-hidden="true" />
                ))}
                {month.days.map((state, i) => (
                  <span
                    key={i}
                    className="att-cell"
                    data-state={state}
                    title={`${month.label} ${i + 1}: ${STATE_LABEL[state]}`}
                    aria-label={`${month.label} ${i + 1}: ${STATE_LABEL[state]}`}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="att-legend" aria-hidden="true">
        {LEGEND.map((state) => (
          <span className="att-legend-item" key={state}>
            <span className="att-cell att-legend-swatch" data-state={state} />
            {STATE_LABEL[state]}
          </span>
        ))}
      </div>

      <p className="body-sm" style={{ margin: 0 }}>{record.note}</p>

      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <EvidenceDrawer
          claim={`Why ${record.rowLabel}'s attendance reads ${pct}%`}
          evidence={[
            { text: `${present} full days present and ${half} half days across ${schoolDays} school days so far.`, when: 'This term' },
            { text: `${absent} absences and ${leave} approved leave days, each marked on the grid above.`, when: 'This term' },
            { text: 'Holidays and weekends are excluded from the denominator, so the percentage reads only against days school was in session.' },
          ]}
          whySeeing="The percentage is built from plain, visible counts — half days count as half a day present — so the figure is never an opaque single number."
        />
        <span className="caption quiet row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
          <Icon name="info" size="sm" /> Calm read — a pattern to notice, never a judgement.
        </span>
      </div>

      <SourceNote source={source} />
    </div>
  );
}
