'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button, ConfidenceBand, Icon, Input, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { LibraryItem } from '../_components/LibraryItem';
import { SourceNote } from '../_components/SourceNote';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import { ApprovalControl } from '../_components/ApprovalControl';
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
 * The content / resource library (d5). Browse and search resources mapped to
 * ontology topics, each with its generate-and-verify state. Filter by subject,
 * topic, and type. Upload/ingest and generate-with-Vidya are first-class
 * affordances that degrade gracefully — only VERIFIED content is servable, and
 * nothing publishes on its own.
 */
export function ContentLibrary() {
  const { state } = useStore();
  // Probe the live content service so the library can show the OBSERVABLE source
  // marker. The store/seed library renders either way (generate-and-verify keeps
  // its invariant), but it is never presented as live when the spine is silent.
  const { source } = useGatewaySource('content');
  const [load, setLoad] = useState<LoadState>('loading');
  const [resources, setResources] = useState<ResourceView[]>([]);

  // Subject / topic / type / search filters.
  const [subjectId, setSubjectId] = useState('all');
  const [topicId, setTopicId] = useState<string | undefined>(undefined);
  const [type, setType] = useState<ResourceType | 'all'>('all');
  const [query, setQuery] = useState('');
  const [onlyServable, setOnlyServable] = useState(false);

  // A small affordance state: upload + generate panels.
  const [ingestOpen, setIngestOpen] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [outlineSubject, setOutlineSubject] = useState(MATH_SUBJECT_ID);

  // The course-outline generator, gateway-first (SourceNote degrade). Generating
  // PREPARES a verified outline; publishing it is the consequential human act.
  const outline = useGenerator<CourseOutline>('course-outline');

  // The human verification surface for a not-yet-verified resource.
  const [reviewing, setReviewing] = useState<ResourceView | null>(null);

  /** A human approves a held-back resource, making it servable (INVARIANT 7). */
  function approveResource(resource: ResourceView) {
    setResources((prev) =>
      prev.map((r) =>
        r.id === resource.id
          ? { ...r, verification: 'verified', servable: true }
          : r,
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

  const stats = useMemo(() => libraryStats(filtered), [filtered]);

  return (
    <SurfaceShell
      eyebrow="Content and resources"
      title="Resource library"
      dockIntro="Ask me to find a resource, or generate fresh material for a topic. Generated content is verified before it can reach a learner — nothing is served unverified."
      dockChips={[
        'Generate a worked example for trig ratios',
        'What is waiting for review',
        'Show only verified material',
      ]}
    >
      {/* Affordances: upload/ingest and generate-with-Vidya. */}
      <section className="stack">
        <div className="row" style={{ gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          <Button variant="secondary" size="sm" onClick={() => setIngestOpen((v) => !v)}>
            <Icon name="plus" size="sm" />
            Upload or ingest
          </Button>
          <Button variant="primary" size="sm" onClick={() => setGenerateOpen((v) => !v)}>
            <Icon name="spark" size="sm" />
            Generate with Vidya
          </Button>
        </div>

        {ingestOpen ? (
          <SpotlightCard padLg>
            <p className="overline" style={{ margin: 0 }}>
              Upload or ingest
            </p>
            <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
              Add a document, image, or recording. We read it with text recognition,
              transcription, or document understanding and map it to a topic. Ingested content
              arrives as a draft — it is never served until a human verifies it.
            </p>
            <div className="row" style={{ gap: 'var(--space-3)', marginTop: 'var(--space-3)', flexWrap: 'wrap' }}>
              <Tag tone="neutral">Text recognition</Tag>
              <Tag tone="neutral">Transcription</Tag>
              <Tag tone="neutral">Document understanding</Tag>
            </div>
            <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
              Reading providers are not connected in this preview, so ingest reports unavailable
              rather than guessing the text. Your upload would be filed as a draft for review.
            </p>
            <div className="rec-actions">
              <Button variant="ghost" size="sm" onClick={() => setIngestOpen(false)}>
                Close
              </Button>
            </div>
          </SpotlightCard>
        ) : null}

        {generateOpen ? (
          <SpotlightCard padLg>
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
      </section>

      {/* Filters. */}
      <section className="stack">
        <p className="overline">Browse</p>
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

      {/* Results — loading / error / empty / list. */}
      {load === 'loading' ? (
        <section className="stack" aria-busy="true" aria-label="Loading the library">
          <div className="skeleton" style={{ height: 140 }} />
          <div className="skeleton" style={{ height: 140 }} />
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
      ) : filtered.length === 0 ? (
        <div className="empty">
          <Icon name="book" size="lg" className="glyph" />
          <h4 className="body">Nothing matches yet</h4>
          <p>
            No resources match these filters. Clear the filters, or generate fresh material for the
            topic with Vidya.
          </p>
          <div className="row" style={{ gap: 'var(--space-3)', justifyContent: 'center' }}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setType('all');
                setQuery('');
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
        <section className="stack">
          <p className="caption muted">
            {stats.total} {stats.total === 1 ? 'resource' : 'resources'} · {stats.verified} verified
            · {stats.needsReview} need review · {stats.generated} generated
          </p>
          {filtered.map((r) => (
            <LibraryItem key={r.id} resource={r} onReview={setReviewing} />
          ))}
          <SourceNote source={source} />
        </section>
      )}

      {reviewing ? (
        <section className="stack">
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
              <Tag tone="warning">Held back until verified</Tag>
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
    </SurfaceShell>
  );
}
