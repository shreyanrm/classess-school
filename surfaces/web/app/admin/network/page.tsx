'use client';

import { useMemo } from 'react';
import { Icon, ProgressBar, SpotlightCard, Stat, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { useAdminConfig } from '@/lib/adminConfig';
import {
  NETWORK_NODES,
  childrenOf,
  exceptions,
  networkRoot,
  type NetworkNode,
} from '@/lib/ring2Data';

/**
 * The multi-campus / network leadership view — group -> region -> campus, with
 * mastery and intervention rollups. Leadership manages by exception: the few
 * nodes outside the calm band surface first, the rest stay quiet. Mastery is a
 * plain-language trend (share moving toward independent), never a grade.
 */
export default function AdminNetworkPage() {
  const root = useMemo(() => networkRoot(NETWORK_NODES), []);
  const exceptionList = useMemo(() => exceptions(NETWORK_NODES), []);
  // Which regions a leader keeps open is governed config: rehydrated from the
  // event store (a persisted open/closed wins over the all-open seed default), so
  // the rollup returns the way they left it. Toggling is authorized at the wall
  // and appended to the immutable store. The hook also carries the five states.
  const surface = useAdminConfig('network');
  const isOpen = (id: string): boolean => {
    const saved = surface.config[`region:${id}`];
    return typeof saved === 'boolean' ? saved : true; // seed default: all open
  };

  function toggleRegion(id: string) {
    void surface.set(`region:${id}`, !isOpen(id));
  }
  if (surface.phase !== 'ready') {
    return (
      <SurfaceShell eyebrow="Network" title="Network leadership">
        <ReadStates phase={surface.phase} onRetry={surface.refresh} />
      </SurfaceShell>
    );
  }

  if (!root) {
    return (
      <SurfaceShell eyebrow="Network" title="Network leadership">
        <SpotlightCard>
          <div className="empty">
            <Icon name="grid" size="lg" className="glyph" />
            <h4 className="body">No campuses connected yet</h4>
            <p>Once your group structure is set up, regions and campuses will roll up here.</p>
          </div>
        </SpotlightCard>
      </SurfaceShell>
    );
  }

  const regions = childrenOf(root.id);

  return (
    <SurfaceShell
      eyebrow="Network"
      title="Across the group"
      dockIntro="A calm rollup of the whole network. We surface the few places that need a look first, so you can manage by exception. Ask me to open any region or explain a trend."
      dockChips={['Which campuses need support', 'Why is Region South flagged', 'Open Region North']}
    >
      <section className="stack">
        <div className="cols-2">
          <Stat label="Mastery trend, group" value={root.masteryTrend} suffix="%" />
          <Stat label="Open interventions" value={root.openInterventions} />
          <Stat label="Need a look" value={exceptionList.length} />
          <Stat label="Campuses" value={NETWORK_NODES.filter((n) => n.level === 'campus').length} />
        </div>
        <p className="caption quiet">
          Mastery trend is the share of learners moving toward working on their own — a direction,
          not a mark. Rollups carry only opaque ids, never personal information.
        </p>
      </section>

      {exceptionList.length > 0 ? (
        <section className="stack">
          <p className="overline">Needs your attention</p>
          <p className="caption quiet">Manage by exception — these are the places to look first.</p>
          <div className="cols-2">
            {exceptionList.map((node) => (
              <SpotlightCard key={node.id}>
                <div className="row-between" style={{ alignItems: 'flex-start' }}>
                  <div>
                    <p className="overline" style={{ margin: 0 }}>
                      {levelLabel(node.level)}
                    </p>
                    <h3 className="body-lg" style={{ margin: 'var(--space-1) 0 0' }}>
                      {node.label}
                    </h3>
                  </div>
                  <Tag tone="warning" dot>
                    Needs a look
                  </Tag>
                </div>
                <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
                  {node.exceptionNote}
                </p>
              </SpotlightCard>
            ))}
          </div>
        </section>
      ) : (
        <section className="stack">
          <SpotlightCard>
            <div className="empty">
              <Icon name="success" size="lg" className="glyph" />
              <h4 className="body">Nothing needs your attention right now</h4>
              <p>Every region and campus is inside the calm band. The full rollup is below.</p>
            </div>
          </SpotlightCard>
        </section>
      )}

      <section className="stack">
        <p className="overline">The full rollup</p>
        <p className="caption quiet">
          {surface.source === 'gateway'
            ? 'The regions you keep open are read back from the event store, so the rollup returns the way you left it.'
            : 'The regions you keep open record to the event store when it is reachable.'}
        </p>
        <div className="net-tree">
          {regions.map((region) => {
            const open = isOpen(region.id);
            const campuses = childrenOf(region.id);
            return (
              <div key={region.id} className="net-region">
                <button
                  type="button"
                  className="net-row net-row-region"
                  aria-expanded={open}
                  onClick={() => toggleRegion(region.id)}
                >
                  <Icon name={open ? 'chevron-down' : 'chevron-right'} size="sm" />
                  <NodeSummary node={region} />
                </button>
                {open ? (
                  <div className="net-children">
                    {campuses.map((campus) => (
                      <div key={campus.id} className="net-row net-row-campus">
                        <span className="net-tick" aria-hidden="true" />
                        <NodeSummary node={campus} />
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>
    </SurfaceShell>
  );
}

function NodeSummary({ node }: { node: NetworkNode }) {
  return (
    <div className="net-summary">
      <div className="net-summary-head">
        <span className="body-sm">{node.label}</span>
        {node.needsAttention ? (
          <Tag tone="warning">Needs a look</Tag>
        ) : (
          <Tag tone="neutral">Steady</Tag>
        )}
      </div>
      <div className="net-summary-metrics">
        <ProgressBar
          value={node.masteryTrend}
          accent={!node.needsAttention}
          label={`Mastery trend for ${node.label}`}
        />
        <span className="caption muted" style={{ whiteSpace: 'nowrap' }}>
          {node.masteryTrend}% trending independent
        </span>
        <span className="caption muted" style={{ whiteSpace: 'nowrap' }}>
          {node.openInterventions} open
        </span>
      </div>
    </div>
  );
}

function levelLabel(level: NetworkNode['level']): string {
  if (level === 'group') return 'Group';
  if (level === 'region') return 'Region';
  return 'Campus';
}
