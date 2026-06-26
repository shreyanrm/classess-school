'use client';

import { useMemo, useState } from 'react';
import { ConfidenceBand, Icon, Tag } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { MarkBand, MarkBook, MarkCell, ReadSource } from '@/lib/vizData';

/* ============================================================================
   Markbook — the v2 grade-entry grid (students × periods/terms), in v3.

   A spreadsheet markbook the way teachers expect it — but in the v3 grammar:
   every cell is a PLAIN-LANGUAGE BAND (exemplary / above / on / below / not-yet),
   never a raw %, never a number on a child. Cells are colour-coded by band on
   a cool ramp; a remark can sit behind a cell. A Setup / View toggle switches
   between entering a band (Setup) and the calm read (View).

   v3 grammar: bands not single scores, evidence-first (ConfidenceBand +
   EvidenceDrawer behind the read), subjects on the cool accent palette (never
   the ultramarine signature, never coral), depth = hairline + tonal step only,
   NO shadow, reduced-motion safe. Local edits are host-owned; this writes
   nothing on its own — a markbook is the teacher's recorded judgement.
   ============================================================================ */

const BAND_ORDER: MarkBand[] = ['exemplary', 'above', 'on', 'below', 'not-yet'];

const BAND_LABEL: Record<MarkBand, string> = {
  exemplary: 'Exemplary',
  above: 'Above target',
  on: 'On target',
  below: 'Below target',
  'not-yet': 'Not yet shown',
};

/** A short cell glyph for the band — a calm token, never a grade letter. */
const BAND_SHORT: Record<MarkBand, string> = {
  exemplary: 'Ex',
  above: 'Ab',
  on: 'On',
  below: 'Be',
  'not-yet': '–',
};

export interface MarkbookProps {
  data: MarkBook;
  source?: ReadSource;
}

type Mode = 'view' | 'setup';

export function Markbook({ data, source = 'fallback' }: MarkbookProps) {
  const [mode, setMode] = useState<Mode>('view');
  // Local edits are host-owned and never auto-persisted — a markbook entry is
  // the teacher's recorded judgement, kept in component state for this session.
  const [edits, setEdits] = useState<Record<string, MarkBand>>({});

  const cellOf = (rowIndex: number, periodIndex: number): MarkCell =>
    data.rows[rowIndex]!.cells[periodIndex] ?? { band: null };

  const bandOf = (rowIndex: number, periodIndex: number): MarkBand | null =>
    edits[`${rowIndex}:${periodIndex}`] ?? cellOf(rowIndex, periodIndex).band;

  function cycle(rowIndex: number, periodIndex: number) {
    const current = bandOf(rowIndex, periodIndex);
    const at = current ? BAND_ORDER.indexOf(current) : -1;
    const next = BAND_ORDER[(at + 1) % BAND_ORDER.length]!;
    setEdits((prev) => ({ ...prev, [`${rowIndex}:${periodIndex}`]: next }));
  }

  // A plain count of how many cells carry a band, for the calm completeness read.
  const filled = useMemo(() => {
    let n = 0;
    for (let r = 0; r < data.rows.length; r++)
      for (let p = 0; p < data.periods.length; p++) if (bandOf(r, p)) n++;
    return n;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, edits]);
  const totalCells = data.rows.length * data.periods.length;

  return (
    <div
      className="stack viz-card subject-tinted"
      data-subject={data.subject}
      style={{ gap: 'var(--space-5)' }}
    >
      <div className="sec-head">
        <div>
          <p className="overline" style={{ margin: 0 }}>Markbook · {data.classLabel}</p>
          <h4 className="h4" style={{ margin: '4px 0 0' }}>Standing by period</h4>
        </div>
        <ConfidenceBand level={data.confidence} />
      </div>

      {/* ── Setup / View toggle ── */}
      <div className="row-between" style={{ flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <div className="segmented" role="tablist" aria-label="Markbook mode">
          <button type="button" role="tab" aria-selected={mode === 'view'} className={mode === 'view' ? 'active' : ''} onClick={() => setMode('view')}>
            View
          </button>
          <button type="button" role="tab" aria-selected={mode === 'setup'} className={mode === 'setup' ? 'active' : ''} onClick={() => setMode('setup')}>
            Setup
          </button>
        </div>
        <span className="caption muted">
          {filled} of {totalCells} cells recorded
        </span>
      </div>

      {mode === 'setup' ? (
        <p className="caption quiet" style={{ margin: 0 }}>
          Setup mode — select a cell to cycle its band. A band is your recorded judgement against
          the period target, never a number shown to a learner. Nothing is published from here.
        </p>
      ) : (
        <p className="caption quiet" style={{ margin: 0 }}>
          View mode — the calm read. Each cell is a plain-language band, colour-coded; switch to Setup
          to record a standing.
        </p>
      )}

      {/* ── The grid: students × periods ── */}
      <div className="markbook-scroll">
        <table className="markbook-table">
          <thead>
            <tr>
              <th scope="col" className="markbook-roll-head">Roll</th>
              <th scope="col" className="markbook-student-head">Student</th>
              {data.periods.map((p) => (
                <th scope="col" key={p} className="num">{p}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, r) => (
              <tr key={row.label}>
                <th scope="row" className="markbook-roll">{row.roll}</th>
                <td className="markbook-student">{row.label}</td>
                {data.periods.map((p, c) => {
                  const band = bandOf(r, c);
                  const remark = cellOf(r, c).remark;
                  const cellClass = `markbook-cell${band ? ` band-${band}` : ' band-empty'}`;
                  const aria = band
                    ? `${row.label}, ${p}: ${BAND_LABEL[band]}${remark ? `. ${remark}` : ''}`
                    : `${row.label}, ${p}: not yet recorded`;
                  if (mode === 'setup') {
                    return (
                      <td key={p} className="markbook-cell-wrap">
                        <button
                          type="button"
                          className={`${cellClass} markbook-cell-btn`}
                          onClick={() => cycle(r, c)}
                          aria-label={`${aria}. Select to change the band.`}
                          title={band ? BAND_LABEL[band] : 'Not yet recorded'}
                        >
                          <span className="markbook-cell-short">{band ? BAND_SHORT[band] : '+'}</span>
                        </button>
                      </td>
                    );
                  }
                  return (
                    <td key={p} className="markbook-cell-wrap">
                      <span className={cellClass} aria-label={aria} title={remark || (band ? BAND_LABEL[band] : 'Not yet recorded')}>
                        <span className="markbook-cell-short">{band ? BAND_SHORT[band] : '–'}</span>
                        {remark ? <span className="markbook-cell-note" aria-hidden="true" /> : null}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Band key ── */}
      <div className="markbook-key">
        {BAND_ORDER.map((b) => (
          <span className="markbook-key-item" key={b}>
            <span className={`markbook-key-swatch band-${b}`} aria-hidden="true" />
            {BAND_LABEL[b]}
          </span>
        ))}
        <span className="markbook-key-item">
          <span className="markbook-cell-note markbook-key-note" aria-hidden="true" />
          carries a remark
        </span>
      </div>

      {/* ── Remarks list — the evidence behind the bands ── */}
      {(() => {
        const remarks = data.rows.flatMap((row, r) =>
          row.cells
            .map((cell, c) => ({ cell, c }))
            .filter((x) => x.cell.remark)
            .map((x) => ({ label: row.label, period: data.periods[x.c]!, remark: x.cell.remark! })),
        );
        if (remarks.length === 0) return null;
        return (
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
            <div className="sec-head">
              <h5 className="h5" style={{ margin: 0 }}>Remarks</h5>
              <Tag tone="info">{remarks.length}</Tag>
            </div>
            <ul className="markbook-remarks">
              {remarks.map((x, i) => (
                <li className="markbook-remark" key={i}>
                  <Icon name="info" size="sm" />
                  <span className="body-sm">
                    <strong>{x.label}</strong> · {x.period} — {x.remark}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        );
      })()}

      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <EvidenceDrawer
          claim="How the markbook bands are read"
          confidence={data.confidence}
          evidence={[
            'Each cell is a plain-language band against the period target — your recorded judgement, never a raw percentage.',
            'A remark attaches the evidence behind a band, so the standing is explainable, not opaque.',
            'A learner never sees a number from here; the band is the teacher-facing record.',
          ]}
          whySeeing="Teachers still expect a markbook even though mastery is derived from evidence — this carries it in the v3 grammar, with bands and remarks instead of bare marks."
        />
        <span className="caption quiet">Bands, never raw marks · nothing publishes from here</span>
      </div>

      <SourceNote source={source} />
    </div>
  );
}
