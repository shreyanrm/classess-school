'use client';

import { useMemo } from 'react';
import { Button, ConfidenceBand, Icon, Tag } from '@classess/design-system';
import { DonutChart, DonutLegend, TrendLine } from './Charts';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { HolisticProgress, ObservationLine, ReadSource } from '@/lib/vizData';

/* ============================================================================
   HolisticProgressCard — the v2 signature report, carried into v3.

   One calm report surface that gathers: a plain-language executive summary, a
   competency distribution (DonutChart, plain bands — never a single grade),
   foundational literacy/numeracy strands as bars, a performance trend (the
   SHAPE), attendance analytics from plain counts, and teacher observations +
   PREPARED interventions (which wait for approval — they never auto-send).

   Re-expressed in the v3 grammar: bands not raw %, evidence-first (a ConfidenceBand
   + an EvidenceDrawer behind the read), the permission ladder (interventions are
   prepared, not fired), one cool accent per surface, depth = hairline + tonal,
   NEVER a shadow, reduced-motion safe.

   A clean PRINT / PDF path: a print button calls window.print(); the print
   stylesheet (.report-print scope in globals) drops the app chrome and lays the
   report out as a document. Pure + data-driven (takes a HolisticProgress prop).
   ============================================================================ */

const OBS_META: Record<ObservationLine['kind'], { label: string; tone: 'success' | 'info' | 'warning'; icon: 'success' | 'target' | 'spark' }> = {
  strength: { label: 'Strength', tone: 'success', icon: 'success' },
  focus: { label: 'Focus', tone: 'info', icon: 'target' },
  intervention: { label: 'Prepared step', tone: 'warning', icon: 'spark' },
};

export interface HolisticProgressCardProps {
  data: HolisticProgress;
  source?: ReadSource;
  /** Hide the six-dimension / teacher-only lens for student/parent audiences. */
  audience?: 'teacher' | 'parent' | 'student';
}

export function HolisticProgressCard({ data, source = 'fallback', audience = 'teacher' }: HolisticProgressCardProps) {
  const competencySegments = data.competencies.map((c) => ({
    label: c.band,
    value: c.count,
    accent: c.accent,
  }));
  const totalTopics = data.competencies.reduce((s, c) => s + c.count, 0);

  const attendancePct = useMemo(() => {
    const { present, half, schoolDays } = data.attendance;
    if (schoolDays <= 0) return 0;
    return Math.round(((present + half * 0.5) / schoolDays) * 100);
  }, [data.attendance]);

  function handlePrint() {
    if (typeof window !== 'undefined') window.print();
  }

  return (
    <article className="report-print stack" style={{ gap: 'var(--space-6)' }} data-testid="holistic-progress-card">
      {/* ── Head: document header + the print path (the print button is hidden in print) ── */}
      <header className="report-head">
        <div className="report-head-id">
          <p className="overline" style={{ margin: 0 }}>Holistic progress · {data.term}</p>
          <h2 className="h2" style={{ margin: '4px 0 0' }}>{data.subjectLabel}</h2>
          <p className="caption muted" style={{ margin: '4px 0 0' }}>{data.classLabel}</p>
        </div>
        <div className="report-head-actions no-print">
          <ConfidenceBand level={data.confidence} />
          <Button variant="secondary" size="sm" onClick={handlePrint} className="row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="chart" size="sm" /> Print / PDF
          </Button>
        </div>
      </header>

      {/* ── Executive summary — plain language, evidence behind it ── */}
      <section className="report-section">
        <p className="overline">In plain language</p>
        <p className="body" style={{ margin: '6px 0 0', maxWidth: '64ch' }}>{data.summary}</p>
        <div className="no-print" style={{ marginTop: 'var(--space-3)' }}>
          <EvidenceDrawer
            claim={`The basis for ${data.subjectLabel}'s progress read`}
            confidence={data.confidence}
            evidence={[
              'The read is corroborated across attempts and time — never a single score.',
              'Competency bands separate "can do with help" from "can do on their own", the keystone independence dimension.',
              'Attendance is built from plain, visible counts against days school was in session.',
            ]}
            whySeeing="A holistic card gathers the whole picture — competency, foundations, trend, attendance, and the prepared next steps — so a conversation has everything in one calm place."
          />
        </div>
      </section>

      {/* ── Competency distribution + performance trend ── */}
      <section className="report-grid-2">
        <div className="report-section">
          <p className="overline">Competency distribution</p>
          <div className="bloom-body" style={{ marginTop: 'var(--space-3)' }}>
            <DonutChart
              segments={competencySegments}
              aria-label={`Competency distribution across ${totalTopics} topics`}
              center={
                <span className="stack" style={{ gap: 0, alignItems: 'center' }}>
                  <span className="gauge-value" style={{ fontSize: 26 }}>{totalTopics}</span>
                  <span className="overline" style={{ margin: 0 }}>topics</span>
                </span>
              }
            />
            <DonutLegend segments={competencySegments} />
          </div>
        </div>
        <div className="report-section">
          <p className="overline">Performance trend</p>
          <div style={{ marginTop: 'var(--space-3)' }}>
            <TrendLine
              actual={data.trend.map((t) => t.value)}
              labels={data.trend.map((t) => t.label)}
              aria-label={`Independence trend for ${data.subjectLabel}`}
            />
          </div>
          <p className="caption muted" style={{ margin: 'var(--space-2) 0 0' }}>
            Share working on their own at each reading — the shape, not a grade.
          </p>
        </div>
      </section>

      {/* ── Foundational literacy & numeracy ── */}
      <section className="report-section">
        <p className="overline">Foundational literacy & numeracy</p>
        <div className="dims" style={{ marginTop: 'var(--space-3)' }}>
          {data.foundational.map((strand, i) => {
            const pct = Math.round(strand.strength * 100);
            const keystone = i === 0; // reading leads the strands visually
            return (
              <div className={`dim${keystone ? ' keystone' : ''}`} key={strand.label}>
                <div className="dim-label">
                  {strand.label}
                  <div className="caption quiet">{strand.read}</div>
                </div>
                <div
                  className="dim-track"
                  role="meter"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={pct}
                  aria-label={`${strand.label}: ${strand.read}`}
                >
                  <div className="dim-fill" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── Attendance analytics (plain counts) ── */}
      <section className="report-section">
        <p className="overline">Attendance</p>
        <div className="report-att" style={{ marginTop: 'var(--space-3)' }}>
          <div className="report-att-pct">
            <span className="gauge-value">{attendancePct}%</span>
            <span className="caption muted">present this term</span>
          </div>
          <div className="report-att-counts">
            <span className="report-att-count"><strong>{data.attendance.present}</strong> present</span>
            <span className="report-att-count"><strong>{data.attendance.half}</strong> half days</span>
            <span className="report-att-count"><strong>{data.attendance.leave}</strong> leave</span>
            <span className="report-att-count"><strong>{data.attendance.absent}</strong> absent</span>
            <span className="report-att-count"><strong>{data.attendance.schoolDays}</strong> school days</span>
          </div>
        </div>
      </section>

      {/* ── Observations + prepared interventions ── */}
      <section className="report-section">
        <p className="overline">Observations & prepared next steps</p>
        <ul className="report-obs" style={{ marginTop: 'var(--space-3)' }}>
          {data.observations.map((obs, i) => {
            const meta = OBS_META[obs.kind];
            return (
              <li className="report-obs-row" key={i}>
                <Icon name={meta.icon} size="sm" />
                <div>
                  <Tag tone={meta.tone}>{meta.label}</Tag>
                  <p className="body-sm" style={{ margin: '6px 0 0' }}>{obs.text}</p>
                </div>
              </li>
            );
          })}
        </ul>
        {audience === 'teacher' ? (
          <p className="caption quiet" style={{ margin: 'var(--space-3) 0 0' }}>
            Prepared steps wait for your approval — nothing is sent or assigned on its own.
          </p>
        ) : null}
      </section>

      <SourceNote source={source} />
    </article>
  );
}
