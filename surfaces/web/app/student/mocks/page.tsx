'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Button, Icon, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import {
  StatMatrix,
  Panel,
  FlagRow,
  HandnotePanel,
  SecHead,
} from '../../_components/StudentComposed';
import { MockSession } from '../../_components/MockSession';
import { useSurfaceState } from '@/lib/useSurfaceState';
import { useGatewaySource } from '@/lib/useGatewaySource';
import { MOCK_BLUEPRINTS, type MockBlueprint } from '@/lib/mocksData';
import { studentRevisionPlan, CURRENT_STUDENT } from '@/lib/loopData';

/**
 * Revision planner, mock tests and exam readiness — composed dense. A four-up
 * read up top, blueprint-aligned mocks as cards with coverage tags, and a
 * spaced-revision plan that surfaces a topic when memory is genuinely fading —
 * accurate, never guilt-based. Plain language only: a learner never sees a raw
 * score. Starting a mock is the student's choice; nothing begins on its own.
 */

type Tab = 'mocks' | 'plan';

// Coverage weights stay cool: light/core read as neutral/info, the one HEAVY
// section is the single warm emphasis (the page never leans warm overall).
const WEIGHT_TONE = { light: 'neutral', core: 'info', heavy: 'warning' } as const;

export default function MocksPage() {
  const [tab, setTab] = useState<Tab>('mocks');
  const [started, setStarted] = useState<string | null>(null);
  const { phase, refresh } = useSurfaceState();
  const { source } = useGatewaySource('learning', { subject: CURRENT_STUDENT.ref });
  const mocks: MockBlueprint[] = MOCK_BLUEPRINTS;
  const revision = useMemo(() => studentRevisionPlan(), []);

  const ready = mocks.filter((m) => m.state === 'ready').length;
  const taken = mocks.filter((m) => m.state === 'taken').length;
  const urgent = revision.filter((r) => r.urgent).length;

  return (
    <SurfaceShell
      breadcrumb={[{ label: 'Learning', href: '/student' }, { label: 'Mocks' }]}
      eyebrow="Exam readiness"
      title="Mocks and study plan"
      meta={[
        { value: mocks.length, label: 'sittable mocks' },
        { value: revision.length, label: 'to revise' },
        { label: 'sectioned paper · timer · plain-language read' },
      ]}
      tabs={[
        { label: 'Mock tests', active: tab === 'mocks', onClick: () => setTab('mocks') },
        { label: 'Revision plan', active: tab === 'plan', onClick: () => setTab('plan') },
      ]}
      dockIntro="Your mocks mirror the real paper, and your revision plan brings a topic back exactly when it is fading — never to nag, only to help it stick. You choose when to begin."
      dockChips={['What should I revise today', 'Start a maths mock', 'Am I ready for trigonometry']}
      aside={
        phase === 'ready' ? (
          <>
            <Panel title="Revise first" meta={<Tag tone={urgent ? 'warning' : 'info'}><span className="dot" />{revision.length}</Tag>}>
              {revision.length === 0 ? (
                <p className="caption">Nothing is fading — everything you earned is still fresh.</p>
              ) : (
                revision.slice(0, 3).map((r) => (
                  <FlagRow
                    key={r.topicId}
                    flag={{
                      icon: r.urgent ? 'clock' : 'target',
                      title: `${r.topic} · ${r.when}`,
                      caption: `${r.subject} — ${r.why}`,
                      href: `/student/topic/${r.topicId}`,
                    }}
                  />
                ))
              )}
            </Panel>

            <Panel title="How readiness works" meta={<span className="overline">honest</span>}>
              <p className="caption" style={{ marginBottom: 'var(--space-3)' }}>
                A topic comes back as memory starts to fade — built from your own practice against the
                real forgetting curve, never a fixed nagging timer.
              </p>
              <EvidenceDrawer
                evidence={[
                  'The schedule is built from your own practice history against the real forgetting curve — opaque ref only.',
                  'A topic surfaces when retention is genuinely fading, not on a fixed nagging timer.',
                ]}
                whySeeing="Your revision plan is shaped to keep what you have already earned. It adapts to time left and where the exam puts its weight."
              />
            </Panel>

            <HandnotePanel>a mock is practice — it feeds your readiness, never a record against you</HandnotePanel>
          </>
        ) : undefined
      }
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : (
        <>
          <StatMatrix
            stats={[
              { label: 'Ready to take', value: ready, delta: 'mirror the real paper', deltaDir: 'flat' },
              { label: 'Taken', value: taken, delta: taken ? 'feeds readiness' : 'none yet', deltaDir: taken ? 'up' : 'flat' },
              { label: 'To revise', value: revision.length, delta: revision.length ? 'fading topics' : 'all fresh', deltaDir: 'flat' },
              { label: 'Due today', value: urgent, delta: urgent ? 'worth keeping' : 'no rush', deltaDir: 'flat' },
            ]}
          />

          {tab === 'mocks' && started ? (
            <section className="reveal reveal-3">
              <div className="row-between" style={{ marginBottom: 'var(--space-4)' }}>
                <SecHead title="Paper in progress" meta={<span className="overline">take your time</span>} />
              </div>
              <MockSession blueprintId={started} onExit={() => setStarted(null)} />
            </section>
          ) : tab === 'mocks' ? (
            <section className="reveal reveal-3">
              <SecHead title="Blueprint-aligned mocks" meta={<span className="overline">where the weight sits</span>} />
              <p className="caption quiet" style={{ marginBottom: 'var(--space-4)' }}>
                Each mock mirrors the real format and difficulty. Coverage shows where the weight sits — in
                plain words, never a marks formula.
              </p>
              <div className="stack" style={{ gap: 'var(--space-4)' }}>
                {mocks.map((m) => (
                  <div className="next-step-hero" key={m.id} style={{ padding: 'var(--space-5)' }}>
                    <div className="row-between" style={{ alignItems: 'flex-start' }}>
                      <div>
                        <h3 className="display-sm" style={{ margin: 0, fontSize: 22 }}>
                          {m.subject} mock
                        </h3>
                        <p className="caption muted" style={{ marginTop: 4 }}>
                          {m.format}
                        </p>
                      </div>
                      <Tag tone={m.state === 'taken' ? 'success' : 'info'}>
                        {m.state === 'taken' ? 'Taken' : 'Ready'}
                      </Tag>
                    </div>

                    <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap', marginTop: 'var(--space-4)' }}>
                      {m.coverage.map((c) => (
                        <Tag key={c.unit} tone={WEIGHT_TONE[c.weight]}>
                          {c.unit} · {c.weight}
                        </Tag>
                      ))}
                    </div>

                    <div className="divider" />
                    <div className="rec-actions">
                      <Button variant="accent" size="sm" onClick={() => setStarted(m.id)}>
                        {m.state === 'taken' ? 'Retake this mock' : 'Begin the mock'}
                      </Button>
                      <span className="caption muted">
                        Full paper · timer · {m.subject === 'Mathematics' ? '40' : '35'} min. Nothing starts
                        until you choose to begin.
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : (
            <section className="reveal reveal-3">
              <SecHead title="Spaced revision" meta={<span className="overline">what to touch, and when</span>} />
              <p className="caption quiet" style={{ marginBottom: 'var(--space-4)' }}>
                A topic comes back exactly as memory starts to fade. This is here to help it stick, never to
                make you feel behind.
              </p>
              {revision.length === 0 ? (
                <div className="empty">
                  <Icon name="success" size="lg" className="glyph" />
                  <h4 className="body">Nothing is fading right now</h4>
                  <p>Everything you have earned is still fresh. A topic will appear here the moment it starts to fade.</p>
                </div>
              ) : (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Topic</th>
                        <th>Subject</th>
                        <th>When</th>
                        <th className="num">Revise</th>
                      </tr>
                    </thead>
                    <tbody>
                      {revision.map((r) => (
                        <tr key={r.topicId}>
                          <td>
                            <Link href={`/student/topic/${r.topicId}`} className="roster-name">
                              {r.topic}
                              <span className="roster-sub caption">{r.why}</span>
                            </Link>
                          </td>
                          <td className="muted">{r.subject}</td>
                          <td>
                            <Tag tone={r.urgent ? 'warning' : 'neutral'}>{r.when}</Tag>
                          </td>
                          <td className="num">
                            <Link
                              href="/student/practice"
                              className={`btn btn-${r.urgent ? 'primary' : 'ghost'} btn-sm`}
                            >
                              <Icon name="arrow-right" size="sm" /> Revise
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}
