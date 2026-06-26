'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Button, Icon, Matrix, ProgressBar, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { RecommendationItem } from '../../_components/RecommendationItem';
import { ReadStates } from '../../_components/ReadStates';
import { KnowledgeBase } from '../../_components/KnowledgeBase';
import { useAdminConfig } from '@/lib/adminConfig';
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
 * The AI control centre — recomposed to the sample-page bar. The most powerful
 * surface, the best governed, now reads as a dense composed console: a page-head
 * with a mono meta line + tab strip, a count-up confidence-gate stat matrix, then
 * cols (the agents-and-tools cell matrix + the live approval queue + the
 * per-track usage on the main; the gate ignite-card, the break-glass / lineage
 * flag panel, and a handnote on the 320px aside). All wiring is preserved:
 * per-agent enable persists, the approval queue is gateway-first through the
 * proactive loop, the emergency disable records to the immutable audit trail.
 */
type Mode = 'console' | 'knowledge';

export default function AdminControlCentrePage() {
  const totals = useMemo(() => gateTotals(TRACK_USAGE), []);
  const { adminConfig } = useStore();
  const proactive = useProactive();
  const gov = useGovernance();
  const { emit } = useEmit();
  // The knowledge base persists its governance gate through the admin-config
  // seam (same wall, same immutable event store); the active lens persists too.
  const kb = useAdminConfig('control-centre');
  const mode: Mode = kb.config.mode === 'knowledge' ? 'knowledge' : 'console';
  const setMode = (m: Mode) => {
    void kb.set('mode', m);
  };

  const runningAgents = AGENTS.filter((a) => agentEnabled(a, adminConfig?.agents)).length;

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
      breadcrumb={[{ label: 'School', href: '/' }, { label: 'Control centre' }]}
      meta={[
        { value: runningAgents, label: `of ${AGENTS.length} agents running` },
        { value: `${totals.passRate}%`, label: 'passed the gate' },
        { value: totals.withheld, label: 'held for a human' },
      ]}
      tabs={[
        { label: 'Control centre', active: mode === 'console', onClick: () => setMode('console') },
        { label: 'Knowledge base', active: mode === 'knowledge', onClick: () => setMode('knowledge') },
        { label: 'Governance', href: '/admin/governance' },
        { label: 'Integrations', href: '/admin/integrations' },
      ]}
      actions={
        <Link href="/admin/governance" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="settings" size="sm" />
          Policy and permissions
        </Link>
      }
      dockIntro={
        mode === 'knowledge'
          ? 'This is your institution’s knowledge base. Add your own documents — handbook, policies, syllabus — and I can ground my answers in them, but only when you turn the reference gate on. A new document waits at the gate until you make it available. I never read the file’s contents here.'
          : 'This is where you watch and bound the intelligence. You choose which agents run and their tools; the confidence gate holds back anything uncertain; the approval queue acts only on your say-so. Ask me to explain any number here.'
      }
      dockChips={
        mode === 'knowledge'
          ? ['Add a reference document', 'What does the reference gate do', 'Is any file content stored']
          : ['What does the gate withhold', 'Which agents are running', 'Show the break-glass log']
      }
      aside={
        mode === 'knowledge' ? (
          <>
            <div className="ignite-card reveal reveal-2">
              <div className="row-between" style={{ marginBottom: 14 }}>
                <span className="overline">Grounded, not generic</span>
                <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
              </div>
              <div className="who">Vidya can reference your own documents</div>
              <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                Your handbook and policies become reference material — but only when you turn the gate
                on. Off by default; you hold it.
              </p>
            </div>

            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>The reference ladder</h4>
                <Tag tone="info" dot>prepare → make available</Tag>
              </div>
              <p className="caption" style={{ marginBottom: 12 }}>
                A document is added, then prepared, then made available — and only read when the gate
                is on. Nothing the assistant can read turns on by itself.
              </p>
              {[
                { t: 'Add', note: 'Title, format, size only — never the file’s contents.' },
                { t: 'Prepare', note: 'A new document waits at the gate, not yet readable.' },
                { t: 'Make available', note: 'You release it; with the gate on, Vidya may reference it.' },
              ].map((s) => (
                <div className="sched" key={s.t}>
                  <span className="t">{s.t}</span>
                  <div>
                    <p className="caption">{s.note}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                stored references, never stored contents — and never read until you say so
              </p>
            </div>
          </>
        ) : (
        <>
          <div className="ignite-card reveal reveal-2">
            <div className="row-between" style={{ marginBottom: 14 }}>
              <span className="overline">Generate-and-verify</span>
              <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
            </div>
            <div className="who">{totals.withheld} outputs held for a human</div>
            <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
              Output below the gate is never shown as final. It waits for a human read — the
              generate-and-verify rule, made visible.
            </p>
          </div>

          <div className="panel">
            <div className="sec-head" style={{ marginBottom: 8 }}>
              <h4 className="h4" style={{ margin: 0 }}>
                Break-glass and lineage
              </h4>
              <span className="overline">immutable</span>
            </div>
            <p className="caption" style={{ marginBottom: 12 }}>
              Privileged actions are break-glass; every model decision keeps its lineage. A read,
              never an edit.
            </p>
            {LINEAGE_LOG.map((r) => (
              <div className="flag" key={r.id}>
                <div className="flag-ic">
                  <Icon name={r.breakGlass ? 'warning' : 'check'} size="sm" />
                </div>
                <div>
                  <div className="body-sm row" style={{ gap: 'var(--space-2)', alignItems: 'center', fontWeight: 500 }}>
                    {r.breakGlass ? <Tag tone="warning">Break-glass</Tag> : null}
                    {r.actor}
                  </div>
                  <p className="caption">
                    {r.action} · {r.when}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <div className="panel" style={{ padding: '18px 20px' }}>
            <p className="handnote" style={{ fontSize: 22 }}>
              the gate is the point — nothing uncertain reaches a learner unread
            </p>
          </div>
        </>
        )
      }
    >
      {mode === 'knowledge' ? (
        kb.phase !== 'ready' ? (
          <ReadStates phase={kb.phase} onRetry={kb.refresh} />
        ) : (
          <KnowledgeBase config={kb.config} source={kb.source} onSet={kb.set} />
        )
      ) : (
      <>
      <Matrix columns={4} className="reveal reveal-1">
        <StatCell label="Model calls" value={totals.calls} delta="this window" tone="flat" />
        <StatCell label="Passed the gate" value={totals.passed} delta="provisional auto" tone="up" />
        <StatCell label="Withheld for review" value={totals.withheld} delta="held for a human" tone="down" />
        <StatCell label="Pass rate" value={totals.passRate} unit="%" delta="released as provisional" tone="up" />
      </Matrix>
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

      <section>
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>
            Agents and their tools
          </h3>
          <span className="overline">{runningAgents} running</span>
        </div>
        <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
          Which agents run, what they may reach, and on which model track. Turning one on or off is
          saved and survives a reload. A consequential agent can prepare but never act on its own.
        </p>
        <Matrix columns={2}>
          {AGENTS.map((agent) => (
            <AgentCell
              key={agent.id}
              agent={agent}
              enabled={agentEnabled(agent, adminConfig?.agents)}
              onToggle={(next) => setAgentEnabled(agent.id, next)}
            />
          ))}
        </Matrix>
      </section>

      <section>
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>
            Approval queue
          </h3>
          <Tag tone={proactive.recommendations.length > 0 ? 'warning' : 'success'}>
            {proactive.recommendations.length}
          </Tag>
        </div>
        <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
          What the agents have prepared, waiting on your decision. Approving runs the action through the
          permission ladder — nothing consequential fires until you approve.
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
          <div className="stack" style={{ gap: 'var(--space-3)' }}>
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

      <section>
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>
            Model usage by track
          </h3>
          <span className="overline">reported apart</span>
        </div>
        <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
          The open-standards track and the proprietary/edge track are reported and governed separately,
          never blended.
        </p>
        <Matrix columns={2}>
          {TRACK_USAGE.map((u) => (
            <TrackCell key={u.track} usage={u} />
          ))}
        </Matrix>
      </section>

      <EmergencyDisable onRecord={recordEmergencyDisable} />
      </>
      )}
    </SurfaceShell>
  );
}

/**
 * A single governed agent in the cell matrix — its purpose, the tools it may
 * reach, its model track, and a real enable/disable that persists. A
 * consequential agent shows the ladder note: it can prepare but never act alone.
 */
function AgentCell({
  agent,
  enabled,
  onToggle,
}: {
  agent: Agent;
  enabled: boolean;
  onToggle: (next: boolean) => void;
}) {
  return (
    <div className="cell" style={{ textAlign: 'left', padding: 'var(--space-5)' }}>
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
      </div>
    </div>
  );
}

function TrackCell({ usage }: { usage: TrackUsage }) {
  const passRate = usage.calls === 0 ? 0 : Math.round((usage.passed / usage.calls) * 100);
  return (
    <div className="cell" style={{ textAlign: 'left', padding: 'var(--space-5)' }}>
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
    </div>
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
    <section>
      <div className="sec-head">
        <h3 className="h3" style={{ margin: 0 }}>
          Emergency disable
        </h3>
        <span className="overline">human authority</span>
      </div>
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
                  <Button variant="danger" size="sm" disabled={!ready} onClick={disable}>
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
