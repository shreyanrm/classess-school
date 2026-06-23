'use client';

import { useEffect, useState } from 'react';
import { Button, Icon, IgniteDot, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ProofArtifact } from '../../_components/ProofArtifact';
import { CredentialItem } from '../../_components/CredentialItem';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { useStore } from '@/lib/useStore';
import {
  loadCredentials,
  loadTimeline,
  type CredentialView,
  type MasteryMomentView,
} from '@/lib/portfolioData';

type LoadState = 'loading' | 'ready' | 'error';

/**
 * Learner portfolio and credentials (d14). A timeline of mastered topics, each
 * with its evidence and a shareable proof; achievements / credentials with an
 * explicit issue + verify state (verifiable, tamper-evident; issuing is
 * permission-laddered); and an export/share-record action. Plain language only —
 * never a raw composite, score, or formula.
 */
export function StudentPortfolio() {
  const { state } = useStore();
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

  return (
    <SurfaceShell
      eyebrow="Your record"
      title="Portfolio and credentials"
      dockIntro="This is the record of what you can do, in plain language, with the evidence behind it. I can help you choose what to share — sharing is always your decision."
      dockChips={['What can I share', 'Explain this credential', 'Show my proudest moment']}
    >
      {/* Export / share the whole record. A deliberate learner action; never auto. */}
      <section className="stack">
        <SpotlightCard padLg>
          <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
            <div>
              <p className="overline" style={{ margin: 0 }}>
                Your record
              </p>
              <h3 className="body-lg" style={{ margin: '4px 0 0' }}>
                A portable record you control
              </h3>
            </div>
            <Tag tone="info">Plain language</Tag>
          </div>
          <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
            Export or share your record with a school, a programme, or anyone you choose. It carries
            what you can do and the evidence behind it — never a raw score.
          </p>
          <div className="rec-actions">
            {exporting ? (
              <span className="row body-sm" style={{ gap: 'var(--space-2)', color: 'var(--text-secondary)' }}>
                <Icon name="check" size="sm" />
                Ready to export. Choose where to send it.
              </span>
            ) : (
              <Button variant="primary" size="sm" onClick={() => setExporting(true)}>
                Export or share record
                <Icon name="send" size="sm" />
              </Button>
            )}
            {exporting ? (
              <Button variant="ghost" size="sm" onClick={() => setExporting(false)}>
                Not now
              </Button>
            ) : null}
          </div>
          <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
            Nothing leaves this surface until you choose to share it.
          </p>
        </SpotlightCard>
      </section>

      {load === 'loading' ? (
        <section className="stack" aria-busy="true" aria-label="Loading your record">
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
          {/* Timeline of mastered topics. */}
          <section className="stack">
            <p className="overline">What you have mastered</p>
            {timeline.length === 0 ? (
              <div className="empty">
                <Icon name="spark" size="lg" className="glyph" />
                <h4 className="body">Your timeline is just beginning</h4>
                <p>As you master topics, each moment will appear here with the evidence behind it.</p>
              </div>
            ) : (
              <div className="parent-timeline">
                {timeline.map((m) => (
                  <div className="parent-timeline-row" key={m.id}>
                    <div className="parent-timeline-marker">
                      {m.independent ? (
                        <IgniteDot label="On your own" />
                      ) : (
                        <span className="dot" aria-hidden="true" />
                      )}
                    </div>
                    <div>
                      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                        <span className="body">{m.topicName}</span>
                        {m.independent ? <Tag tone="success">On your own</Tag> : <Tag tone="neutral">Reliable</Tag>}
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
          {timeline.find((m) => m.independent) ? (
            <section className="stack">
              <p className="overline">A proud moment to share</p>
              <ProofArtifact proof={timeline.find((m) => m.independent)!.proof} />
            </section>
          ) : null}

          {/* Credentials. */}
          <section className="stack">
            <p className="overline">Achievements and credentials</p>
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
        </>
      )}
    </SurfaceShell>
  );
}
