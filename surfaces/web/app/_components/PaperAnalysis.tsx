'use client';

import { ConfidenceBand, Icon, Tag } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { BandDistribution, PaperAnalysis as PaperAnalysisData, ReadSource } from '@/lib/vizData';

/* ============================================================================
   PaperAnalysis — the v2 paper-analysis + remedial-grouping feature, in v3.

   A target-band distribution (Below / On / Above target) shown as a calm
   stacked bar (cool ramp, never raw marks), a per-period breakdown with its own
   distribution and a plain read, and PREPARED remedial groups — who is in each
   group, on what, and the prepared step that waits for approval (it never
   auto-fires).

   v3 grammar: bands not single scores, evidence-first, the permission ladder on
   the remedial step, subjects on the cool accent palette, depth = hairline +
   tonal step, NO shadow, reduced-motion safe. Pure + data-driven.
   ============================================================================ */

const BAND_LABEL: Record<keyof BandDistribution, string> = {
  below: 'Below target',
  on: 'On target',
  above: 'Above target',
};

/** A calm stacked bar — one cool ramp: below (sunken+hairline), on (tint), above (accent). */
function BandBar({ dist, subject }: { dist: BandDistribution; subject?: string }) {
  const total = dist.below + dist.on + dist.above || 1;
  const seg = (n: number) => `${(n / total) * 100}%`;
  const accent = subject ? `var(--${subject})` : 'var(--accent)';
  return (
    <div
      className="band-bar"
      role="img"
      aria-label={`${dist.below} below target, ${dist.on} on target, ${dist.above} above target`}
    >
      <span className="band-seg band-below" style={{ width: seg(dist.below) }} title={`Below target: ${dist.below}`} />
      <span
        className="band-seg band-on"
        style={{ width: seg(dist.on), background: `color-mix(in srgb, ${accent} 22%, transparent)`, borderColor: accent }}
        title={`On target: ${dist.on}`}
      />
      <span className="band-seg band-above" style={{ width: seg(dist.above), background: accent }} title={`Above target: ${dist.above}`} />
    </div>
  );
}

function BandKey({ dist }: { dist: BandDistribution }) {
  return (
    <div className="band-key">
      <span className="band-key-item"><span className="band-key-swatch band-below" /> {BAND_LABEL.below} · {dist.below}</span>
      <span className="band-key-item"><span className="band-key-swatch band-on" /> {BAND_LABEL.on} · {dist.on}</span>
      <span className="band-key-item"><span className="band-key-swatch band-above" /> {BAND_LABEL.above} · {dist.above}</span>
    </div>
  );
}

export interface PaperAnalysisProps {
  data: PaperAnalysisData;
  source?: ReadSource;
}

export function PaperAnalysis({ data, source = 'fallback' }: PaperAnalysisProps) {
  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-5)' }}>
      <div className="sec-head">
        <div>
          <p className="overline" style={{ margin: 0 }}>Paper analysis · {data.classLabel}</p>
          <h4 className="h4" style={{ margin: '4px 0 0' }}>{data.title}</h4>
        </div>
        <ConfidenceBand level={data.confidence} />
      </div>

      {/* ── Overall target-band distribution ── */}
      <div className="stack" style={{ gap: 'var(--space-3)' }}>
        <div className="sec-head">
          <h5 className="h5" style={{ margin: 0 }}>Across the {data.total} students</h5>
          <span className="overline">target bands</span>
        </div>
        <BandBar dist={data.overall} />
        <BandKey dist={data.overall} />
      </div>

      {/* ── Per-period breakdown ── */}
      <div className="stack" style={{ gap: 'var(--space-3)' }}>
        <h5 className="h5" style={{ margin: 0 }}>By period</h5>
        <ul className="paper-periods">
          {data.periods.map((period) => (
            <li className="paper-period" key={period.label}>
              <div className="paper-period-head">
                <span className="subject-dot" style={{ background: `var(--${period.subject})` }} aria-hidden="true" />
                <span className="paper-period-label">{period.label}</span>
              </div>
              <BandBar dist={period.distribution} subject={period.subject} />
              <p className="caption muted" style={{ margin: 0 }}>{period.note}</p>
            </li>
          ))}
        </ul>
      </div>

      {/* ── Prepared remedial groups ── */}
      <div className="stack" style={{ gap: 'var(--space-3)' }}>
        <div className="sec-head">
          <h5 className="h5" style={{ margin: 0 }}>Prepared remedial groups</h5>
          <Tag tone="warning">{data.remedial.length} prepared</Tag>
        </div>
        {data.remedial.length === 0 ? (
          <div className="empty">
            <Icon name="success" size="lg" className="glyph" />
            <h4 className="body">No remedial grouping needed</h4>
            <p>No below-target cluster was confirmed from corroborated evidence.</p>
          </div>
        ) : (
          <ul className="paper-remedials">
            {data.remedial.map((group, i) => (
              <li className="paper-remedial subject-tinted" data-subject={group.subject} key={i}>
                <div className="paper-remedial-head">
                  <span className="paper-remedial-topic">{group.topic}</span>
                  <span className="caption muted">{group.members.length} students</span>
                </div>
                <div className="paper-remedial-members">
                  {group.members.map((m) => (
                    <span className="chip-soft" key={m}>{m}</span>
                  ))}
                </div>
                <p className="body-sm" style={{ margin: 0 }}>{group.preparedStep}</p>
              </li>
            ))}
          </ul>
        )}
        <p className="caption quiet" style={{ margin: 0 }}>
          Remedial steps are prepared and wait for your approval — nothing is assigned on its own.
        </p>
      </div>

      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <EvidenceDrawer
          claim="How the target bands are read"
          confidence={data.confidence}
          evidence={[
            'Each student is placed in a band against the period target — below, on, or above — from corroborated work, not a single item.',
            'A remedial group forms only when a below-target cluster is confirmed across the period, never from one low result.',
          ]}
          whySeeing="Showing bands and groups, not raw marks, keeps the focus on who needs which support next — and the prepared step waits for you."
        />
      </div>

      <SourceNote source={source} />
    </div>
  );
}
