'use client';

import { useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { AI_CONTROLS, AUDIT_LOG, PERMISSION_MATRIX, type AiControl } from '@/lib/mock';

/**
 * Governance and audit — policy, the permissions matrix, the AI control centre,
 * and break-glass. Autonomy is bounded by the permission ladder: consequential
 * capabilities are locked off and can never auto-fire. Break-glass requires an
 * explicit confirmation and is recorded — human authority is preserved.
 */
export default function AdminGovernancePage() {
  return (
    <SurfaceShell
      eyebrow="Governance and audit"
      title="Policy, permissions, and the AI control centre"
      dockIntro="This is where you set the rules. Consequential actions can never auto-fire; break-glass is logged. Ask me to explain any permission."
      dockChips={['Explain the permission ladder', 'Who can publish reports', 'Show the recent audit trail']}
    >
      <section className="stack">
        <p className="overline">Permissions matrix</p>
        <p className="caption quiet">
          Who may do what. Consequential actions (send, submit, publish, delete, charge, grade)
          always require an explicit human decision and never auto-fire.
        </p>
        <SpotlightCard>
          <div className="table-scroll">
          <table className="eval-table">
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
                      <Tag tone="warning">Human approval</Tag>
                    ) : (
                      <Tag tone="neutral">Read or draft</Tag>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </SpotlightCard>
      </section>

      <section className="stack">
        <p className="overline">AI control centre</p>
        <div className="cols-2">
          {AI_CONTROLS.map((c) => (
            <AiControlCard key={c.id} control={c} />
          ))}
        </div>
      </section>

      <section className="stack">
        <p className="overline">Recent audit trail</p>
        <p className="caption quiet">Events are append-only and immutable. This is a read.</p>
        <div className="admin-list">
          {AUDIT_LOG.map((e) => (
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
      </section>

      <BreakGlass />
    </SurfaceShell>
  );
}

/** A single AI capability toggle. Locked capabilities are consequential and cannot be enabled. */
function AiControlCard({ control }: { control: AiControl }) {
  const [on, setOn] = useState(control.defaultOn);
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
          <Button
            variant={on ? 'primary' : 'secondary'}
            size="sm"
            aria-pressed={on}
            onClick={() => setOn((v) => !v)}
          >
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
 * and leaves authority with the human. This is the gate, not a shortcut.
 */
function BreakGlass() {
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState('');
  const [engaged, setEngaged] = useState(false);
  const ready = confirm.trim().toUpperCase() === 'BREAK GLASS';

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
                  <Button variant="danger" size="sm" disabled={!ready} onClick={() => setEngaged(true)}>
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
