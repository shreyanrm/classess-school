'use client';

import { SourceNote } from './SourceNote';
import type { ReadSource } from '@/lib/vizData';
import type { AcademicPlanner as AcademicPlannerData, PlannerUnit } from '@/lib/opsData';

/* ============================================================================
   AcademicPlanner — the v2 Gantt-style multi-subject academic planner, carried
   into the v3 grammar. A year x month grid; each subject lays its units out as
   tinted bars spanning a month range, on the COOL accent palette (never coral).
   The current month draws a calm "now" rule; the unit in delivery reads with a
   hairline ring. Depth = hairline + tonal step, NO shadow, reduced-motion safe.
   Pure + data-driven (takes an AcademicPlanner prop). A planning lens, never a
   learner score.
   ============================================================================ */

export interface AcademicPlannerProps {
  data: AcademicPlannerData;
  source?: ReadSource;
}

export function AcademicPlanner({ data, source = 'fallback' }: AcademicPlannerProps) {
  const { months, currentMonth, units } = data;
  const cols = months.length;

  // Group units by subject so each subject is one row track (a Gantt lane).
  const lanes = new Map<string, { subject: PlannerUnit['subject']; name: string; units: PlannerUnit[] }>();
  for (const u of units) {
    const lane = lanes.get(u.subjectName) ?? { subject: u.subject, name: u.subjectName, units: [] };
    lane.units.push(u);
    lanes.set(u.subjectName, lane);
  }
  const laneList = [...lanes.values()];

  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-4)' }}>
      <div className="sec-head">
        <h4 className="h4" style={{ margin: 0 }}>{data.scopeLabel} — academic planner</h4>
        <span className="overline">year × month</span>
      </div>

      <div
        className="gantt"
        role="grid"
        aria-label={`Academic planner for ${data.scopeLabel}`}
        style={{ ['--gantt-cols' as string]: cols } as React.CSSProperties}
      >
        {/* Header row: a label gutter + each month. */}
        <div className="gantt-corner" role="columnheader" aria-hidden="true" />
        {months.map((m, i) => (
          <div
            className={`gantt-month${i === currentMonth ? ' gantt-month-now' : ''}`}
            role="columnheader"
            key={m}
          >
            {m}
          </div>
        ))}

        {/* One lane (track) per subject. */}
        {laneList.map((lane) => (
          <div className="gantt-lane" role="row" key={lane.name} style={{ display: 'contents' }}>
            <div className="gantt-lane-label" role="rowheader">
              <span className="subject-dot" style={{ background: `var(--${lane.subject})` }} aria-hidden="true" />
              <span className="caption">{lane.name}</span>
            </div>
            <div className="gantt-track" style={{ gridColumn: `2 / span ${cols}` }}>
              {/* The month gridlines behind the bars. */}
              <div className="gantt-gridlines" aria-hidden="true">
                {months.map((m, i) => (
                  <span className={`gantt-gridline${i === currentMonth ? ' gantt-gridline-now' : ''}`} key={m} />
                ))}
              </div>
              {lane.units.map((u) => (
                <div
                  key={u.id}
                  className={`gantt-bar subject-tinted${u.current ? ' gantt-bar-current' : ''}`}
                  data-subject={u.subject}
                  role="gridcell"
                  title={`${u.subjectName} — ${u.unit} (${months[u.startMonth]}${u.span > 1 ? ` to ${months[Math.min(months.length - 1, u.startMonth + u.span - 1)]}` : ''})`}
                  style={{
                    left: `${(u.startMonth / cols) * 100}%`,
                    width: `${(u.span / cols) * 100}%`,
                  }}
                >
                  <span className="gantt-bar-label">{u.unit}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="cal-legend" aria-hidden="true">
        {laneList.map((lane) => (
          <span className="cal-legend-item" key={lane.name}>
            <span className="subject-dot" style={{ background: `var(--${lane.subject})` }} /> {lane.name}
          </span>
        ))}
      </div>

      <p className="caption quiet" style={{ margin: 0 }}>
        Each bar is a unit and the months it runs. The vertical rule marks the current month; a ringed
        bar is the unit in delivery now. A planning lens — never a learner score.
      </p>

      <SourceNote source={source} />
    </div>
  );
}
