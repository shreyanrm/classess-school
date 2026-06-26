'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button, CrystallizeNode, Icon, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ProofArtifact } from '../../_components/ProofArtifact';
import { CredentialItem } from '../../_components/CredentialItem';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { SourceNote } from '../../_components/SourceNote';
import { openVidya } from '../../_components/VidyaOrb';
import {
  StatMatrix,
  IgniteCard,
  Panel,
  FlagRow,
  HandnotePanel,
  SecHead,
} from '../../_components/StudentComposed';
import { useStore } from '@/lib/useStore';
import { useGatewaySource } from '@/lib/useGatewaySource';
import { CURRENT_STUDENT } from '@/lib/loopData';
import {
  loadCredentials,
  loadTimeline,
  type CredentialView,
  type MasteryMomentView,
} from '@/lib/portfolioData';

type LoadState = 'loading' | 'ready' | 'error';

/** A real, portable export of the record — plain language only, never a score. */
function downloadRecord(timeline: MasteryMomentView[], credentials: CredentialView[]) {
  const record = {
    kind: 'classess.portfolio.record',
    generated: new Date().toISOString(),
    mastered: timeline.map((m) => ({
      topic: m.topicName,
      independent: m.independent,
      summary: m.plainLanguage,
    })),
    credentials: credentials.map((c) => ({ title: c.title, state: c.stateLabel })),
  };
  const blob = new Blob([JSON.stringify(record, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'my-classess-record.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * Learner portfolio and credentials — composed dense. A four-up read, a portable
 * export the learner controls, a timeline of mastered topics (each with evidence
 * and the Crystallize mark on an unaided demonstration), a shareable proof, and
 * verifiable credentials. The aside carries the proudest moment + a human note.
 * Plain language only — never a raw composite, score, or formula.
 */
export function StudentPortfolio() {
  const { state } = useStore();
  const { source } = useGatewaySource('learning', { subject: CURRENT_STUDENT.ref });
  const [load, setLoad] = useState<LoadState>('loading');
  const [timeline, setTimeline] = useState<MasteryMomentView[]>([]);
  const [credentials, setCredentials] = useState<CredentialView[]>([]);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    try {
      setTimeline(loadTimeline(state));
      setCredentials(loadCredentials(state));
      setLoad('ready');
    } catch {
      setLoad('error');
    }
  }, [state]);

  const independentCount = useMemo(() => timeline.filter((m) => m.independent).length, [timeline]);
  const verifiableCount = useMemo(() => credentials.filter((c) => c.verifiable).length, [credentials]);
  const proudest = useMemo(() => timeline.find((m) => m.independent), [timeline]);

  return (
    <SurfaceShell
      breadcrumb={[{ label: 'Learning', href: '/student' }, { label: 'Portfolio' }]}
      eyebrow="Your record"
      title="Portfolio and credentials"
      meta={[
        { value: timeline.length, label: 'mastered' },
        { value: independentCount, label: 'on your own' },
        { label: 'yours to share' },
      ]}
      dockIntro="This is the record of what you can do, in plain language, with the evidence behind it. I can help you choose what to share — sharing is always your decision."
      dockChips={['What can I share', 'Explain this credential', 'Show my proudest moment']}
      aside={
        load === 'ready' ? (
          <>
            {proudest ? (
              <IgniteCard
                when="Proudest moment"
                who={proudest.topicName}
                detail="A real, unaided demonstration — verified and shareable. This is the line that matters."
              />
            ) : (
              <Panel title="Your spark" meta={<span className="overline">soon</span>}>
                <p className="caption">
                  The moment you do a topic on your own, it lights here — a real, unaided demonstration.
                </p>
              </Panel>
            )}

            <Panel title="What you can share" meta={<Tag tone="info"><span className="dot" />{verifiableCount}</Tag>}>
              {verifiableCount === 0 ? (
                <p className="caption">When a credential is verified, it becomes shareable here.</p>
              ) : (
                credentials
                  .filter((c) => c.verifiable)
                  .map((c) => (
                    <FlagRow
                      key={c.id}
                      flag={{ icon: 'check', title: c.title, caption: 'Signed and verifiable — share with anyone.' }}
                    />
                  ))
              )}
            </Panel>

            <HandnotePanel>nothing leaves until you choose — the record is yours</HandnotePanel>
          </>
        ) : undefined
      }
    >
      {load === 'loading' ? (
        <section className="stack" aria-busy="true" aria-label="Loading your record">
          <div className="skeleton" style={{ height: 96 }} />
          <div className="skeleton" style={{ height: 160 }} />
          <div className="skeleton" style={{ height: 160 }} />
        </section>
      ) : load === 'error' ? (
        <div className="empty">
          <Icon name="search" size="lg" className="glyph" />
          <h4 className="body">Your record could not be read</h4>
          <p>Something went wrong loading your portfolio. Try again in a moment.</p>
        </div>
      ) : (
        <>
          <StatMatrix
            stats={[
              { label: 'Mastered', value: timeline.length, delta: 'topics with evidence', deltaDir: 'up' },
              { label: 'On your own', value: independentCount, delta: independentCount ? 'the green spark' : 'soon', deltaDir: independentCount ? 'up' : 'flat' },
              { label: 'Credentials', value: credentials.length, delta: 'earned', deltaDir: 'flat' },
              { label: 'Verifiable', value: verifiableCount, delta: verifiableCount ? 'shareable' : 'none yet', deltaDir: 'flat' },
            ]}
          />

          {/* Export / share the whole record. A deliberate learner action; never auto. */}
          <section className="next-step-hero reveal reveal-3">
            <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
              <div>
                <p className="overline" style={{ margin: 0 }}>
                  Your record
                </p>
                <h3 className="display-sm" style={{ margin: '6px 0 0', fontSize: 24 }}>
                  A portable record you control
                </h3>
              </div>
              <Tag tone="info">Plain language</Tag>
            </div>
            <p className="body-sm muted" style={{ marginTop: 'var(--space-3)', maxWidth: 560 }}>
              Export your record with a school, a programme, or anyone you choose. It carries what you can
              do and the evidence behind it — never a raw score.
            </p>
            <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  downloadRecord(timeline, credentials);
                  setExporting(true);
                }}
              >
                Download my record
                <Icon name="send" size="sm" />
              </Button>
              {exporting ? (
                <span className="row body-sm" style={{ gap: 'var(--space-2)', color: 'var(--text-secondary)' }}>
                  <Icon name="check" size="sm" />
                  Downloaded. The file is yours to share wherever you choose.
                </span>
              ) : null}
            </div>
            <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
              Nothing leaves this surface until you choose to share it — the download stays on your device.
            </p>
          </section>

          {/* Timeline of mastered topics. */}
          <section>
            <SecHead title="What you have mastered" meta={<span className="overline">with the evidence</span>} />
            {timeline.length === 0 ? (
              <div className="empty">
                <Icon name="spark" size="lg" className="glyph" />
                <h4 className="body">Your timeline is just beginning</h4>
                <p>As you master topics, each moment will appear here with the evidence behind it.</p>
                <Button variant="secondary" size="sm" onClick={() => openVidya('Help me start my first topic')}>
                  <Icon name="spark" size="sm" /> Start your first topic
                </Button>
              </div>
            ) : (
              <div className="parent-timeline">
                {timeline.map((m) => (
                  <div className="parent-timeline-row" key={m.id}>
                    <div className="parent-timeline-marker">
                      {m.independent ? (
                        <CrystallizeNode variant="b" inline resolved label="On your own" />
                      ) : (
                        <span className="dot" aria-hidden="true" />
                      )}
                    </div>
                    <div>
                      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                        <span className="body">{m.topicName}</span>
                        {m.independent ? <Tag tone="success">On your own</Tag> : <Tag tone="info">Reliable</Tag>}
                      </div>
                      <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
                        {m.plainLanguage}
                      </p>
                      <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                        {m.subjectName} · {m.when}
                      </p>
                      <div style={{ marginTop: 'var(--space-2)' }}>
                        <EvidenceDrawer
                          evidence={m.evidence}
                          whySeeing="Every moment in your record links to the evidence behind it — nothing is claimed without it."
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Proudest moment — a shareable proof artifact. */}
          {proudest ? (
            <section>
              <SecHead title="A proud moment to share" meta={<span className="overline">shareable proof</span>} />
              <ProofArtifact proof={proudest.proof} voice="self" />
            </section>
          ) : null}

          {/* Credentials. */}
          <section>
            <SecHead title="Achievements and credentials" meta={<span className="overline">verifiable</span>} />
            {credentials.length === 0 ? (
              <div className="empty">
                <Icon name="check" size="lg" className="glyph" />
                <h4 className="body">No credentials yet</h4>
                <p>When you are ready, credentials you have earned will appear here to issue and share.</p>
              </div>
            ) : (
              <div className="stack">
                {credentials.map((c) => (
                  <CredentialItem key={c.id} credential={c} />
                ))}
              </div>
            )}
          </section>

          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}
