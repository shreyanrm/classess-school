'use client';

import { useMemo, useState } from 'react';
import { Button, Icon, Matrix, Cell, SpotlightCard, Stat, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import {
  CONNECTORS,
  CONNECTOR_STATE_META,
  TRACK_LABEL,
  connectorHealth,
  type Connector,
  type ConnectorState,
} from '@/lib/ring2Data';

/**
 * The connector hub — a tight matrix of education-interop standards (LTI,
 * OneRoster, xAPI, QTI, SCORM, CASE) and platform bridges (Clever, Ed-Fi, MCP),
 * each with a health state and a last-sync read. Enabling a connector that
 * writes data outward is consequential: it is human-gated and waits for an
 * explicit Approve. The two tracks stay visibly separate.
 */
export default function AdminIntegrationsPage() {
  // Local view state so enable/approve feels live without a backend. The real
  // path is the gateway + connector registry (env vars in lib/runtime.ts).
  const [connectors, setConnectors] = useState<Connector[]>(CONNECTORS);
  const health = useMemo(() => connectorHealth(connectors), [connectors]);

  function setState(id: string, state: ConnectorState) {
    setConnectors((prev) => prev.map((c) => (c.id === id ? { ...c, state } : c)));
  }

  const standards = connectors.filter((c) => c.track === 'standards');
  const platform = connectors.filter((c) => c.track === 'platform');

  return (
    <SurfaceShell
      eyebrow="Integrations"
      title="The connector hub"
      dockIntro="Connect the standards and platforms your campuses already use. Turning on a connector that writes data out is yours to approve; it never switches itself on. Ask me what a connector moves."
      dockChips={['What does OneRoster sync', 'Why is SCORM failing', 'Explain Track 1 vs Track 2']}
    >
      <section className="stack">
        <div className="cols-2">
          <Stat label="Connected" value={health.connected} suffix={` of ${health.total}`} />
          <Stat label="Awaiting your approval" value={health.awaitingApproval} />
          <Stat label="Need a look" value={health.needsAttention} />
          <Stat label="Standards and platforms" value={health.total} />
        </div>
        <p className="caption quiet">
          Last sync and health update on each call through the gateway. Behavioural records carry
          only the opaque canonical id, never personal information.
        </p>
      </section>

      <ConnectorTrackSection
        title={TRACK_LABEL.standards}
        note="Open, board-agnostic interoperability standards. Reading these in is low-risk."
        connectors={standards}
        onState={setState}
      />

      <ConnectorTrackSection
        title={TRACK_LABEL.platform}
        note="Proprietary and edge bridges. Kept separate from the open standards in config, and governed apart."
        connectors={platform}
        onState={setState}
      />
    </SurfaceShell>
  );
}

function ConnectorTrackSection({
  title,
  note,
  connectors,
  onState,
}: {
  title: string;
  note: string;
  connectors: Connector[];
  onState: (id: string, state: ConnectorState) => void;
}) {
  return (
    <section className="stack">
      <p className="overline">{title}</p>
      <p className="caption quiet">{note}</p>
      {connectors.length === 0 ? (
        <SpotlightCard>
          <div className="empty">
            <Icon name="grid" size="lg" className="glyph" />
            <h4 className="body">No connectors on this track yet</h4>
            <p>When a connector is offered for this track it will appear here.</p>
          </div>
        </SpotlightCard>
      ) : (
        <Matrix columns={2} className="connector-matrix">
          {connectors.map((c) => (
            <ConnectorCell key={c.id} connector={c} onState={onState} />
          ))}
        </Matrix>
      )}
    </section>
  );
}

function ConnectorCell({
  connector,
  onState,
}: {
  connector: Connector;
  onState: (id: string, state: ConnectorState) => void;
}) {
  const meta = CONNECTOR_STATE_META[connector.state];
  return (
    <Cell className="connector-cell">
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
        <div>
          <h3 className="body-lg" style={{ margin: 0 }}>
            {connector.name}
          </h3>
          <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
            {connector.summary}
          </p>
        </div>
        <Tag tone={meta.tone} dot>
          {meta.label}
        </Tag>
      </div>

      <p className="caption muted" style={{ marginTop: 'var(--space-3)' }}>
        {connector.lastSync ?? 'Never synced'}
      </p>

      <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
        <ConnectorControl connector={connector} onState={onState} />
      </div>
    </Cell>
  );
}

/**
 * The enable / Approve control. A connector that does not write outward can be
 * toggled directly. A consequential connector (it writes data out) is gated:
 * it sits in "Awaiting approval" and only an explicit human Approve turns it on.
 * Nothing auto-fires.
 */
function ConnectorControl({
  connector,
  onState,
}: {
  connector: Connector;
  onState: (id: string, state: ConnectorState) => void;
}) {
  if (connector.state === 'enabled') {
    return (
      <>
        <span className="state-pill correct">
          <span className="dot" />
          Connected
        </span>
        <Button variant="ghost" size="sm" onClick={() => onState(connector.id, 'available')}>
          Disconnect
        </Button>
      </>
    );
  }

  if (connector.state === 'error') {
    return (
      <Button variant="secondary" size="sm" onClick={() => onState(connector.id, 'enabled')}>
        Retry sync
      </Button>
    );
  }

  if (connector.state === 'attention') {
    return (
      <>
        <span className="caption muted row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="warning" size="sm" />
          Records are held — clearing them resumes the sync
        </span>
        <Button variant="secondary" size="sm" onClick={() => onState(connector.id, 'enabled')}>
          Clear held records and resume
        </Button>
      </>
    );
  }

  // available (non-consequential) or pending (consequential, human-gated).
  if (connector.consequential || connector.state === 'pending') {
    return (
      <>
        <span className="caption muted row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="warning" size="sm" />
          Writes data out — your approval required
        </span>
        <Button variant="primary" size="sm" onClick={() => onState(connector.id, 'enabled')}>
          Approve and connect
        </Button>
      </>
    );
  }

  return (
    <Button variant="secondary" size="sm" onClick={() => onState(connector.id, 'enabled')}>
      Enable
    </Button>
  );
}
