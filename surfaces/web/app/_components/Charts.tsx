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
