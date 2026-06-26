'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button, ConfidenceBand, Icon, Input, ProgressBar, SpotlightCard, SubjectCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { LibraryItem } from '../_components/LibraryItem';
import { SourceNote } from '../_components/SourceNote';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import { ApprovalControl } from '../_components/ApprovalControl';
import { StatMatrix, Panel, FlagRow, HandnotePanel, SecHead, type FlagModel } from '../_components/StudentComposed';
import { openVidya } from '../_components/VidyaOrb';
import { useStore } from '@/lib/useStore';
import { useGatewaySource } from '@/lib/useGatewaySource';
import { useGenerator } from '@/lib/useGenerator';
import type { CourseOutline } from '@/lib/generate';
import {
  RESOURCE_TYPE_LABEL,
  filterResources,
  libraryStats,
  loadContent,
  type ResourceType,
  type ResourceView,
} from '@/lib/contentData';
import { MATH_SUBJECT_ID, PHYS_SUBJECT_ID, topicsForSubject } from '@/lib/loopData';

type LoadState = 'loading' | 'ready' | 'error';

const SUBJECT_OPTIONS = [
  { id: 'all', name: 'All subjects' },
  { id: MATH_SUBJECT_ID, name: 'Mathematics' },
  { id: PHYS_SUBJECT_ID, name: 'Physics' },
];

const TYPE_OPTIONS: Array<{ id: ResourceType | 'all'; name: string }> = [
  { id: 'all', name: 'All types' },
  ...(Object.keys(RESOURCE_TYPE_LABEL) as ResourceType[]).map((t) => ({
    id: t,
    name: RESOURCE_TYPE_LABEL[t],
  })),
];

/**
 * The content / resource library (d5), recomposed to the bar. A count-up stat
 * matrix opens it (the library at a glance), a colour-band subject grid carries
 * the one hit of pigment (cool hues only), and the resources render as a DENSE
 * two-column grid of subject-tinted cards with their generate-and-verify state.
 * A right aside holds what is waiting for review + the generate-and-verify rule.
 *
 * Browse and search resources mapped to ontology topics; filter by subject,
 * topic, and type. Upload/ingest and generate-with-Vidya are first-class
 * affordances that degrade gracefully — only VERIFIED content is servable, and
 * nothing publishes on its own.
 */
export function ContentLibrary() {
  const { state } = useStore();
  const { source } = useGatewaySource('content');
  const [load, setLoad] = useState<LoadState>('loading');
  const [resources, setResources] = useState<ResourceView[]>([]);

  const [subjectId, setSubjectId] = useState('all');
  const [topicId, setTopicId] = useState<string | undefined>(undefined);
  const [type, setType] = useState<ResourceType | 'all'>('all');
  const [query, setQuery] = useState('');
  const [onlyServable, setOnlyServable] = useState(false);

  const [ingestOpen, setIngestOpen] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [outlineSubject, setOutlineSubject] = useState(MATH_SUBJECT_ID);

  const outline = useGenerator<CourseOutline>('course-outline');

  const [reviewing, setReviewing] = useState<ResourceView | null>(null);

  function approveResource(resource: ResourceView) {
    setResources((prev) =>
      prev.map((r) =>
        r.id === resource.id ? { ...r, verification: 'verified', servable: true } : r,
      ),
    );
    setReviewing(null);
  }

  useEffect(() => {
    try {
      setResources(loadContent(state));
      setLoad('ready');
    } catch {
      setLoad('error');
    }
  }, [state]);

  const topicOptions = useMemo(
    () => (subjectId === 'all' ? [] : topicsForSubject(subjectId)),
    [subjectId],
  );

  const filtered = useMemo(
    () =>
      filterResources(resources, {
        subjectId,
        topicId,
        type: type === 'all' ? undefined : type,
        query,
        onlyServable,
      }),
    [resources, subjectId, topicId, type, query, onlyServable],
  );

  const stats = useMemo(() => libraryStats(resources), [resources]);
  const filteredStats = useMemo(() => libraryStats(filtered), [filtered]);

  // The per-subject summary, for the colour-band grid (whole library, not filtered).
  const subjects = useMemo(() => {
    const map = new Map<string, { name: string; accent: ResourceView['accent']; total: number; verified: number }>();
    for (const r of resources) {
      const cur = map.get(r.subjectId) ?? { name: r.subjectName, accent: r.accent, total: 0, verified: 0 };
      cur.total += 1;
      if (r.verification === 'verified') cur.verified += 1;
      map.set(r.subjectId, cur);
    }
    return [...map.entries()].map(([id, v]) => ({ id, ...v }));
  }, [resources]);

  // Resources awaiting a human read — the aside queue (whole library).
  const awaiting = useMemo(() => resources.filter((r) => !r.servable), [resources]);

  const awaitingFlags: FlagModel[] = awaiting.slice(0, 3).map((r) => ({
    icon: r.source === 'generated' ? 'spark' : 'book',
    title: r.title,
    caption: `${r.subjectName} · held back until a human verifies it.`,
  }));

  const aside = (
    <>
      <div className="ignite-card reveal reveal-3">
        <div className="row-between" style={{ marginBottom: 14 }}>
          <span className="overline">The rule</span>
          <Icon name="check" size="sm" style={{ color: 'var(--accent)' }} />
        </div>
        <div className="who">Only verified content reaches a learner</div>
        <p className="body-sm" style={{ opacity: 0.82, marginTop: 8 }}>
          Everything generated or ingested arrives as a draft. It passes the verification gate, then
          waits for an explicit human approval — nothing is auto-served.
        </p>
      </div>

      <Panel
        title="Waiting for review"
        meta={<Tag tone="warning" dot>{String(awaiting.length)}</Tag>}
      >
        <p className="caption" style={{ marginBottom: 'var(--space-3)' }}>
          Drafts held back until a human verifies them.
        </p>
        {awaitingFlags.length > 0 ? (
          awaitingFlags.map((f, i) => <FlagRow key={i} flag={f} />)
        ) : (
          <p className="caption muted">Nothing is waiting — every resource has been verified.</p>
        )}
        {awaiting[0] ? (
          <button
            type="button"
            className="btn btn-secondary btn-sm btn-block"
            style={{ marginTop: 'var(--space-4)' }}
            onClick={() => setReviewing(awaiting[0]!)}
          >
            Open the first review
          </button>
        ) : null}
      </Panel>

      <HandnotePanel>three drafts still need a human read before Friday</HandnotePanel>
    </>
  );

  return (
    <SurfaceShell
      eyebrow="Content and resources"
      title="Resource library"
      meta={[
        { value: stats.total, label: 'resources' },
        { value: stats.verified, label: 'verified' },
        { value: stats.needsReview + stats.generated, label: 'awaiting review' },
      ]}
      actions={
        <>
          <Button variant="secondary" size="sm" onClick={() => setIngestOpen((v) => !v)}>
            <Icon name="plus" size="sm" />
            Upload or ingest
          </Button>
          <Button variant="accent" size="sm" onClick={() => setGenerateOpen((v) => !v)}>
            <Icon name="spark" size="sm" />
            Generate with Vidya
          </Button>
        </>
      }
      aside={load === 'ready' && filtered.length > 0 ? aside : undefined}
      dockIntro="Ask me to find a resource, or generate fresh material for a topic. Generated content is verified before it can reach a learner — nothing is served unverified."
      dockChips={[
        'Generate a worked example for trig ratios',
        'What is waiting for review',
        'Show only verified material',
      ]}
    >
      {ingestOpen ? (
        <SpotlightCard padLg style={{ marginBottom: 'var(--space-5)' }}>
          <p className="overline" style={{ margin: 0 }}>
            Upload or ingest
          </p>
          <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
            Add a document, image, or recording. We read it with text recognition, transcription, or
            document understanding and map it to a topic. Ingested content arrives as a draft — it is
            never served until a human verifies it.
          </p>
          <div className="row" style={{ gap: 'var(--space-3)', marginTop: 'var(--space-3)', flexWrap: 'wrap' }}>
            <Tag tone="neutral">Text recognition</Tag>
            <Tag tone="neutral">Transcription</Tag>
            <Tag tone="neutral">Document understanding</Tag>
          </div>
          <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
            Reading providers are not connected in this preview, so ingest reports unavailable rather
            than guessing the text. Your upload would be filed as a draft for review.
          </p>
          <div className="rec-actions">
            <Button variant="ghost" size="sm" onClick={() => setIngestOpen(false)}>
              Close
            </Button>
          </div>
        </SpotlightCard>
      ) : null}

      {generateOpen ? (
        <SpotlightCard padLg style={{ marginBottom: 'var(--space-5)' }}>
          <p className="overline" style={{ margin: 0 }}>
            Generate a course outline
          </p>
          <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
            Pick a subject and Classess prepares a course outline — units to topics to outcomes —
            verified against ontology coverage so every outcome resolves. It runs through the
            verification gate first; publishing is your decision, never auto-published.
          </p>
          <div className="segmented" role="group" aria-label="Subject" style={{ marginTop: 'var(--space-3)' }}>
            {SUBJECT_OPTIONS.filter((s) => s.id !== 'all').map((s) => (
              <button
                key={s.id}
                type="button"
                className={outlineSubject === s.id ? 'active' : ''}
                onClick={() => setOutlineSubject(s.id)}
              >
                {s.name}
              </button>
            ))}
          </div>
          <div className="rec-actions">
            <Button
              variant="primary"
              size="sm"
              disabled={outline.phase === 'loading'}
              onClick={() => outline.run({ subject: outlineSubject })}
            >
              <Icon name="spark" size="sm" />
              {outline.phase === 'loading' ? 'Generating…' : 'Generate outline'}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => { setGenerateOpen(false); outline.reset(); }}>
              Close
            </Button>
          </div>

          {outline.phase === 'error' ? (
            <p className="caption" role="status" style={{ marginTop: 'var(--space-3)', color: 'var(--danger)' }}>
              The generator could not be reached. Try again in a moment.
            </p>
          ) : null}

          {outline.phase === 'ready' && outline.artifact ? (
            <div className="stack" style={{ gap: 'var(--space-3)', marginTop: 'var(--space-4)' }}>
              <div className="row-between" style={{ alignItems: 'flex-start' }}>
                <p className="overline" style={{ margin: 0 }}>
                  Verified outline · {outline.artifact.units.length} units
                </p>
                <ConfidenceBand level={outline.confidence} />
              </div>
              {outline.artifact.units.map((u) => (
                <div key={u.unitId} className="cell" style={{ textAlign: 'left' }}>
                  <span className="body-sm"><strong>{u.name}</strong></span>
                  <p className="caption muted" style={{ marginTop: 4 }}>
                    {u.topics.map((t) => t.title).join(' · ') || 'No topics mapped yet.'}
                  </p>
                </div>
              ))}
              <EvidenceDrawer
                evidence={[
                  'Verified against ontology coverage — every outcome the outline names resolves in the curriculum graph.',
                  'Mapped to the curriculum nodes — board-agnostic.',
                ]}
                whySeeing="Publishing a course outline is consequential, so it is prepared and waits for your approval."
              />
              <SourceNote source={outline.source} />
              <ApprovalControl
                kind="Course outline"
                summary={`Publish the ${SUBJECT_OPTIONS.find((s) => s.id === outlineSubject)?.name ?? ''} outline`}
                consequence="The outline is published to the planning home as an annual draft plan."
                eventType="plan.generated"
                payload={{ surface: 'content', subjectId: outlineSubject, kind: 'course-outline' }}
                approveLabel="Publish for approval"
                onAdjust={outline.reset}
              />
            </div>
          ) : null}
        </SpotlightCard>
      ) : null}

      {load === 'loading' ? (
        <section className="stack" aria-busy="true" aria-label="Loading the library">
          <div className="skeleton" style={{ height: 96 }} />
          <div className="skeleton" style={{ height: 220 }} />
        </section>
      ) : load === 'error' ? (
        <div className="empty">
          <Icon name="search" size="lg" className="glyph" />
          <h4 className="body">The library could not be read</h4>
          <p>Something went wrong reading the library. Try again in a moment.</p>
          <Button variant="secondary" size="sm" onClick={() => setLoad('loading')}>
            Try again
          </Button>
        </div>
      ) : (
        <>
          <StatMatrix
            columns={4}
            stats={[
              { label: 'In the library', value: stats.total, delta: 'mapped to topics', deltaDir: 'flat' },
              { label: 'Verified', value: stats.verified, delta: 'servable to learners', deltaDir: 'up' },
              { label: 'Needs review', value: stats.needsReview, delta: 'awaiting a human', deltaDir: 'flat' },
              { label: 'Fresh drafts', value: stats.generated, delta: 'held back', deltaDir: 'down' },
            ]}
          />

          {subjects.length > 0 ? (
            <section className="stack reveal reveal-3" style={{ marginTop: 'var(--space-6)' }}>
              <SecHead title="By subject" meta={<span className="overline">coverage</span>} />
              <div className="matrix" style={{ gridTemplateColumns: `repeat(${Math.min(subjects.length, 3)}, 1fr)` }}>
                {subjects.map((s, i) => {
                  const pct = s.total > 0 ? Math.round((s.verified / s.total) * 100) : 0;
                  return (
                    <SubjectCard
                      key={s.id}
                      name={s.name}
                      code={s.name.slice(0, 3).toUpperCase()}
                      accent={s.accent}
                      className={`reveal reveal-${Math.min(i + 1, 8)}`}
                    >
                      <div className="display-sm" style={{ fontSize: 20 }}>
                        {s.total} {s.total === 1 ? 'resource' : 'resources'}
                      </div>
                      <p className="caption" style={{ marginTop: 5 }}>
                        {s.verified} verified · {s.total - s.verified} awaiting review
                      </p>
                      <ProgressBar
                        value={pct}
                        animate
                        label={`${s.name} verified`}
                        style={{ margin: '14px 0 8px', ['--subject-fill' as string]: `var(--${s.accent})` }}
                        className="subject-progress"
                      />
                      <div className="data">{pct}% verified and servable</div>
                    </SubjectCard>
                  );
                })}
              </div>
            </section>
          ) : null}

          {/* Browse controls */}
          <section className="stack reveal reveal-4" style={{ marginTop: 'var(--space-6)' }}>
            <SecHead
              title="Browse"
              meta={
                <span className="caption muted">
                  {filteredStats.total} {filteredStats.total === 1 ? 'match' : 'matches'} · {filteredStats.verified} verified
                </span>
              }
            />
            <Input
              aria-label="Search the library"
              placeholder="Search by title or topic"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="row" style={{ gap: 'var(--space-3)', flexWrap: 'wrap', alignItems: 'center' }}>
              <div className="segmented" role="group" aria-label="Subject">
                {SUBJECT_OPTIONS.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={subjectId === s.id ? 'active' : ''}
                    onClick={() => {
                      setSubjectId(s.id);
                      setTopicId(undefined);
                    }}
                  >
                    {s.name}
                  </button>
                ))}
              </div>
              <div className="segmented" role="group" aria-label="Type">
                {TYPE_OPTIONS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className={type === t.id ? 'active' : ''}
                    onClick={() => setType(t.id)}
                  >
                    {t.name}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className={`btn btn-ghost btn-sm row${onlyServable ? ' active' : ''}`}
                style={{ gap: 'var(--space-2)' }}
                aria-pressed={onlyServable}
                onClick={() => setOnlyServable((v) => !v)}
              >
                <Icon name={onlyServable ? 'check' : 'plus'} size="sm" />
                Verified only
              </button>
            </div>

            {topicOptions.length > 0 ? (
              <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className={`btn btn-ghost btn-sm${!topicId ? ' active' : ''}`}
                  onClick={() => setTopicId(undefined)}
                >
                  All topics
                </button>
                {topicOptions.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className={`btn btn-ghost btn-sm${topicId === t.id ? ' active' : ''}`}
                    onClick={() => setTopicId(t.id)}
                  >
                    {t.name}
                  </button>
                ))}
              </div>
            ) : null}
          </section>

          {/* Results — the dense subject-tinted grid, or the empty state. */}
          {filtered.length === 0 ? (
            <div className="empty">
              <Icon name="book" size="lg" className="glyph" />
              <h4 className="body">Nothing matches yet</h4>
              <p>
                No resources match these filters. Clear the filters, or generate fresh material for
                the topic with Vidya.
              </p>
              <div className="row" style={{ gap: 'var(--space-3)', justifyContent: 'center' }}>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setType('all');
                    setQuery('');
                    setSubjectId('all');
                    setTopicId(undefined);
                    setOnlyServable(false);
                  }}
                >
                  Clear filters
                </Button>
                <Button variant="secondary" size="sm" onClick={() => openVidya('Generate fresh material for this topic')}>
                  <Icon name="spark" size="sm" /> Try with Vidya
                </Button>
              </div>
            </div>
          ) : (
            <section className="stack reveal reveal-5" style={{ marginTop: 'var(--space-5)' }}>
              <div className="resource-grid">
                {filtered.map((r) => (
                  <LibraryItem key={r.id} resource={r} onReview={setReviewing} />
                ))}
              </div>
              <SourceNote source={source} />
            </section>
          )}

          {reviewing ? (
            <section className="stack" style={{ marginTop: 'var(--space-5)' }}>
              <SpotlightCard hero padLg>
                <div className="row-between" style={{ alignItems: 'flex-start' }}>
                  <div>
                    <p className="overline" style={{ margin: 0 }}>
                      Human verification
                    </p>
                    <h3 className="body-lg" style={{ margin: '4px 0 0' }}>
                      {reviewing.title}
                    </h3>
                    <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                      {reviewing.subjectName} · {reviewing.topicName}
                    </p>
                  </div>
                  <Tag tone="warning" dot>Held back until verified</Tag>
                </div>
                <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
                  {reviewing.summary}
                </p>
                <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
                  {reviewing.provenance} · Rights: {reviewing.licence}
                </p>
                <div className="divider" />
                <div className="rec-actions">
                  <Button variant="accent" size="sm" onClick={() => approveResource(reviewing)}>
                    Approve and make servable
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setReviewing(null)}>
                    Cancel
                  </Button>
                  <span className="caption muted">
                    Approving is a human decision — only verified content reaches a learner.
                  </span>
                </div>
              </SpotlightCard>
            </section>
          ) : null}
        </>
      )}
    </SurfaceShell>
  );
}
