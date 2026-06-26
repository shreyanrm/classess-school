'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { Icon, Matrix, ProgressBar, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { useAdminConfig } from '@/lib/adminConfig';
import {
  NETWORK_NODES,
  childrenOf,
  exceptions,
  networkRoot,
  type NetworkNode,
} from '@/lib/ring2Data';

/**
 * The multi-campus / network leadership view — recomposed to the sample-page
 * bar. Group -> region -> campus, managed by exception: a page-head with a mono
 * meta line + tab strip, a count-up rollup stat matrix, then cols (the
 * needs-attention cell matrix + the full expandable tree on the main; an
 * exception ignite-card, the needs-a-look flag panel, and a handnote on the
 * 320px aside). The regions a leader keeps open persist through the wall.
 * Mastery is a plain-language trend (share moving toward independent), never a
 * grade; rollups carry only opaque ids.
 */
export default function AdminNetworkPage() {
  const root = useMemo(() => networkRoot(NETWORK_NODES), []);
  const exceptionList = useMemo(() => exceptions(NETWORK_NODES), []);
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
        <div className="empty">
          <Icon name="grid" size="lg" className="glyph" />
          <h4 className="body">No campuses connected yet</h4>
          <p>Once your group structure is set up, regions and campuses will roll up here.</p>
        </div>
      </SurfaceShell>
    );
  }

  const regions = childrenOf(root.id);
  const campuses = NETWORK_NODES.filter((n) => n.level === 'campus');

  return (
    <SurfaceShell
      eyebrow="Network"
      title="Across the group"
      breadcrumb={[{ label: 'School', href: '/' }, { label: 'Network' }]}
      meta={[
        { value: regions.length, label: 'regions' },
        { value: campuses.length, label: 'campuses' },
        { value: root.openInterventions, label: 'open interventions' },
        { label: 'manage by exception' },
      ]}
      tabs={[
        { label: 'Rollup', active: true },
        { label: 'Intelligence', href: '/admin/intelligence' },
        { label: 'Briefing', href: '/admin' },
      ]}
      actions={
        <Link href="/admin/intelligence" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="chart" size="sm" />
          School intelligence
        </Link>
      }
      dockIntro="A calm rollup of the whole network. We surface the few places that need a look first, so you can manage by exception. Ask me to open any region or explain a trend."
      dockChips={['Which campuses need support', 'Why is Region South flagged', 'Open Region North']}
      aside={
        <>
          <div className="ignite-card reveal reveal-2">
            <div className="row-between" style={{ marginBottom: 14 }}>
              <span className="overline">Group rollup</span>
              <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
            </div>
            <div className="who">{root.masteryTrend}% trending toward independent</div>
            <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
              The share of learners across the group moving to work on their own — a direction, not a
              mark. The whole network rolls up to this.
            </p>
          </div>

          <div className="panel">
            <div className="sec-head" style={{ marginBottom: 8 }}>
              <h4 className="h4" style={{ margin: 0 }}>
                Needs a look
              </h4>
              <Tag tone={exceptionList.length > 0 ? 'warning' : 'success'}>{exceptionList.length}</Tag>
            </div>
            <p className="caption" style={{ marginBottom: 12 }}>
              Manage by exception — the few places to look first; the rest stay quiet.
            </p>
            {exceptionList.length === 0 ? (
              <p className="body-sm muted" style={{ margin: 0 }}>
                Every region and campus is inside the calm band.
              </p>
            ) : (
              exceptionList.map((node) => (
                <div className="flag" key={node.id}>
                  <div className="flag-ic">
                    <Icon name="warning" size="sm" />
                  </div>
                  <div>
                    <div className="body-sm" style={{ fontWeight: 500 }}>
                      {node.label}
                    </div>
                    <p className="caption">{node.exceptionNote}</p>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="panel" style={{ padding: '18px 20px' }}>
            <p className="handnote" style={{ fontSize: 22 }}>
              rollups carry opaque ids only — never a name leaves the campus
            </p>
          </div>
        </>
      }
    >
      <Matrix columns={4} className="reveal reveal-1">
        <StatCell label="Mastery trend, group" value={root.masteryTrend} unit="%" delta="toward independent" tone="up" />
        <StatCell label="Open interventions" value={root.openInterventions} delta="across the network" tone="flat" />
        <StatCell label="Need a look" value={exceptionList.length} delta="manage by exception" tone={exceptionList.length > 0 ? 'down' : 'flat'} />
        <StatCell label="Campuses" value={campuses.length} delta={`in ${regions.length} regions`} tone="flat" />
      </Matrix>

      {exceptionList.length > 0 ? (
        <section>
          <div className="sec-head">
            <h3 className="h3" style={{ margin: 0 }}>
              Needs your attention
            </h3>
            <span className="overline">look here first</span>
          </div>
          <Matrix columns={2}>
            {exceptionList.map((node) => (
              <div key={node.id} className="cell" style={{ textAlign: 'left', padding: 'var(--space-5)' }}>
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
                <ProgressBar
                  value={node.masteryTrend}
                  label={`Mastery trend for ${node.label}`}
                  style={{ marginTop: 'var(--space-3)' }}
                />
                <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
                  {node.exceptionNote}
                </p>
              </div>
            ))}
          </Matrix>
        </section>
      ) : null}

      <section>
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>
            The full rollup
          </h3>
          <span className="overline">group → region → campus</span>
        </div>
        <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
          {surface.source === 'gateway'
            ? 'The regions you keep open are read back from the event store, so the rollup returns the way you left it.'
            : 'The regions you keep open record to the event store when it is reachable.'}
        </p>
        <div className="net-tree">
          {regions.map((region) => {
            const open = isOpen(region.id);
            const regionCampuses = childrenOf(region.id);
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
                    {regionCampuses.map((campus) => (
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

      <SourceNote source={surface.source} />
    </SurfaceShell>
  );
}

function NodeSummary({ node }: { node: NetworkNode }) {
  return (
    <div className="net-summary">
      <div className="net-summary-head">
        <span className="body-sm">{node.label}</span>
        {node.needsAttention ? (
          <Tag tone="warning" dot>
            Needs a look
          </Tag>
        ) : (
          <Tag tone="neutral" dot>
            Steady
          </Tag>
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
