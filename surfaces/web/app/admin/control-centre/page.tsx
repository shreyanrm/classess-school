'use client';

import { useMemo, useState } from 'react';
import { Button, Icon, ProgressBar, SpotlightCard, Stat, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import {
  TRACK_USAGE,
  TRACK_LABEL,
  gateTotals,
  LINEAGE_LOG,
  type TrackUsage,
} from '@/lib/ring2Data';

/**
 * The AI control centre — model usage with a clear Track 1 / Track 2 split, the
 * confidence-gate pass/withhold picture, an emergency-disable control that takes
 * an explicit human confirmation, and the break-glass + lineage view. Autonomy
 * is always bounded: the gate withholds low-confidence output for a human, and
 * nothing consequential auto-fires.
 */
export default function AdminControlCentrePage() {
  const totals = useMemo(() => gateTotals(TRACK_USAGE), []);

  return (
    <SurfaceShell
      eyebrow="Governance"
      title="The AI control centre"
      dockIntro="This is where you watch and bound the intelligence. The confidence gate holds back anything uncertain for a human. Track 1 and Track 2 are reported apart. Ask me to explain any number here."
      dockChips={['What does the gate withhold', 'Track 1 vs Track 2', 'Show the break-glass log']}
    >
      <section className="stack">
        <p className="overline">Confidence gate, this window</p>
        <div className="cols-2">
          <Stat label="Model calls" value={totals.calls} />
          <Stat label="Passed the gate" value={totals.passed} delta="provisional auto" deltaDir="up" />
          <Stat label="Withheld for review" value={totals.withheld} delta="held for a human" />
          <Stat label="Pass rate" value={totals.passRate} suffix="%" />
        </div>
        <SpotlightCard>
          <div className="row-between">
            <span className="body-sm">Output released vs held by the confidence gate</span>
            <span className="caption muted">{totals.passRate}% released</span>
          </div>
          <ProgressBar
            value={totals.passRate}
            accent
            label="Share of model output the confidence gate released as provisional"
            style={{ marginTop: 'var(--space-3)' }}
          />
          <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
            Output below the gate is never shown as final. It waits for a human read — this is the
            generate-and-verify rule, made visible.
          </p>
        </SpotlightCard>
      </section>

      <section className="stack">
        <p className="overline">Model usage by track</p>
        <p className="caption quiet">
          The open-standards track and the proprietary/edge track are reported and governed
          separately, never blended.
        </p>
        <div className="cols-2">
          {TRACK_USAGE.map((u) => (
            <TrackCard key={u.track} usage={u} />
          ))}
        </div>
      </section>

      <EmergencyDisable />

      <section className="stack">
        <p className="overline">Break-glass and lineage</p>
        <p className="caption quiet">
          Privileged actions are break-glass and every model decision keeps its lineage. This log is
          append-only and immutable — a read, never an edit.
        </p>
        <div className="admin-list">
          {LINEAGE_LOG.map((r) => (
            <div key={r.id} className="admin-list-row">
              <div>
                <div className="body-sm row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                  {r.breakGlass ? <Tag tone="warning">Break-glass</Tag> : null}
                  {r.action}
                </div>
                <div className="caption muted">{r.actor}</div>
              </div>
              <span className="caption muted" style={{ whiteSpace: 'nowrap' }}>
                {r.when}
              </span>
            </div>
          ))}
        </div>
      </section>
    </SurfaceShell>
  );
}

function TrackCard({ usage }: { usage: TrackUsage }) {
  const passRate = usage.calls === 0 ? 0 : Math.round((usage.passed / usage.calls) * 100);
  return (
    <SpotlightCard>
      <div className="row-between" style={{ alignItems: 'flex-start' }}>
        <div>
          <p className="overline" style={{ margin: 0 }}>
            {TRACK_LABEL[usage.track]}
          </p>
          <h3 className="body-lg" style={{ margin: 'var(--space-2) 0 0' }}>
            {usage.modelLabel}
          </h3>
        </div>
        <Tag tone="neutral">{usage.calls} calls</Tag>
      </div>
      <ProgressBar
        value={passRate}
        accent
        label={`Share of ${usage.modelLabel} output released by the confidence gate`}
        style={{ marginTop: 'var(--space-4)' }}
      />
      <div className="row-between" style={{ marginTop: 'var(--space-3)' }}>
        <span className="caption muted">{usage.passed} passed</span>
        <span className="caption muted">{usage.withheld} withheld</span>
      </div>
    </SpotlightCard>
  );
}

/**
 * Emergency disable — a single human-authority switch that halts all model
 * autonomy at once. It never one-clicks: it takes an explicit typed confirmation,
 * states exactly what stops, and remains the human's to engage and to restore.
 */
function EmergencyDisable() {
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState('');
  const [disabled, setDisabled] = useState(false);
  const ready = confirm.trim().toUpperCase() === 'DISABLE';

  return (
    <section className="stack">
      <p className="overline">Emergency disable</p>
      <SpotlightCard padLg>
        <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'flex-start' }}>
          <Icon name="danger" size="lg" />
          <div style={{ flex: 1 }}>
            <h3 className="body-lg" style={{ margin: 0 }}>
              Halt all model autonomy
            </h3>
            <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
              This stops every model from drafting, recommending, or preparing across all campuses.
              People keep full access; only the intelligence pauses. It is recorded to the immutable
              audit trail and stays paused until you restore it.
            </p>

            {disabled ? (
              <div className="row-between" style={{ marginTop: 'var(--space-4)' }}>
                <span className="body-sm row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                  <Tag tone="danger" dot>
                    Models paused
                  </Tag>
                  Autonomy is halted and recorded. People are unaffected.
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setDisabled(false);
                    setOpen(false);
                    setConfirm('');
                  }}
                >
                  Restore autonomy
                </Button>
              </div>
            ) : !open ? (
              <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                <Button variant="danger" size="sm" onClick={() => setOpen(true)}>
                  Begin emergency disable
                </Button>
              </div>
            ) : (
              <div style={{ marginTop: 'var(--space-4)' }}>
                <label className="caption muted" htmlFor="ed-confirm">
                  Type DISABLE to confirm you are halting all model autonomy.
                </label>
                <input
                  id="ed-confirm"
                  className="input"
                  style={{ marginTop: 'var(--space-2)', width: '100%' }}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="DISABLE"
                  autoComplete="off"
                />
                <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
                  <Button
                    variant="danger"
                    size="sm"
                    disabled={!ready}
                    onClick={() => setDisabled(true)}
                  >
                    Disable and record
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setOpen(false);
                      setConfirm('');
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </SpotlightCard>
    </section>
  );
}
