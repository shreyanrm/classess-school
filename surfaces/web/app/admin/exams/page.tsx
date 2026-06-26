'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button, Icon, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { SCAN_ROWS } from '@/lib/examsData';
import { useAdminConfig } from '@/lib/adminConfig';

/**
 * Exam operations (admin) — recomposed to the sample-page bar. Scheduling,
 * seating, secure-print packaging, and OMR/scan intake, each behind an Approval
 * control (prepare -> human approves -> execute). A page-head with a mono meta
 * line + tab strip, a count-up stage stat matrix, then cols: the stage selector
 * + the approval control on the main; the four-stage progress flag panel and a
 * handnote on the 320px aside. Scan intake is human-final and NEVER penalises a
 * student for scan quality. Each approval persists through the wall.
 */

type Stage = 'schedule' | 'seating' | 'print' | 'intake';

const STAGES: { id: Stage; label: string }[] = [
  { id: 'schedule', label: 'Schedule' },
  { id: 'seating', label: 'Seating' },
  { id: 'print', label: 'Secure print' },
  { id: 'intake', label: 'Scan intake' },
];

export default function ExamsPage() {
  const [stage, setStage] = useState<Stage>('schedule');
  const surface = useAdminConfig('exams');
  const approved: Record<Stage, boolean> = {
    schedule: surface.config.schedule === true,
    seating: surface.config.seating === true,
    print: surface.config.print === true,
    intake: surface.config.intake === true,
  };
  const approvedCount = Object.values(approved).filter(Boolean).length;

  function approve(s: Stage) {
    void surface.set(s, true);
  }
  function reopen(s: Stage) {
    void surface.set(s, false);
  }

  const stageMeta: Record<Stage, { title: string; prepared: string; consequence: string; cta: string }> = {
    schedule: {
      title: 'Exam timetable',
      prepared: 'A clash-free schedule across grades and halls is prepared, respecting the calendar and accommodations.',
      consequence: 'Publishing the schedule notifies staff and families. It waits for your approval.',
      cta: 'Approve and publish schedule',
    },
    seating: {
      title: 'Seating plan',
      prepared: 'A seating arrangement is prepared per hall, spacing students from the same section.',
      consequence: 'Approving locks the plan for printing on hall lists. Nothing prints until you approve.',
      cta: 'Approve seating plan',
    },
    print: {
      title: 'Secure-print package',
      prepared: 'Papers are packaged for secure printing — sealed counts per hall, with a chain-of-custody label.',
      consequence: 'Approving releases the package to the secure printer. This is the most sensitive step.',
      cta: 'Approve and release to print',
    },
    intake: {
      title: 'OMR and scan intake',
      prepared: 'Scanned sheets are read and matched. Low-quality scans are flagged for a human, never marked wrong.',
      consequence: 'Confirming intake sends clean reads to the gradebook; flagged sheets wait for a human read.',
      cta: 'Confirm clean reads',
    },
  };

  const meta = stageMeta[stage];
  const cleanScans = SCAN_ROWS.filter((r) => r.state === 'read').length;

  return (
    <SurfaceShell
      eyebrow="Examination"
      title="Exam operations"
      breadcrumb={[{ label: 'School', href: '/' }, { label: 'Exams' }]}
      meta={[
        { value: STAGES.length, label: 'gated stages' },
        { value: approvedCount, label: 'approved' },
        { value: STAGES.length - approvedCount, label: 'awaiting you' },
        { label: 'nothing fires on its own' },
      ]}
      tabs={[
        { label: 'Operations', active: true },
        { label: 'Calendar', href: '/admin/calendar' },
        { label: 'Curriculum', href: '/admin/curriculum' },
        { label: 'Governance', href: '/admin/governance' },
      ]}
      actions={
        <Link href="/admin/calendar" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="calendar" size="sm" />
          Timetable
        </Link>
      }
      dockIntro="I prepare each step — schedule, seating, secure print, scan intake — and hold it at the approval gate. Nothing publishes, prints, or grades on its own. A poor scan is flagged for a human, never penalised."
      dockChips={['Prepare the timetable', 'Why is this sheet flagged', 'Package for secure print']}
      aside={
        surface.phase !== 'ready' ? null : (
          <>
            <div className="ignite-card reveal reveal-2">
              <div className="row-between" style={{ marginBottom: 14 }}>
                <span className="overline">Human-final</span>
                <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
              </div>
              <div className="who">A faint scan is never marked wrong</div>
              <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                Low-quality scans are routed to a person to read. The student is never penalised for a
                poor scan — intake stays human-final.
              </p>
            </div>

            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>
                  The four gates
                </h4>
                <Tag tone={approvedCount === STAGES.length ? 'success' : 'info'}>
                  {approvedCount}/{STAGES.length}
                </Tag>
              </div>
              <p className="caption" style={{ marginBottom: 12 }}>
                Each step is prepared and held. Approving one never opens the next.
              </p>
              {STAGES.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className="flag flag-link"
                  style={{ width: '100%', textAlign: 'left', background: 'none', border: 0, borderBottom: '0.5px solid var(--border)' }}
                  onClick={() => setStage(s.id)}
                >
                  <div className="flag-ic">
                    <Icon name={approved[s.id] ? 'check' : 'clock'} size="sm" />
                  </div>
                  <div>
                    <div className="body-sm" style={{ fontWeight: 500 }}>
                      {s.label}
                    </div>
                    <p className="caption">{approved[s.id] ? 'Approved' : 'Prepared — awaiting approval'}</p>
                  </div>
                </button>
              ))}
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                secure print is the most sensitive gate — you release it, no one else
              </p>
            </div>
          </>
        )
      }
    >
      {surface.phase !== 'ready' ? (
        <ReadStates phase={surface.phase} onRetry={surface.refresh} />
      ) : (
        <>
          <Matrix columns={4} className="reveal reveal-1">
            <StatCell label="Gated stages" value={STAGES.length} delta="prepare → approve → execute" tone="flat" />
            <StatCell label="Approved" value={approvedCount} delta="by your hand" tone="up" />
            <StatCell label="Awaiting you" value={STAGES.length - approvedCount} delta="held at the gate" tone={STAGES.length - approvedCount > 0 ? 'down' : 'flat'} />
            <StatCell label="Clean scans" value={cleanScans} delta={`of ${SCAN_ROWS.length} read`} tone="up" />
          </Matrix>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Stage
              </h3>
              <span className="overline">prepare and approve, in order</span>
            </div>
            <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
              {surface.source === 'gateway'
                ? 'Each approval is read back from the event store — recorded the moment you approve, never auto-fired.'
                : 'Each approval is recorded on your explicit action; it persists to the event store when it is reachable.'}
            </p>
            <div className="segmented" role="group" aria-label="Exam stage">
              {STAGES.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={stage === s.id ? 'active' : ''}
                  aria-pressed={stage === s.id}
                  onClick={() => setStage(s.id)}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </section>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                The approval control
              </h3>
              <Tag tone={approved[stage] ? 'success' : 'info'} dot>
                {approved[stage] ? 'Approved' : 'Prepared — awaiting approval'}
              </Tag>
            </div>
            <SpotlightCard padLg>
              <h3 className="body-lg" style={{ margin: 0 }}>
                {meta.title}
              </h3>
              <p className="body-sm muted" style={{ marginTop: 'var(--space-3)', maxWidth: 600 }}>
                {meta.prepared}
              </p>

              {stage === 'seating' ? (
                <Matrix columns={2} style={{ marginTop: 'var(--space-3)' }}>
                  {['Hall 1', 'Hall 2'].map((h) => (
                    <div key={h} className="cell" style={{ textAlign: 'left' }}>
                      <div className="row-between">
                        <span className="body-sm">{h}</span>
                        <Tag tone="neutral">30 seats</Tag>
                      </div>
                      <p className="caption muted" style={{ marginTop: 4 }}>
                        Sections interleaved; aisle gaps preserved.
                      </p>
                    </div>
                  ))}
                </Matrix>
              ) : null}

              {stage === 'intake' ? (
                <div className="table-wrap" style={{ marginTop: 'var(--space-3)' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Sheet</th>
                        <th>Read</th>
                        <th>Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {SCAN_ROWS.map((row) => (
                        <tr key={row.id}>
                          <td>{row.label}</td>
                          <td>
                            <Tag tone={row.state === 'read' ? 'success' : 'warning'} dot>
                              {row.state === 'read' ? 'Read cleanly' : 'Needs a human read'}
                            </Tag>
                          </td>
                          <td className="muted" style={{ maxWidth: 320 }}>
                            {row.quality === 'low'
                              ? 'Scan quality is low. Sent to a person to read — never penalised for a faint scan.'
                              : 'High-confidence read, ready for the gradebook on your confirm.'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}

              <EvidenceDrawer
                evidence={[
                  'Every step is prepared deterministically and held at the approval gate; agents hold no credentials.',
                  'Scan intake is human-final: a low-quality scan is routed to a person, never auto-marked wrong.',
                ]}
                whySeeing={meta.consequence}
              />

              <div className="divider" />
              {approved[stage] ? (
                <div className="rec-actions">
                  <span className="body-sm">
                    {stage === 'intake'
                      ? 'Clean reads sent to the gradebook. Flagged sheets are waiting for a human read.'
                      : `${meta.title} approved. The downstream steps stay gated behind their own approvals.`}
                  </span>
                  <Button variant="ghost" size="sm" onClick={() => reopen(stage)}>
                    Reopen
                  </Button>
                </div>
              ) : (
                <div className="rec-actions">
                  <Button variant="accent" size="sm" onClick={() => approve(stage)}>
                    {meta.cta}
                  </Button>
                  <span className="caption muted">
                    Nothing happens until you approve. You hold the authority at every gate.
                  </span>
                </div>
              )}
            </SpotlightCard>
          </section>

          <SourceNote source={surface.source} />
        </>
      )}
    </SurfaceShell>
  );
}
