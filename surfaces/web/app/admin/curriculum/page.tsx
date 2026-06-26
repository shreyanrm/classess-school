'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Icon, Input, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { SEED_ONTOLOGY } from '@classess/contracts';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { ReadStates } from '../../_components/ReadStates';
import { useAdminConfig } from '@/lib/adminConfig';

/**
 * Curriculum / ontology view — recomposed to the sample-page bar. Board ->
 * grade -> subject -> unit -> topic with the prerequisite edges, plus
 * hyperlocalisation as live configuration (board is a FIELD, never a lock-in).
 * A page-head with a mono meta line + tab strip, a count-up graph stat matrix
 * (subjects / units / topics / edges), then cols: the subject ladder + the
 * unit/chapter/topic browse + the selected topic's prerequisite edges on the
 * main; the hyperlocalisation panel + a handnote on the 320px aside. The
 * hyperlocalisation fields persist through the wall. Board-agnostic throughout.
 */
export default function CurriculumPage() {
  const ont = SEED_ONTOLOGY;
  const surface = useAdminConfig('curriculum');
  const [subjectId, setSubjectId] = useState<string>(ont.subjects[0]?.id ?? '');
  const [topicId, setTopicId] = useState<string | null>(null);

  const cfg = surface.config;
  const boardName = typeof cfg.board === 'string' ? cfg.board : ont.board.name;
  const language = typeof cfg.language === 'string' ? cfg.language : 'English';
  const region = typeof cfg.region === 'string' ? cfg.region : ont.board.region;
  const calendar = typeof cfg.calendar === 'string' ? cfg.calendar : 'April–March';
  const setField = (key: 'board' | 'language' | 'region' | 'calendar', value: string) => {
    void surface.set(key, value);
  };

  const grade = ont.grades[0];

  const units = useMemo(
    () => ont.units.filter((u) => u.subject_id === subjectId).sort((a, b) => a.sequence - b.sequence),
    [ont.units, subjectId],
  );

  const chaptersByUnit = useMemo(() => {
    const map = new Map<string, typeof ont.chapters>();
    for (const c of ont.chapters) {
      const arr = map.get(c.unit_id) ?? [];
      arr.push(c);
      map.set(c.unit_id, arr);
    }
    return map;
  }, [ont.chapters]);

  const topicsByChapter = useMemo(() => {
    const map = new Map<string, typeof ont.topics>();
    for (const t of ont.topics) {
      const arr = map.get(t.chapter_id) ?? [];
      arr.push(t);
      map.set(t.chapter_id, arr);
    }
    return map;
  }, [ont.topics]);

  const topicName = (id: string) => ont.topics.find((t) => t.id === id)?.name ?? 'topic';

  const edgesForTopic = useMemo(() => {
    if (!topicId) return [];
    return ont.edges.filter((e) => e.from_topic_id === topicId || e.to_topic_id === topicId);
  }, [ont.edges, topicId]);

  const confirmedEdges = ont.edges.filter((e) => e.confirmed).length;

  return (
    <SurfaceShell
      eyebrow="Curriculum and ontology"
      title="The curriculum graph"
      breadcrumb={[{ label: 'School', href: '/' }, { label: 'Curriculum' }]}
      meta={[
        { value: ont.subjects.length, label: 'subjects' },
        { value: ont.units.length, label: 'units' },
        { value: ont.topics.length, label: 'topics' },
        { value: ont.edges.length, label: 'prerequisite edges' },
      ]}
      tabs={[
        { label: 'Graph', active: true },
        { label: 'Calendar', href: '/admin/calendar' },
        { label: 'Exams', href: '/admin/exams' },
        { label: 'Setup', href: '/admin/setup' },
      ]}
      actions={
        <Link href="/admin/setup" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="settings" size="sm" />
          School setup
        </Link>
      }
      dockIntro="This is the living curriculum graph: board, grade, subject, unit, topic, with the prerequisite edges that drive gap detection. Board, language, region and calendar are all fields you set — never locked in."
      dockChips={['What unlocks trigonometric identities', 'Show proposed edges', 'Change the board label']}
      aside={
        surface.phase !== 'ready' ? null : (
          <>
            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>
                  Hyperlocalisation
                </h4>
                <span className="overline">live config</span>
              </div>
              <p className="caption" style={{ marginBottom: 12 }}>
                Board terminology, language, regional calendar — all fields you set. The contract
                stays board-agnostic.{' '}
                {surface.source === 'gateway'
                  ? 'Read back from the event store.'
                  : 'Saved as you set it; records when reachable.'}
              </p>
              <div className="stack" style={{ gap: 'var(--space-3)' }}>
                <label className="stack" style={{ gap: 4 }}>
                  <span className="caption muted">Board label</span>
                  <Input value={boardName} onChange={(e) => setField('board', e.target.value)} aria-label="Board label" />
                </label>
                <label className="stack" style={{ gap: 4 }}>
                  <span className="caption muted">Language of instruction</span>
                  <Input value={language} onChange={(e) => setField('language', e.target.value)} aria-label="Language" />
                </label>
                <label className="stack" style={{ gap: 4 }}>
                  <span className="caption muted">Region</span>
                  <Input value={region} onChange={(e) => setField('region', e.target.value)} aria-label="Region" />
                </label>
                <label className="stack" style={{ gap: 4 }}>
                  <span className="caption muted">Academic calendar</span>
                  <Input value={calendar} onChange={(e) => setField('calendar', e.target.value)} aria-label="Calendar" />
                </label>
              </div>
              <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap', marginTop: 'var(--space-3)' }}>
                <Tag tone="info" dot>
                  {grade?.name ?? 'Grade'}
                </Tag>
                <Tag tone="neutral">{boardName}</Tag>
                <Tag tone="neutral">{language}</Tag>
              </div>
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                the board is a field, never a lock-in — your terms, your calendar
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
            <StatCell label="Subjects" value={ont.subjects.length} delta={`in ${grade?.name ?? 'this grade'}`} tone="flat" />
            <StatCell label="Units" value={ont.units.length} delta="sequenced" tone="flat" />
            <StatCell label="Topics" value={ont.topics.length} delta="the graph's nodes" tone="flat" />
            <StatCell label="Confirmed edges" value={confirmedEdges} delta={`of ${ont.edges.length} prerequisite`} tone="up" />
          </Matrix>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Subject
              </h3>
              <span className="overline">pick a lens</span>
            </div>
            <div className="segmented" role="group" aria-label="Subject">
              {ont.subjects.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={subjectId === s.id ? 'active' : ''}
                  aria-pressed={subjectId === s.id}
                  onClick={() => {
                    setSubjectId(s.id);
                    setTopicId(null);
                  }}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </section>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Unit → chapter → topic
              </h3>
              <span className="overline">tap a topic for its edges</span>
            </div>
            <div className="stack" style={{ gap: 'var(--space-3)' }}>
              {units.map((u) => (
                <SpotlightCard key={u.id}>
                  <div className="row-between">
                    <span className="body-sm" style={{ fontWeight: 500 }}>
                      {u.name}
                    </span>
                    <Tag tone="neutral">unit</Tag>
                  </div>
                  {(chaptersByUnit.get(u.id) ?? []).map((c) => (
                    <div key={c.id} style={{ marginTop: 'var(--space-3)' }}>
                      <p className="caption muted" style={{ margin: '0 0 6px' }}>
                        {c.name}
                      </p>
                      <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                        {(topicsByChapter.get(c.id) ?? []).map((t) => {
                          const on = topicId === t.id;
                          return (
                            <button
                              key={t.id}
                              type="button"
                              className={`ladder-rung${on ? ' active' : ''}`}
                              onClick={() => setTopicId(on ? null : t.id)}
                              aria-pressed={on}
                            >
                              {t.name}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </SpotlightCard>
              ))}
            </div>
          </section>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Prerequisite edges
              </h3>
              <span className="overline">{topicId ? topicName(topicId) : 'select a topic'}</span>
            </div>
            {!topicId ? (
              <div className="empty">
                <Icon name="target" size="lg" className="glyph" />
                <h4 className="body">Select a topic to see what unlocks it</h4>
                <p>Tap any topic above and its prerequisite edges — hard or soft, confirmed or proposed — surface here.</p>
              </div>
            ) : edgesForTopic.length === 0 ? (
              <div className="empty">
                <Icon name="info" size="lg" className="glyph" />
                <h4 className="body">No prerequisite edges on this topic yet</h4>
                <p>This topic stands alone in the graph for now. Edges can be proposed and confirmed by a steward.</p>
              </div>
            ) : (
              <div className="stack" style={{ gap: 'var(--space-2)' }}>
                {edgesForTopic.map((e) => {
                  const outgoing = e.from_topic_id === topicId;
                  return (
                    <SpotlightCard key={e.id}>
                      <div className="row-between" style={{ alignItems: 'flex-start' }}>
                        <div>
                          <div className="row" style={{ gap: 'var(--space-2)' }}>
                            <span className="body-sm" style={{ fontWeight: 500 }}>
                              {outgoing ? 'Unlocks ' : 'Needs first '}
                              {topicName(outgoing ? e.to_topic_id : e.from_topic_id)}
                            </span>
                          </div>
                          <p className="caption muted" style={{ marginTop: 4, maxWidth: 540 }}>
                            {e.rationale}
                          </p>
                        </div>
                        <div className="row" style={{ gap: 'var(--space-2)' }}>
                          <Tag tone={e.kind === 'hard' ? 'warning' : 'neutral'}>{e.kind}</Tag>
                          <Tag tone={e.confirmed ? 'success' : 'info'} dot>
                            {e.confirmed ? 'confirmed' : 'proposed'}
                          </Tag>
                        </div>
                      </div>
                    </SpotlightCard>
                  );
                })}
                <EvidenceDrawer
                  evidence={[
                    'Edges come from the ontology snapshot in @classess/contracts — the same graph the gap engine reads.',
                    'A proposed edge awaits steward confirmation before it drives a hard prerequisite gap.',
                  ]}
                  whySeeing="Prerequisite edges are how the platform reasons about what unlocks what. Showing them keeps the curriculum explainable, not a black box."
                />
              </div>
            )}
          </section>
        </>
      )}
    </SurfaceShell>
  );
}
