'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button, Icon, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { AI_CONTROLS, AUDIT_LOG, PERMISSION_MATRIX, type AiControl } from '@/lib/mock';
import {
  POLICIES,
  ROLE_CATALOGUE,
  policyInForce,
  aiControlOn,
  type Policy,
  type RoleProfile,
} from '@/lib/adminData';
import { useStore } from '@/lib/useStore';
import { setPolicyVersion, setAiControlOn } from '@/lib/store';
import { useEmit } from '@/lib/useEmit';
import { useGovernance, type GovernanceAuditEntry } from '@/lib/governance';
import { EVENT_PURPOSE } from '@/lib/events';

/**
 * Governance and audit — policy, the permissions matrix, the AI control centre,
 * and break-glass. Autonomy is bounded by the permission ladder: consequential
 * capabilities are locked off and can never auto-fire. Break-glass requires an
 * explicit confirmation and is recorded — human authority is preserved.
 *
 * The whole surface is wired into the circuit: it rehydrates the governed config
 * + the immutable audit trail on mount from the real source (the event store via
 * /api/governance), every consequential governance action is authorized at the
 * wall and appended to that immutable trail, and the seed mock is a degrade-only
 * fallback. The five designed read states ship from ReadStates.
 */
export default function AdminGovernancePage() {
  const gov = useGovernance();

  const consequentialCaps = PERMISSION_MATRIX.filter((r) => r.consequential).length;
  const lockedControls = AI_CONTROLS.filter((c) => c.locked).length;
  // The recent audit trail for the aside — live when the round-trip answers,
  // else the seed mock as a clearly last-known fallback (never blank).
  const auditRows =
    gov.source === 'gateway' && gov.audit.length > 0
      ? gov.audit.map((e) => ({ id: e.id, action: e.action, actor: 'You', when: e.when }))
      : AUDIT_LOG;

  return (
    <SurfaceShell
      eyebrow="Governance and audit"
      title="Policy, permissions, and the AI control centre"
      breadcrumb={[{ label: 'School', href: '/' }, { label: 'Governance' }]}
      meta={[
        { value: PERMISSION_MATRIX.length, label: 'capabilities' },
        { value: ROLE_CATALOGUE.length, label: 'roles' },
        { value: POLICIES.length, label: 'policies versioned' },
        { value: consequentialCaps, label: 'human-gated' },
        { label: 'nothing auto-fires' },
      ]}
      tabs={[
        { label: 'Governance', active: true },
        { label: 'Control centre', href: '/admin/control-centre' },
        { label: 'Integrations', href: '/admin/integrations' },
        { label: 'Briefing', href: '/admin' },
      ]}
      actions={
        <Link href="/admin/control-centre" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="chart" size="sm" />
          AI control centre
        </Link>
      }
      dockIntro="This is where you set the rules. Consequential actions can never auto-fire; break-glass is logged. Ask me to explain any permission."
      dockChips={['Explain the permission ladder', 'Who can publish reports', 'Show the recent audit trail']}
      aside={
        gov.phase !== 'ready' ? null : (
          <>
            <div className="ignite-card reveal reveal-2">
              <div className="row-between" style={{ marginBottom: 14 }}>
                <span className="overline">Human authority</span>
                <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
              </div>
              <div className="who">{consequentialCaps} consequential actions stay human-gated</div>
              <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                Send, submit, publish, grade, charge — every one needs your explicit decision. The
                platform prepares; you act.
              </p>
            </div>

            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>
                  Recent audit trail
                </h4>
                <span className="overline">append-only</span>
              </div>
              <p className="caption" style={{ marginBottom: 12 }}>
                {gov.source === 'gateway'
                  ? 'Read back from the event store — immutable, never an edit.'
                  : 'Last-known trail; refreshes from the event store when reachable.'}
              </p>
              {auditRows.slice(0, 4).map((e) => (
                <div className="flag" key={e.id}>
                  <div className="flag-ic">
                    <Icon name="check" size="sm" />
                  </div>
                  <div>
                    <div className="body-sm" style={{ fontWeight: 500 }}>
                      {e.actor}
                    </div>
                    <p className="caption">
                      {e.action} · {e.when}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                {lockedControls} capabilities are locked off — they can never be enabled
              </p>
            </div>
          </>
        )
      }
    >
      {gov.phase !== 'ready' ? (
        <ReadStates phase={gov.phase} onRetry={gov.refresh} />
      ) : (
        <>
          <Matrix columns={4} className="reveal reveal-1">
            <StatCell label="Capabilities governed" value={PERMISSION_MATRIX.length} delta="across the tree" tone="flat" />
            <StatCell label="Human-gated" value={consequentialCaps} delta="never auto-fire" tone="up" />
            <StatCell label="Policies versioned" value={POLICIES.length} delta="with effective dates" tone="flat" />
            <StatCell label="AI controls locked off" value={lockedControls} delta="consequential" tone="down" />
          </Matrix>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Permissions matrix
              </h3>
              <span className="overline">who may do what</span>
            </div>
            <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
              Consequential actions (send, submit, publish, delete, charge, grade) always require an
              explicit human decision and never auto-fire.
            </p>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Capability</th>
                    <th>Allowed roles</th>
                    <th>Authority</th>
                  </tr>
                </thead>
                <tbody>
                  {PERMISSION_MATRIX.map((row) => (
                    <tr key={row.capability}>
                      <td>{row.capability}</td>
                      <td className="muted">{row.roles}</td>
                      <td>
                        {row.consequential ? (
                          <Tag tone="warning" dot>
                            Human approval
                          </Tag>
                        ) : (
                          <Tag tone="neutral" dot>
                            Read or draft
                          </Tag>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Role catalogue
              </h3>
              <span className="overline">{ROLE_CATALOGUE.length} roles · per-role permissions</span>
            </div>
            <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
              The same permissions, read from each role&rsquo;s side: its reach in the tree and the exact
              capabilities it holds. A gated capability is prepared, never auto-fired — a human in the
              role closes it. Generic counts only; no one is named.
            </p>
            <Matrix columns={2}>
              {ROLE_CATALOGUE.map((role, i) => (
                <RoleCard key={role.id} role={role} index={i} />
              ))}
            </Matrix>
          </section>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Policies
              </h3>
              <span className="overline">versioned, with effective dates</span>
            </div>
            <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
              Policies flow down the tree. Setting a different version in force is a consequential
              governance action — it is recorded to the immutable audit trail.
            </p>
            <div className="stack" style={{ gap: 'var(--space-3)' }}>
              {POLICIES.map((policy) => (
                <PolicyCard
                  key={policy.id}
                  policy={policy}
                  serverVersion={gov.config.policyVersions[policy.id]}
                  onSet={gov.setPolicy}
                />
              ))}
            </div>
          </section>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                AI control centre
              </h3>
              <span className="overline">autonomy is bounded</span>
            </div>
            <Matrix columns={2}>
              {AI_CONTROLS.map((c) => (
                <AiControlCard
                  key={c.id}
                  control={c}
                  serverOn={gov.config.aiControls[c.id]}
                  onSet={gov.setAiControl}
                />
              ))}
            </Matrix>
          </section>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Recent audit trail
              </h3>
              <span className="overline">immutable</span>
            </div>
            <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
              {gov.source === 'gateway'
                ? 'Events are append-only and immutable, read back from the event store. This is a read.'
                : 'Events are append-only and immutable. This is the last-known trail; it refreshes from the event store when it is reachable.'}
            </p>
            <AuditTrail entries={gov.audit} source={gov.source} />
          </section>

          <BreakGlass onRecord={gov.recordBreakGlass} />

          <SourceNote source={gov.source} />
        </>
      )}
    </SurfaceShell>
  );
}

/**
 * The immutable audit trail. Reads from the real source (the event store) when
 * the round-trip succeeds; falls back to the seed mock ONLY on a degraded
 * deploy (no db / unreachable), clearly the last-known record, never an edit.
 */
function AuditTrail({ entries, source }: { entries: GovernanceAuditEntry[]; source: 'gateway' | 'fallback' }) {
  // Degrade-only: the seed mock stands in when the live trail is unavailable or
  // empty so the surface is never blank. The live trail (source === 'gateway')
  // is authoritative the moment it answers.
  const rows =
    source === 'gateway' && entries.length > 0
      ? entries.map((e) => ({ id: e.id, action: e.action, actor: 'You', when: e.when }))
      : AUDIT_LOG;

  return (
    <div className="admin-list">
      {rows.map((e) => (
        <div key={e.id} className="admin-list-row">
          <div>
            <div className="body-sm">{e.action}</div>
            <div className="caption muted">{e.actor}</div>
          </div>
          <span className="caption muted" style={{ whiteSpace: 'nowrap' }}>
            {e.when}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * One role in the catalogue — its reach in the tree (a mono scope token + a
 * plain-language line), a generic holder count, and the exact capability set it
 * holds, each tagged gated (consequential, prepared-never-fired) or open (read
 * or draft). The platform role reads distinctly: it only ever prepares. Composed
 * to the surface depth language — hairline panel, tonal capability rows, no
 * shadow; the accent stays the single admin violet.
 */
function RoleCard({ role, index }: { role: RoleProfile; index: number }) {
  const gatedCount = role.capabilities.filter((c) => c.gated).length;
  return (
    <SpotlightCard className={`reveal reveal-${(index % 4) + 1}`}>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
        <div>
          <p className="overline" style={{ margin: '0 0 6px' }}>
            {role.scopeToken}
          </p>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {role.name}
          </h3>
        </div>
        {role.platform ? (
          <Tag tone="info" dot>
            Prepares only
          </Tag>
        ) : (
          <Tag tone="neutral" dot>
            {role.holders} {role.holders === 1 ? 'holder' : 'holders'}
          </Tag>
        )}
      </div>

      <p className="body-sm muted" style={{ margin: 'var(--space-3) 0 0' }}>
        {role.scope}
      </p>

      <div
        className="admin-list"
        style={{ marginTop: 'var(--space-3)' }}
        aria-label={`${role.name} capabilities`}
      >
        {role.capabilities.map((cap) => (
          <div
            key={cap.label}
            className="admin-list-row"
            style={{ alignItems: 'center', gap: 'var(--space-3)' }}
          >
            <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
              <Icon
                name={cap.gated ? 'warning' : 'check'}
                size="sm"
                style={{ color: cap.gated ? 'var(--warning)' : 'var(--text-tertiary)', flex: 'none' }}
              />
              <span className="body-sm">{cap.label}</span>
            </div>
            {cap.gated ? (
              <Tag tone="warning">Human-gated</Tag>
            ) : (
              <Tag tone="neutral">Read or draft</Tag>
            )}
          </div>
        ))}
      </div>

      <p className="caption quiet" style={{ margin: 'var(--space-3) 0 0' }}>
        {role.platform
          ? 'No consequential act fires without a human in the right role.'
          : `${gatedCount} of ${role.capabilities.length} are human-gated — prepared, then closed by you.`}
      </p>
    </SpotlightCard>
  );
}

/**
 * A versioned policy — the version in force (persisted), the full version ledger
 * with effective dates, and a consequential "set in force" control. Choosing a
 * version emits an attributed, consent-stamped audit event, persists the choice
 * locally, AND records it to the immutable audit trail through the wall; nothing
 * changes silently.
 */
function PolicyCard({
  policy,
  serverVersion,
  onSet,
}: {
  policy: Policy;
  serverVersion?: string;
  onSet: (policyId: string, policyName: string, version: string) => Promise<{ persisted: boolean }>;
}) {
  const { adminConfig } = useStore();
  const { emit } = useEmit();
  // The server-rehydrated version (the round-trip) wins over the local store so
  // the choice survives reload from the DB, not just localStorage.
  const localInForce = policyInForce(policy, adminConfig?.policyVersions);
  const inForce = serverVersion
    ? policy.versions.find((v) => v.version === serverVersion) ?? localInForce
    : localInForce;
  const [expanded, setExpanded] = useState(false);
  const [pending, setPending] = useState<string | null>(null);

  async function setInForce(version: string) {
    setPolicyVersion(policy.id, version);
    setPending(null);
    // Record to the immutable audit trail through the wall AND emit the event.
    await onSet(policy.id, policy.name, version);
    await emit({
      type: 'policy.version.set',
      purpose: EVENT_PURPOSE.teaching,
      payload: { policyId: policy.id, version },
    });
  }

  return (
    <SpotlightCard>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <div>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {policy.name}
          </h3>
          <p className="caption muted" style={{ marginTop: 4 }}>
            {policy.domain}
          </p>
        </div>
        <Tag tone="info" dot>
          {inForce.version} in force
        </Tag>
      </div>

      <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
        <span className="quiet">In force since {inForce.effective}. </span>
        {inForce.summary}
      </p>

      <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
        >
          <Icon name={expanded ? 'chevron-down' : 'chevron-right'} size="sm" />
          {expanded ? 'Hide version history' : 'Version history'}
        </Button>
      </div>

      {expanded ? (
        <div className="admin-list" style={{ marginTop: 'var(--space-3)' }}>
          {policy.versions.map((v) => {
            const current = v.version === inForce.version;
            const confirming = pending === v.version;
            return (
              <div key={v.version} className="admin-list-row" style={{ alignItems: 'flex-start' }}>
                <div>
                  <div className="body-sm row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                    {v.version}
                    {current ? <Tag tone="success">In force</Tag> : null}
                  </div>
                  <div className="caption muted">
                    Effective {v.effective} · set by {v.setBy}
                  </div>
                  <div className="caption muted" style={{ marginTop: 4, maxWidth: 520 }}>
                    {v.summary}
                  </div>
                  {confirming ? (
                    <div className="rec-actions" style={{ marginTop: 'var(--space-2)' }}>
                      <Button variant="accent" size="sm" onClick={() => setInForce(v.version)}>
                        Set {v.version} in force and record
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setPending(null)}>
                        Cancel
                      </Button>
                      <span className="caption muted">
                        This changes the policy in force across the tree and is recorded to audit.
                      </span>
                    </div>
                  ) : null}
                </div>
                {!current && !confirming ? (
                  <Button variant="secondary" size="sm" onClick={() => setPending(v.version)}>
                    Set in force
                  </Button>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      <EvidenceDrawer
        evidence={[
          'Each version is an immutable record with an effective date and the role that set it; older versions are never edited.',
          'Setting a version in force flows the policy down the tree and emits an attributed audit event.',
        ]}
        whySeeing="Versioning with effective dates keeps governance accountable: you can see exactly which rules were in force at any point, and who changed them."
      />
    </SpotlightCard>
  );
}

/**
 * A single AI capability toggle. Locked capabilities are consequential and
 * cannot be enabled. A toggle PERSISTS (survives reload) and is recorded to the
 * immutable audit trail through the wall — it is real governed configuration,
 * not session state.
 */
function AiControlCard({
  control,
  serverOn,
  onSet,
}: {
  control: AiControl;
  serverOn?: boolean;
  onSet: (controlId: string, controlLabel: string, on: boolean) => Promise<{ persisted: boolean }>;
}) {
  const { adminConfig } = useStore();
  // Server rehydrate (round-trip) wins; then the local store; then the default.
  const on =
    typeof serverOn === 'boolean' ? serverOn : aiControlOn(control, adminConfig?.aiControls);

  async function toggle() {
    const next = !on;
    setAiControlOn(control.id, next);
    await onSet(control.id, control.label, next);
  }

  return (
    <SpotlightCard>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <div>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {control.label}
          </h3>
          <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
            {control.description}
          </p>
        </div>
        {control.locked ? (
          <Tag tone="neutral">Locked off</Tag>
        ) : (
          <Button variant={on ? 'primary' : 'secondary'} size="sm" aria-pressed={on} onClick={toggle}>
            {on ? 'On' : 'Off'}
          </Button>
        )}
      </div>
    </SpotlightCard>
  );
}

/**
 * Break-glass — emergency elevated access. It is never one click: it requires an
 * explicit, typed confirmation, states what it grants and that it is recorded,
 * and leaves authority with the human. This is the gate, not a shortcut. On
 * engagement it EMITS an attributed event AND records to the governance/audit
 * endpoint so the claim "recorded to the immutable audit trail" is TRUE.
 */
function BreakGlass({ onRecord }: { onRecord: () => Promise<{ persisted: boolean }> }) {
  const { emit } = useEmit();
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState('');
  const [engaged, setEngaged] = useState(false);
  const ready = confirm.trim().toUpperCase() === 'BREAK GLASS';

  async function engage() {
    setEngaged(true);
    // Record to the immutable audit trail through the wall AND emit the event.
    await onRecord();
    await emit({
      type: 'governance.break_glass.engaged',
      purpose: EVENT_PURPOSE.teaching,
      payload: { recorded: true },
    });
  }

  return (
    <section className="stack">
      <p className="overline">Break-glass</p>
      <SpotlightCard padLg>
        <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'flex-start' }}>
          <Icon name="warning" size="lg" />
          <div style={{ flex: 1 }}>
            <h3 className="body-lg" style={{ margin: 0 }}>
              Emergency elevated access
            </h3>
            <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
              Break-glass grants temporary elevated access for a genuine emergency. It is fully
              recorded to the immutable audit trail, time-boxed, and reviewed afterward. It is yours
              to engage — the system never engages it for you.
            </p>

            {engaged ? (
              <div className="row-between" style={{ marginTop: 'var(--space-4)' }}>
                <span className="body-sm">
                  Break-glass engaged and recorded. Access is time-boxed and will be reviewed.
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setEngaged(false);
                    setOpen(false);
                    setConfirm('');
                  }}
                >
                  Stand down
                </Button>
              </div>
            ) : !open ? (
              <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
                <Button variant="danger" size="sm" onClick={() => setOpen(true)}>
                  Begin break-glass
                </Button>
              </div>
            ) : (
              <div style={{ marginTop: 'var(--space-4)' }}>
                <label className="caption muted" htmlFor="bg-confirm">
                  Type BREAK GLASS to confirm you are engaging emergency access.
                </label>
                <input
                  id="bg-confirm"
                  className="input"
                  style={{ marginTop: 'var(--space-2)', width: '100%' }}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="BREAK GLASS"
                  autoComplete="off"
                />
                <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
                  <Button variant="danger" size="sm" disabled={!ready} onClick={engage}>
                    Engage and record
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
