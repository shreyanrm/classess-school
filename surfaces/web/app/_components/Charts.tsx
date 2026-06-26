'use client';

import { useId } from 'react';
import { ConfidenceBand, type SubjectAccent } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type {
  BloomDistribution,
  PerformanceTrend as PerformanceTrendData,
  SuccessProbability,
  ReadSource,
} from '@/lib/vizData';

/* ============================================================================
   Charts — the SVG-based, on-brand viz primitives shared across roles:
     • DonutChart    — a hairline-segmented ring (no chart lib)
     • TrendLine     — actual (solid) + predicted (dotted) line, by SHAPE
     • ArcGauge      — a single-arc success-probability gauge
   and the surface-facing wrappers that wear the v3 grammar:
     • BloomTaxonomy   (donut of cognitive levels)
     • PerformanceTrend (line + plain read + evidence)
     • SuccessGauge     (probability as an honest direction; plain read for
                         students, the % stays teacher/parent-side)

   All cool/brand only (subject accents from the SubjectAccent palette; the
   signature ultramarine only for the brand-level read). Depth = hairline +
   tonal. No shadow. Reduced-motion safe (no transitions that animate position;
   the donut/line are static geometry). PURE + data-driven.
   ============================================================================ */

/* ----------------------------------------------------------------------------
   DonutChart — segments drawn as stroked arcs on one circle. Each segment is a
   cool/brand subject hue (via the inline stroke var); gaps are the hairline.
   -------------------------------------------------------------------------- */
export interface DonutSegment {
  label: string;
  value: number;
  /** A cool/brand accent name — resolved to var(--<accent>). */
  accent: SubjectAccent;
}

export interface DonutChartProps {
  segments: DonutSegment[];
  /** Diameter in px. */
  size?: number;
  /** Ring thickness in px. */
  thickness?: number;
  /** A centred caption (e.g. a total or a label). */
  center?: React.ReactNode;
  'aria-label'?: string;
}

export function DonutChart({
  segments,
  size = 168,
  thickness = 20,
  center,
  'aria-label': ariaLabel,
}: DonutChartProps) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = (size - thickness) / 2;
  const c = size / 2;
  const circumference = 2 * Math.PI * r;
  // A small gap between segments reveals the surface as a hairline separator.
  const gap = segments.length > 1 ? 1.5 : 0;

  let offset = 0;
  return (
    <div className="donut" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label={ariaLabel}>
        {/* the track — the calm sunken ring beneath */}
        <circle cx={c} cy={c} r={r} fill="none" stroke="var(--bg-sunken)" strokeWidth={thickness} />
        {segments.map((seg, i) => {
          const frac = seg.value / total;
          const len = Math.max(0, frac * circumference - gap);
          const dash = `${len} ${circumference - len}`;
          const el = (
            <circle
              key={i}
              cx={c}
              cy={c}
              r={r}
              fill="none"
              stroke={`var(--${seg.accent})`}
              strokeWidth={thickness}
              strokeDasharray={dash}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${c} ${c})`}
            >
              <title>{`${seg.label}: ${Math.round(frac * 100)}%`}</title>
            </circle>
          );
          offset += frac * circumference;
          return el;
        })}
      </svg>
      {center ? <div className="donut-center">{center}</div> : null}
    </div>
  );
}

/** A small legend for a donut — swatch · label · value. */
export function DonutLegend({ segments }: { segments: DonutSegment[] }) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  return (
    <ul className="donut-legend">
      {segments.map((seg, i) => (
        <li className="donut-legend-item" key={i}>
          <span className="subject-dot" style={{ background: `var(--${seg.accent})` }} aria-hidden="true" />
          <span className="donut-legend-label">{seg.label}</span>
          <span className="data donut-legend-value">{Math.round((seg.value / total) * 100)}%</span>
        </li>
      ))}
    </ul>
  );
}

/* ----------------------------------------------------------------------------
   TrendLine — actual (solid) + predicted (dotted), one shared 0..100 y axis.
   Reuses the .trajectory-* tokens already in globals. A direction, never a grade.
   -------------------------------------------------------------------------- */
export interface TrendLineProps {
  /** 0..100 values, oldest -> newest. */
  actual: number[];
  /** 0..100 predicted continuation; begins at the last actual point. */
  predicted?: number[];
  /** Column labels under the axis (one per actual point). */
  labels?: string[];
  'aria-label'?: string;
}

const TL_W = 640;
const TL_H = 200;
const TL_PAD = 16;

function projectLine(values: number[], offset: number, total: number): string {
  return values
    .map((v, i) => {
      const x = TL_PAD + ((offset + i) / Math.max(1, total - 1)) * (TL_W - TL_PAD * 2);
      const y = TL_H - TL_PAD - (v / 100) * (TL_H - TL_PAD * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

export function TrendLine({ actual, predicted = [], labels, 'aria-label': ariaLabel }: TrendLineProps) {
  const total = actual.length + Math.max(0, predicted.length - 1);
  const actualPts = projectLine(actual, 0, total);
  const predictedPts =
    predicted.length > 0 ? projectLine(predicted, actual.length - 1, total) : '';

  return (
    <div className="stack" style={{ gap: 'var(--space-2)' }}>
      <div className="trajectory" role="img" aria-label={ariaLabel}>
        <svg viewBox={`0 0 ${TL_W} ${TL_H}`} preserveAspectRatio="none" className="trajectory-svg">
          <line x1={TL_PAD} y1={TL_H - TL_PAD} x2={TL_W - TL_PAD} y2={TL_H - TL_PAD} className="trajectory-grid" />
          <line x1={TL_PAD} y1={TL_H / 2} x2={TL_W - TL_PAD} y2={TL_H / 2} className="trajectory-grid" />
          <polyline points={actualPts} className="trajectory-actual" />
          {predictedPts ? <polyline points={predictedPts} className="trajectory-predicted" /> : null}
        </svg>
      </div>
      {labels && labels.length > 0 ? (
        <div className="trend-axis">
          {labels.map((l, i) => (
            <span className="data trend-axis-label" key={i}>
              {l}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/* ----------------------------------------------------------------------------
   ArcGauge — one 240deg arc; the fill is the surface accent. A direction read,
   never a promise. The numeric is optional (teacher/parent only).
   -------------------------------------------------------------------------- */
export interface ArcGaugeProps {
  /** 0..1. */
  value: number;
  /** Show the numeric percent in the centre (off for the student read). */
  showValue?: boolean;
  /** A short label under the value. */
  label?: string;
  size?: number;
  'aria-label'?: string;
}

export function ArcGauge({ value, showValue = true, label, size = 180, 'aria-label': ariaLabel }: ArcGaugeProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const stroke = 16;
  const r = (size - stroke) / 2;
  const c = size / 2;
  // 240deg sweep, centred at the bottom (gap of 120deg at the base).
  const startAngle = 150; // degrees
  const sweep = 240;
  const circumference = 2 * Math.PI * r;
  const arcLen = (sweep / 360) * circumference;
  const filled = arcLen * clamped;
  const uid = useId();

  return (
    <div className="gauge" style={{ width: size, height: size * 0.74 }}>
      <svg viewBox={`0 0 ${size} ${size * 0.74}`} width={size} role="img" aria-label={ariaLabel}>
        <g transform={`rotate(${startAngle} ${c} ${c})`}>
          {/* track */}
          <circle
            cx={c}
            cy={c}
            r={r}
            fill="none"
            stroke="var(--bg-sunken)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${arcLen} ${circumference - arcLen}`}
          />
          {/* fill — the surface accent */}
          <circle
            cx={c}
            cy={c}
            r={r}
            fill="none"
            stroke="var(--accent)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference - filled}`}
            data-gauge-fill={uid}
          />
        </g>
      </svg>
      {showValue ? (
        <div className="gauge-center">
          <span className="gauge-value">{Math.round(clamped * 100)}%</span>
          {label ? <span className="caption muted gauge-label">{label}</span> : null}
        </div>
      ) : null}
    </div>
  );
}

/* ============================================================================
   Surface-facing wrappers — wear the v3 grammar (overline, evidence, source).
   ============================================================================ */

export function BloomTaxonomy({
  data,
  source = 'fallback',
}: {
  data: BloomDistribution;
  source?: ReadSource;
}) {
  const segments: DonutSegment[] = data.slices.map((s) => ({
    label: s.level,
    value: s.share,
    accent: s.accent,
  }));
  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-4)' }}>
      <div className="sec-head">
        <h4 className="h4" style={{ margin: 0 }}>
          Thinking levels
        </h4>
        <span className="overline">{data.topicLabel}</span>
      </div>
      <div className="bloom-body">
        <DonutChart
          segments={segments}
          aria-label={`Cognitive levels across ${data.topicLabel}`}
          center={<span className="overline" style={{ margin: 0 }}>Bloom</span>}
        />
        <DonutLegend segments={segments} />
      </div>
      <p className="body-sm" style={{ margin: 0 }}>{data.read}</p>
      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <ConfidenceBand level={data.confidence} />
        <EvidenceDrawer
          claim="How the thinking-level mix is read"
          confidence={data.confidence}
          evidence={[
            'Each demonstrated piece of work is tagged to the cognitive level it required — recalling, understanding, applying, analysing, or creating.',
            'The ring is the share of work at each level, not a grade; it shows where the thinking is concentrated.',
          ]}
          whySeeing="Seeing the mix tells you whether the next stretch is more higher-order work — analysing and creating — rather than only recall."
        />
      </div>
      <SourceNote source={source} />
    </div>
  );
}

export function PerformanceTrend({
  data,
  source = 'fallback',
}: {
  data: PerformanceTrendData;
  source?: ReadSource;
}) {
  const labels = [...data.points.map((p) => p.label), ...data.predicted.slice(1).map((p) => p.label)];
  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-3)' }}>
      <div className="sec-head">
        <h4 className="h4" style={{ margin: 0 }}>
          Performance trend
        </h4>
        <span className="overline">direction, not a grade</span>
      </div>
      <TrendLine
        actual={data.points.map((p) => p.value)}
        predicted={data.predicted.map((p) => p.value)}
        labels={labels}
        aria-label={`${data.topicLabel}. ${data.read}`}
      />
      <div className="row" style={{ gap: 'var(--space-4)', flexWrap: 'wrap' }}>
        <span className="caption muted row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
          <span className="trajectory-key" aria-hidden="true" /> So far
        </span>
        <span className="caption muted row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
          <span className="trajectory-key trajectory-key-predicted" aria-hidden="true" /> Projected
        </span>
      </div>
      <p className="body-sm" style={{ margin: 0 }}>{data.read}</p>
      <SourceNote source={source} />
    </div>
  );
}

/* ----------------------------------------------------------------------------
   EffortOutcomeScatter — a small bubble plot of prep-effort vs where it landed.
   Each bubble is one topic: x = how much practice you put in (pieces of your own
   work), y = how far it has landed (a plain band — never a raw score), and the
   bubble grows with how much of that work you did unaided. The hue is the topic's
   subject accent (cool/brand only). The signal it carries: effort generally
   lifts outcome, and the topics sitting low-left are where a little practice goes
   furthest. Hairline + tonal, NO shadow; static SVG geometry, reduced-motion safe.
   -------------------------------------------------------------------------- */
export interface ScatterPoint {
  /** Topic label, shown on hover (title) + in the legend list. */
  label: string;
  /** Practice effort — pieces of your own work (drives the x position). */
  effort: number;
  /** Outcome 0..1 — how far it has landed (drives the y position). NOT shown numerically. */
  outcome: number;
  /** 0..1 share of the work that was unaided — drives the bubble radius + ring. */
  independence: number;
  /** Cool/brand subject accent. */
  accent: SubjectAccent;
  /** True when the topic is genuinely standing on its own (a filled bubble). */
  independent?: boolean;
}

const SC_W = 580;
const SC_H = 280;
const SC_PAD_L = 96;
const SC_PAD_B = 44;
const SC_PAD_T = 18;
const SC_PAD_R = 24;

/** A plain band for the y axis — never a number. The full word is in the title. */
const OUTCOME_BANDS = ['Starting', 'With support', 'Developing', 'Reliable', 'On your own'];

export function EffortOutcomeScatter({ points }: { points: ScatterPoint[] }) {
  const maxEffort = Math.max(4, ...points.map((p) => p.effort));
  const plotW = SC_W - SC_PAD_L - SC_PAD_R;
  const plotH = SC_H - SC_PAD_T - SC_PAD_B;
  const x = (effort: number) => SC_PAD_L + (effort / maxEffort) * plotW;
  const y = (outcome: number) => SC_PAD_T + (1 - Math.max(0, Math.min(1, outcome))) * plotH;
  // Bubble radius eases with independence so unaided wins read larger.
  const radius = (p: ScatterPoint) => 6 + p.independence * 9;

  // Four horizontal band guides at the quarter lines (the y "labels").
  const bandLines = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="scatter" role="img" aria-label="Practice effort against where each topic has landed. Topics with more of your own work generally sit higher.">
      <svg viewBox={`0 0 ${SC_W} ${SC_H}`} preserveAspectRatio="xMidYMid meet" className="scatter-svg">
        {/* horizontal band guides + their plain labels */}
        {bandLines.map((b, i) => {
          const yy = y(b);
          return (
            <g key={b}>
              <line x1={SC_PAD_L} y1={yy} x2={SC_W - SC_PAD_R} y2={yy} className="scatter-grid" />
              <text x={SC_PAD_L - 8} y={yy + 3} textAnchor="end" className="scatter-axis-label">
                {OUTCOME_BANDS[i]}
              </text>
            </g>
          );
        })}
        {/* axes */}
        <line x1={SC_PAD_L} y1={SC_PAD_T} x2={SC_PAD_L} y2={SC_H - SC_PAD_B} className="scatter-axis" />
        <line x1={SC_PAD_L} y1={SC_H - SC_PAD_B} x2={SC_W - SC_PAD_R} y2={SC_H - SC_PAD_B} className="scatter-axis" />
        {/* x ticks — effort, in pieces of work */}
        {[0, Math.round(maxEffort / 2), maxEffort].map((t, i) => (
          <text key={i} x={x(t)} y={SC_H - SC_PAD_B + 16} textAnchor="middle" className="scatter-axis-label">
            {t}
          </text>
        ))}
        <text x={SC_PAD_L + plotW / 2} y={SC_H - 6} textAnchor="middle" className="scatter-axis-caption">
          pieces of your own work →
        </text>
        {/* bubbles */}
        {points.map((p, i) => {
          const r = radius(p);
          const stroke = `var(--${p.accent})`;
          return (
            <circle
              key={`${p.label}-${i}`}
              cx={x(p.effort)}
              cy={y(p.outcome)}
              r={r}
              fill={p.independent ? stroke : `var(--${p.accent}-tint)`}
              stroke={stroke}
              strokeWidth={1}
              className="scatter-bubble"
              style={{ ['--reveal-delay' as string]: `${i * 60}ms` }}
            >
              <title>{`${p.label}: ${OUTCOME_BANDS[Math.round(p.outcome * 4)]}, ${p.effort} ${p.effort === 1 ? 'piece' : 'pieces'} of work`}</title>
            </circle>
          );
        })}
      </svg>
      <ul className="scatter-legend">
        {points.map((p, i) => (
          <li className="scatter-legend-item" key={`${p.label}-${i}`}>
            <span
              className="subject-dot"
              style={{
                background: p.independent ? `var(--${p.accent})` : `var(--${p.accent}-tint)`,
                borderColor: `var(--${p.accent})`,
              }}
              aria-hidden="true"
            />
            <span className="scatter-legend-label">{p.label}</span>
            <span className="data scatter-legend-value">
              {p.effort} {p.effort === 1 ? 'piece' : 'pieces'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EffortOutcomeCard({
  points,
  source = 'fallback',
}: {
  points: ScatterPoint[];
  source?: ReadSource;
}) {
  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-3)' }}>
      <div className="sec-head">
        <h4 className="h4" style={{ margin: 0 }}>
          Practice and where it lands
        </h4>
        <span className="overline">effort, not a grade</span>
      </div>
      <EffortOutcomeScatter points={points} />
      <p className="body-sm" style={{ margin: 0 }}>
        Each bubble is a topic — further right means more of your own practice, higher up means it has
        landed more firmly. A bigger, filled bubble is work you did unaided. The pattern is honest: the
        practice you put in is what lifts a topic, and the bubbles sitting low-left are where a little
        more goes furthest.
      </p>
      <EvidenceDrawer
        claim="How this is read"
        evidence={[
          'The x position is the count of your own attempts and checks on each topic — pieces of your work, not a timer.',
          'The y position is a plain band read from that same evidence; it is never surfaced as a number or a percentage.',
          'A larger, filled bubble means more of the work on that topic was unaided — the share that lights the spark.',
        ]}
        whySeeing="Seeing effort against outcome together makes the next move obvious: the topics low and to the left repay a short, focused practice the most."
      />
      <SourceNote source={source} />
    </div>
  );
}

export function SuccessGauge({
  data,
  source = 'fallback',
  /** Students see the plain read only; teachers/parents see the percentage. */
  showValue = true,
}: {
  data: SuccessProbability;
  source?: ReadSource;
  showValue?: boolean;
}) {
  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-3)' }}>
      <div className="sec-head">
        <h4 className="h4" style={{ margin: 0 }}>
          Where this is heading
        </h4>
        <span className="overline">a likelihood, not a promise</span>
      </div>
      <div className="gauge-body">
        <ArcGauge
          value={data.probability}
          showValue={showValue}
          label="on the current pace"
          aria-label={`Likelihood read. ${data.read}`}
        />
        <div className="stack" style={{ gap: 'var(--space-2)' }}>
          <p className="body-sm" style={{ margin: 0 }}>{data.read}</p>
          <p className="caption muted" style={{ margin: 0 }}>
            <strong style={{ color: 'var(--text-primary)' }}>Lifts it fastest:</strong> {data.lever}
          </p>
        </div>
      </div>
      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <ConfidenceBand level={data.confidence} />
        <EvidenceDrawer
          claim="How this likelihood is read"
          confidence={data.confidence}
          evidence={[
            'It projects the current trend forward using the same mastery evidence the trend line draws from.',
            'It recalculates as fresh evidence arrives — a direction, never a fixed grade or a promise.',
          ]}
          whySeeing="Showing a likelihood keeps the read honest: it is a direction to act on, with the single lever that moves it most."
        />
      </div>
      <SourceNote source={source} />
    </div>
  );
}
