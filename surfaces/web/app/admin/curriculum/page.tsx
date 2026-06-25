'use client';

import { useMemo, useState } from 'react';
import { Button, Icon, Input, SpotlightCard, Tag } from '@classess/design-system';
import { SEED_ONTOLOGY } from '@classess/contracts';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { EvidenceDrawer } from '../../_components/EvidenceDrawer';
import { ReadStates } from '../../_components/ReadStates';
import { useSurfaceState } from '@/lib/useSurfaceState';

/**
 * d3 — Curriculum / ontology view. Board -> grade -> subject -> unit -> topic,
 * with the prerequisite edges shown (hard/soft, confirmed/proposed), plus a
 * hyperlocalisation panel: board terminology is a FIELD (never a lock-in),
 * language, region, and calendar are live configuration.
 *
 * Reads the ontology seed from @classess/contracts. Board is a field; nothing
 * here is baked to one board.
 */

export default function CurriculumPage() {
  const ont = SEED_ONTOLOGY;
  const surface = useSurfaceState();
  const [subjectId, setSubjectId] = useState<string>(ont.subjects[0]?.id ?? '');
  const [topicId, setTopicId] = useState<string | null>(null);

  // Live hyperlocalisation config (board is a field, not a lock-in).
  const [boardName, setBoardName] = useState(ont.board.name);
  const [language, setLanguage] = useState('English');
  const [region, setRegion] = useState(ont.board.region);
  const [calendar, setCalendar] = useState('April–March');

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

  // Prerequisite edges touching the selected topic.
  const edgesForTopic = useMemo(() => {
    if (!topicId) return [];
    return ont.edges.filter((e) => e.from_topic_id === topicId || e.to_topic_id === topicId);
  }, [ont.edges, topicId]);

  return (
    <SurfaceShell
      eyebrow="Curriculum and ontology"
      title="The curriculum graph"
      dockIntro="This is the living curriculum graph: board, grade, subject, unit, topic, with the prerequisite edges that drive gap detection. Board, language, region and calendar are all fields you set — never locked in."
      dockChips={['What unlocks trigonometric identities', 'Show proposed edges', 'Change the board label']}
    >
      {surface.phase !== 'ready' ? (
        <ReadStates phase={surface.phase} onRetry={surface.refresh} />
      ) : (
      <>
      <section className="stack">
        <p className="overline">Hyperlocalisation</p>
        <p className="caption quiet">
          Board terminology, language, regional calendar — all live configuration. The board is a
          field; the contract stays board-agnostic.
        </p>
        <div className="cols-2">
          <label className="stack" style={{ gap: 4 }}>
            <span className="caption muted">Board label</span>
            <Input value={boardName} onChange={(e) => setBoardName(e.target.value)} aria-label="Board label" />
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="caption muted">Language of instruction</span>
            <Input value={language} onChange={(e) => setLanguage(e.target.value)} aria-label="Language" />
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="caption muted">Region</span>
            <Input value={region} onChange={(e) => setRegion(e.target.value)} aria-label="Region" />
          </label>
          <label className="stack" style={{ gap: 4 }}>
            <span className="caption muted">Academic calendar</span>
            <Input value={calendar} onChange={(e) => setCalendar(e.target.value)} aria-label="Calendar" />
          </label>
        </div>
        <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          <Tag tone="info">{grade?.name ?? 'Grade'}</Tag>
          <Tag tone="neutral">{boardName}</Tag>
          <Tag tone="neutral">{language}</Tag>
          <Tag tone="neutral">{calendar}</Tag>
        </div>
      </section>

      <section className="stack">
        <p className="overline">Subject</p>
        <div className="ladder" role="group" aria-label="Subject" style={{ maxWidth: 360 }}>
          {ont.subjects.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`ladder-rung${subjectId === s.id ? ' active' : ''}`}
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

      <section className="stack">
        <p className="overline">Unit → chapter → topic</p>
        <div className="stack" style={{ gap: 'var(--space-3)' }}>
          {units.map((u) => (
            <SpotlightCard key={u.id}>
              <div className="row-between">
                <span className="body-sm">{u.name}</span>
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

      {topicId ? (
        <section className="stack">
          <p className="overline">Prerequisite edges — {topicName(topicId)}</p>
          {edgesForTopic.length === 0 ? (
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
                          <span className="body-sm">
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
                        <Tag tone={e.confirmed ? 'success' : 'info'}>
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
      ) : (
        <p className="caption muted">Select a topic above to see its prerequisite edges.</p>
      )}
      </>
      )}
    </SurfaceShell>
  );
}
