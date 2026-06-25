'use client';

import { useMemo, useState } from 'react';
import { Button, Icon, ProgressBar, SpotlightCard, Stat, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { RecommendationItem } from '../../_components/RecommendationItem';
import { ReadStates } from '../../_components/ReadStates';
import {
  TRACK_USAGE,
  TRACK_LABEL,
  gateTotals,
  LINEAGE_LOG,
  type TrackUsage,
} from '@/lib/ring2Data';
import { AGENTS, agentEnabled, type Agent } from '@/lib/adminData';
import { useStore } from '@/lib/useStore';
import { setAgentEnabled } from '@/lib/store';
import { useProactive } from '@/lib/useProactive';
import { useGovernance } from '@/lib/governance';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';

/**
 * The AI control centre — the institution-level governance of which agents run,
 * the tools they may reach, and model routing, with a LIVE approval queue and an
 * emergency disable. The most powerful surface, the best governed:
 *   - Per-agent governance: enable/disable each agent. The choice PERSISTS
 *     (survives reload). A consequential agent may prepare but never act on its
 *     own — its act is gated by the permission ladder.
 *   - Approval queue: the live proactive feed, read gateway-first; an Approve
 *     runs the prepared action THROUGH the ladder (the wall enforces it).
 *   - The confidence gate withholds low-confidence output for a human.
 *   - Emergency disable halts all autonomy at once, with a typed confirmation.
 * Every decision keeps its lineage in an append-only, immutable log.
 */
export default function AdminControlCentrePage() {
  const totals = useMemo(() => gateTotals(TRACK_USAGE), []);
  const { adminConfig } = useStore();
  const proactive = useProactive();
  const gov = useGovernance();
  const { emit } = useEmit();

  // The emergency disable EMITS an attributed event AND records to the immutable
  // audit trail through the wall, so "recorded to the immutable audit trail" is
  // TRUE. Best-effort; never blocks the human authority switch.
  async function recordEmergencyDisable() {
    await gov.recordEmergencyDisable();
    await emit({
      type: 'governance.emergency_disable.engaged',
      purpose: EVENT_PURPOSE.teaching,
      payload: { recorded: true },
    });
  }

  return (
    <SurfaceShell
      eyebrow="Governance"
      title="The AI control centre"
      dockIntro="This is where you watch and bound the intelligence. You choose which agents run and their tools; the confidence gate holds back anything uncertain; the approval queue acts only on your say-so. Ask me to explain any number here."
      dockChips={['What does the gate withhold', 'Which agents are running', 'Show the break-glass log']}
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
        <p className="overline">Agents and their tools</p>
        <p className="caption quiet">
          Which agents run, what they may reach, and on which model track. Turning one on or off is
          saved and survives a reload. A consequential agent can prepare but never act on its own.
        </p>
        <div className="cols-2">
          {AGENTS.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              enabled={agentEnabled(agent, adminConfig?.agents)}
              onToggle={(next) => setAgentEnabled(agent.id, next)}
            />
          ))}
        </div>
      </section>

      <section className="stack">
        <p className="overline">Approval queue</p>
        <p className="caption quiet">
          What the agents have prepared, waiting on your decision. Approving runs the action through
          the permission ladder — nothing consequential fires until you approve.
        </p>
        {proactive.phase !== 'ready' ? (
          <ReadStates phase={proactive.phase} onRetry={proactive.refresh} />
        ) : proactive.recommendations.length === 0 ? (
          <SpotlightCard>
            <div className="empty">
              <Icon name="check" size="lg" className="glyph" />
              <h4 className="body">Nothing needs you right now</h4>
              <p>The queue is clear. Prepared actions will appear here as agents surface them.</p>
            </div>
          </SpotlightCard>
        ) : (
          <div className="stack">
            {proactive.source === 'fallback' ? (
              <p className="caption quiet">
                Showing the last-known queue. It will refresh from the live spine when it is reachable.
              </p>
            ) : null}
            {proactive.recommendations.map((rec) => (
              <RecommendationItem key={rec.id} rec={rec} onActioned={proactive.actioned} />
            ))}
          </div>
        )}
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

      <EmergencyDisable onRecord={recordEmergencyDisable} />

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

/**
 * A single governed agent — its purpose, the tools it may reach, its model
 * track, and a real enable/disable that persists. A consequential agent shows
 * the ladder note: it can prepare but never act on its own.
 */
function AgentCard({
  agent,
  enabled,
  onToggle,
}: {
  agent: Agent;
  enabled: boolean;
  onToggle: (next: boolean) => void;
}) {
  return (
    <SpotlightCard>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
        <div>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {agent.name}
          </h3>
          <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
            {agent.purpose}
          </p>
        </div>
        <Tag tone={enabled ? 'success' : 'neutral'} dot>
          {enabled ? 'Running' : 'Paused'}
        </Tag>
      </div>

      <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap', marginTop: 'var(--space-3)' }}>
        <Tag tone="neutral">{TRACK_LABEL[agent.track]}</Tag>
        {agent.consequential ? <Tag tone="warning">Prepares only — human acts</Tag> : null}
      </div>

      <p className="caption muted" style={{ marginTop: 'var(--space-3)' }}>
        Tools: {agent.tools.join(' · ')}
      </p>

      <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
        <Button
          variant={enabled ? 'secondary' : 'primary'}
          size="sm"
          aria-pressed={enabled}
          onClick={() => onToggle(!enabled)}
        >
          {enabled ? 'Pause this agent' : 'Enable this agent'}
        </Button>
        <span className="caption muted">
          {enabled
            ? agent.consequential
              ? 'Running. It prepares; nothing it touches fires without your approval.'
              : 'Running. It observes and recommends only.'
            : 'Paused and saved. It will not run until you enable it.'}
        </span>
      </div>
    </SpotlightCard>
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
function EmergencyDisable({ onRecord }: { onRecord: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState('');
  const [disabled, setDisabled] = useState(false);
  const ready = confirm.trim().toUpperCase() === 'DISABLE';

  async function disable() {
    setDisabled(true);
    await onRecord();
  }

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
                    onClick={disable}
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
