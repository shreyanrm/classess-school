'use client';

import { useMemo } from 'react';
import { Button, ConfidenceBand, Icon, Tag, useCountUp } from '@classess/design-system';
import { SourceNote } from './SourceNote';
import type { FormalReportCard as FormalReportCardData, ReadSource } from '@/lib/vizData';

/* ============================================================================
   FormalReportCard — the FORMAL marks/grade report-card DOCUMENT, offered
   ALONGSIDE the plain-language HolisticProgressCard (never replacing it). The
   holistic card stays the default read; this is the explicit "Formal report
   card" export a teacher, parent, or student can toggle to and print.

   It is a proper report-card document, not a dashboard:
     · a document header  — student / roll / class / term + the generic scale
     · an overall matrix  — total marks, percentage, GPA, attendance % (count-up)
     · a marks table      — subject × { marks, total/max, grade, grade-points },
                            cool subject-hue row rails, mono-tabular figures
     · an attendance line — plain counts behind the %
     · a teacher remark   — calm, plain language, never a label on a child
     · a clean PDF path   — the Print / PDF button calls window.print(); the
                            shared .report-print print scope drops the app
                            chrome and lays this out as a single document.

   v3 grammar: dense + composed, ONE cool accent per surface, mono-caps
   overlines, hairline + tonal + frost (NEVER a shadow), count-up matrix,
   designed states, reduced-motion safe (count-up jumps to its end value). The
   ultramarine signature stays reserved — the marks table carries the cool
   subject hues; no coral anywhere.

   Confidentiality: every label is generic + fictional (Student A, an opaque
   roll, Section 10-B). No board lock-in — the scale is a generic A1..E /
   grade-point shape carried as data. Marks describe a generic assessment
   record, never a real child.
   ============================================================================ */

const GRADE_TONE: Record<string, 'success' | 'info' | 'warning' | 'neutral'> = {
  A1: 'success',
  A2: 'success',
  B1: 'info',
  B2: 'info',
  C1: 'warning',
  C2: 'warning',
  D: 'neutral',
  E: 'neutral',
};

export interface FormalReportCardProps {
  data: FormalReportCardData;
  source?: ReadSource;
  /** Tunes the framing copy; the document itself reads the same for all. */
  audience?: 'teacher' | 'parent' | 'student';
}

/** A single count-up figure for the overall matrix — tabular, reduced-motion safe.
 *  The hook eases an INTEGER; for decimal figures (GPA, percentage) we count up
 *  a scaled integer and divide back on render, so the decimals never get lost. */
function CountCell({
  label,
  value,
  unit,
  delta,
  decimals = 0,
}: {
  label: string;
  value: number;
  unit?: string;
  delta?: string;
  decimals?: number;
}) {
  const scale = Math.pow(10, decimals);
  const { value: scaled, ref } = useCountUp(Math.round(value * scale));
  const shown = (scaled / scale).toFixed(decimals);
  return (
    <div className="cell">
      <div className="cell-label">{label}</div>
      <div className="cell-value">
        <span ref={ref}>{shown}</span>
        {unit ? unit : null}
      </div>
      {delta ? <div className="cell-delta flat">{delta}</div> : null}
    </div>
  );
}

export function FormalReportCard({ data, source = 'fallback', audience = 'teacher' }: FormalReportCardProps) {
  const totals = useMemo(() => {
    const marks = data.subjects.reduce((s, r) => s + r.marks, 0);
    const max = data.subjects.reduce((s, r) => s + r.max, 0);
    const points = data.subjects.reduce((s, r) => s + r.gradePoints, 0);
    const pct = max > 0 ? (marks / max) * 100 : 0;
    const gpa = data.subjects.length > 0 ? points / data.subjects.length : 0;
    return { marks, max, pct, gpa };
  }, [data.subjects]);

  const attendancePct = useMemo(() => {
    const { present, schoolDays } = data.attendance;
    if (schoolDays <= 0) return 0;
    return Math.round((present / schoolDays) * 100);
  }, [data.attendance]);

  function handlePrint() {
    if (typeof window !== 'undefined') window.print();
  }

  return (
    <article className="report-print formal-report stack" style={{ gap: 'var(--space-6)' }} data-testid="formal-report-card">
      {/* ── Document header — the report-card masthead + the print path ── */}
      <header className="report-head formal-report-head">
        <div className="report-head-id">
          <p className="overline" style={{ margin: 0 }}>Formal report card · {data.scaleLabel}</p>
          <h2 className="h2" style={{ margin: '4px 0 0' }}>{data.studentLabel}</h2>
          <div className="formal-report-meta">
            <span className="m"><span className="k">Roll</span> <b>{data.rollLabel}</b></span>
            <span className="m"><span className="k">Class</span> <b>{data.classLabel}</b></span>
            <span className="m"><span className="k">Term</span> <b>{data.term}</b></span>
          </div>
        </div>
        <div className="report-head-actions no-print">
          <ConfidenceBand level={data.confidence} />
          <Button variant="secondary" size="sm" onClick={handlePrint} className="row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="file" size="sm" /> Print / PDF
          </Button>
        </div>
      </header>

      {/* ── Overall standing — the count-up matrix (total, %, GPA, attendance) ── */}
      <section className="report-section">
        <p className="overline">Overall standing · {data.term}</p>
        <div className="matrix reveal" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginTop: 'var(--space-3)' }}>
          <CountCell label="Total marks" value={totals.marks} delta={`of ${totals.max}`} />
          <CountCell label="Percentage" value={Math.round(totals.pct * 10) / 10} unit="%" decimals={1} delta="aggregate" />
          <CountCell label="GPA" value={Math.round(totals.gpa * 100) / 100} decimals={2} delta="grade-point average" />
          <CountCell label="Attendance" value={attendancePct} unit="%" delta={`${data.attendance.present} of ${data.attendance.schoolDays} days`} />
        </div>
      </section>

      {/* ── The marks table — subject × {marks, total, grade, grade-points} ── */}
      <section className="report-section">
        <p className="overline">Subject marks &amp; grades</p>
        <div className="table-wrap" style={{ marginTop: 'var(--space-3)' }}>
          <table className="table formal-marks-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th className="num">Marks</th>
                <th className="num">Out of</th>
                <th>Grade</th>
                <th className="num">Grade points</th>
              </tr>
            </thead>
            <tbody>
              {data.subjects.map((r) => (
                <tr
                  key={r.subject}
                  className="formal-marks-row"
                  data-subject={r.accent}
                  style={{ '--subject': `var(--${r.accent})` } as React.CSSProperties}
                >
                  <td>
                    <span className="formal-subject">
                      <span className="formal-subject-rail" aria-hidden="true" />
                      {r.subject}
                    </span>
                  </td>
                  <td className="num"><span className="data">{r.marks}</span></td>
                  <td className="num muted"><span className="data">{r.max}</span></td>
                  <td>
                    <Tag tone={GRADE_TONE[r.grade] ?? 'neutral'}>{r.grade}</Tag>
                  </td>
                  <td className="num"><span className="data">{r.gradePoints}</span></td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="formal-marks-total">
                <td><strong>Total</strong></td>
                <td className="num"><strong className="data">{totals.marks}</strong></td>
                <td className="num"><strong className="data">{totals.max}</strong></td>
                <td>
                  <span className="caption quiet" style={{ fontVariantNumeric: 'tabular-nums', paddingLeft: 'var(--space-2)' }}>
                    {Math.round(totals.pct * 10) / 10}%
                  </span>
                </td>
                <td className="num"><strong className="data">GPA {Math.round(totals.gpa * 100) / 100}</strong></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      {/* ── Attendance summary — plain counts behind the % ── */}
      <section className="report-section">
        <p className="overline">Attendance</p>
        <div className="report-att" style={{ marginTop: 'var(--space-3)' }}>
          <div className="report-att-pct">
            <span className="gauge-value">{attendancePct}%</span>
            <span className="caption muted">present this term</span>
          </div>
          <div className="report-att-counts">
            <span className="report-att-count"><strong>{data.attendance.present}</strong> present</span>
            <span className="report-att-count"><strong>{data.attendance.schoolDays}</strong> school days</span>
          </div>
        </div>
      </section>

      {/* ── Teacher remark — calm, plain, signed by a generic role ── */}
      <section className="report-section formal-remark">
        <p className="overline">Teacher remark</p>
        <p className="body" style={{ margin: '6px 0 0', maxWidth: '64ch' }}>{data.remark}</p>
        <p className="caption muted" style={{ margin: 'var(--space-3) 0 0' }}>
          Issued by {data.issuedBy}
          {audience === 'teacher'
            ? ' · this formal card sits alongside the plain-language holistic card, which stays the default read'
            : ' · the plain-language progress card carries the fuller picture'}
          .
        </p>
      </section>

      <SourceNote source={source} />
    </article>
  );
}
