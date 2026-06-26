'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { CrystallizeNode, Icon, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../../_components/SurfaceShell';
import { ReadStates } from '../../../_components/ReadStates';
import { SourceNote } from '../../../_components/SourceNote';
import { EvidenceDrawer } from '../../../_components/EvidenceDrawer';
import { masteryEvidence } from '../../../_components/MasteryConclusion';
import { BloomTaxonomy, PerformanceTrend } from '../../../_components/Charts';
import {
  StatMatrix,
  IgniteCard,
  Panel,
  FlagRow,
  HandnotePanel,
  SecHead,
} from '../../../_components/StudentComposed';
import { useDeepReads, type TopicRead } from '@/lib/useDeepReads';
import { useVizData } from '@/lib/useVizData';
import { BAND_SHORT, gapLabel } from '@/lib/engine';
import { topicInfo, EDGES, LOOP_TOPIC_ID } from '@/lib/loopData';

/**
 * Topic detail — the INTERNAL drill-in from /student/learn or /student/progress
 * into a single topic: where you are (plain language), the evidence behind it,
 * the focuses, and the prerequisites it rests on (with their own live reads).
 *
 * Read GATEWAY-FIRST: this topic AND its confirmed prerequisites are read in one
 * governed hop; the TS engine answers only on degrade, and the OBSERVABLE
 * SourceNote keeps the seam honest. Plain language only — never a number, never
 * the six-dimension diagnostic (that is the teacher view). All five states ship.
 */

/** Plain-language gloss per dimension — words only, never the raw value. */
const DIMENSION_GLOSS: Array<{ key: string; label: string }> = [
  { key: 'performance', label: 'How correct the work is' },
  { key: 'reliability', label: 'How dependable across attempts' },
  { key: 'independence', label: 'How much was done alone, not with help' },
  { key: 'difficulty', label: 'How hard the items succeeded on were' },
  { key: 'recency', label: 'How fresh the evidence is' },
  { key: 'consistency', label: 'How steady the work is over time' },
];

function level(v: number): { word: string; tone: 'success' | 'info' | 'neutral' } {
  if (v >= 0.7) return { word: 'Strong', tone: 'success' };
  if (v >= 0.45) return { word: 'Building', tone: 'info' };
  return { word: 'Early', tone: 'neutral' };
}

export default function TopicDetailPage() {
  const params = useParams();
  const id = typeof params?.id === 'string' ? params.id : Array.isArray(params?.id) ? params.id[0]! : LOOP_TOPIC_ID;
  const info = topicInfo(id);

  // The confirmed prerequisites this topic rests on (from the ontology edges).
  const prereqIds = useMemo(
    () => EDGES.filter((e) => e.to_topic_id === id && e.confirmed).map((e) => e.from_topic_id),
    [id],
  );
  // Read this topic AND its prerequisites gateway-first, in one governed hop.
  const { phase, reads, source } = useDeepReads([id, ...prereqIds]);
  // The topic-scoped analytics — the thinking-level mix and the direction this
  // topic is heading, read gateway-first (seed fallback). Re-labelled to the
  // topic so the read reads as "for this topic", never a class-wide figure.
  const viz = useVizData(['bloom', 'trend'], id);
  const bloom = useMemo(() => ({ ...viz.data.bloom, topicLabel: info.name }), [viz.data.bloom, info.name]);
  const trend = useMemo(
    () => ({ ...viz.data.trend, topicLabel: `${info.name} — your own work` }),
    [viz.data.trend, info.name],
  );

  const read = reads.find((r) => r.topicId === id);
  const prereqReads = prereqIds
    .map((pid) => reads.find((r) => r.topicId === pid))
    .filter((r): r is TopicRead => Boolean(r));

  const mastery = read?.mastery;
  const gaps = read?.gaps ?? [];
  const confirmedGaps = gaps.filter((g) => g.evidence.confirmed);
  const independent = mastery?.reading.independent ?? false;
  const dims = (mastery?.reading.dimensions ?? {}) as unknown as Record<string, number>;

  return (
    <SurfaceShell
      breadcrumb={[
        { label: 'Learning', href: '/student' },
        { label: 'Progress', href: '/student/progress' },
        { label: info.name },
      ]}
      eyebrow={`${info.subjectName} · ${info.chapterName}`}
      title={info.name}
      meta={[
        { value: mastery?.observationCount ?? 0, label: 'pieces of evidence' },
        { value: mastery?.independentObservationCount ?? 0, label: 'done on your own' },
        { label: 'plain language only' },
      ]}
      dockIntro={`Everything behind where you are on ${info.name} — in plain language, with the evidence. Ask me to explain any of it, or what to do next.`}
      dockChips={['Why am I here', 'What is my next step', `Explain ${info.name} simply`]}
      aside={
        phase === 'ready' && mastery ? (
          <>
            {independent ? (
              <IgniteCard
                when="The spark"
                who="You can do this on your own"
                detail="A real, unaided demonstration — no hints, verified across attempts. This is the line that matters."
              />
            ) : (
              <Panel title="Where you are" meta={<Tag tone="info">live read</Tag>}>
                <p className="body-sm" style={{ margin: '0 0 var(--space-2)' }}>
                  {capitalise(mastery.plainLanguage)}.
                </p>
                <p className="caption muted" style={{ margin: 0 }}>
                  {BAND_SHORT[mastery.reading.band]}
                  {mastery.revisionDue ? ' · a short review is due' : ''}
                </p>
              </Panel>
            )}

            <Panel title="What to do next" meta={<span className="overline">your step</span>}>
              <FlagRow
                flag={{
                  icon: 'target',
                  title: independent ? 'Keep it fresh' : 'Practise on your own',
                  caption: independent
                    ? 'You have this — a short revisit now and then keeps it.'
                    : 'The next unaided try is the one that counts.',
                  href: '/student/practice',
                }}
              />
              <FlagRow
                flag={{
                  icon: 'book',
                  title: 'Learn it by trying',
                  caption: 'Meet a problem, attempt it, then see the idea.',
                  href: '/student/learn',
                }}
              />
            </Panel>

            <HandnotePanel>this is a focus, not a failing — naming it is how we close it</HandnotePanel>
          </>
        ) : undefined
      }
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : !mastery || mastery.observationCount === 0 ? (
        <div className="empty">
          <Icon name="target" size="lg" className="glyph" />
          <h4 className="body">No evidence on {info.name} yet</h4>
          <p>
            Once you attempt this topic, its reading will grow here from your own work — what you can
            do, and what to focus on next.
          </p>
          <Link href="/student/learn" className="btn btn-accent btn-sm">
            Learn it first
            <Icon name="arrow-right" size="sm" />
          </Link>
        </div>
      ) : (
        <>
          <StatMatrix
            stats={[
              { label: 'Your evidence', value: mastery.observationCount, delta: 'pieces of work', deltaDir: 'up' },
              { label: 'On your own', value: mastery.independentObservationCount, delta: mastery.independentObservationCount ? 'unaided' : 'the goal', deltaDir: mastery.independentObservationCount ? 'up' : 'flat' },
              { label: 'Where you are', value: <span style={{ fontSize: 15 }}>{capitalise(mastery.reading.band)}</span>, delta: 'plain language', deltaDir: 'flat' },
              { label: 'Focuses', value: confirmedGaps.length, delta: confirmedGaps.length ? 'named' : 'none right now', deltaDir: 'flat' },
            ]}
          />

          <section className="next-step-hero reveal reveal-3">
            <div className="ignite-row">
              {independent ? <CrystallizeNode variant="b" inline resolved label="On your own" /> : null}
              <p className="overline" style={{ margin: 0 }}>
                Where you are
              </p>
            </div>
            <h2 className="display-sm" style={{ margin: '6px 0 0', fontSize: 26 }}>
              {capitalise(mastery.plainLanguage)}
            </h2>
            <p className="body-sm muted" style={{ marginTop: 'var(--space-3)', maxWidth: 560 }}>
              This reading is built from your own attempts and checks — never a mark, never a formula.
              {mastery.revisionDue ? ' A short review is due; the memory is starting to fade.' : ''}
            </p>
            <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
              <EvidenceDrawer
                evidence={masteryEvidence(mastery, gaps)}
                whySeeing={
                  source === 'fallback'
                    ? 'This is the last reading kept on your device — it refreshes from the live engine when the connection is back.'
                    : 'This reading comes from your own attempts and checks, read live from the learning engine.'
                }
              />
              <Link href="/student/practice" className="btn btn-accent btn-sm">
                Practise this
                <Icon name="arrow-right" size="sm" />
              </Link>
            </div>
          </section>

          {/* The reasoning, in plain WORDS — never the raw six-dimension diagnostic. */}
          <section>
            <SecHead title="What stands behind it" meta={<span className="overline">in plain words</span>} />
            <div className="matrix" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
              {DIMENSION_GLOSS.map(({ key, label }, i) => {
                const v = dims[key];
                const lv = typeof v === 'number' ? level(v) : { word: '—', tone: 'neutral' as const };
                return (
                  <div className="cell" key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 'var(--space-3)' }}>
                    <span className="body-sm" style={{ maxWidth: 220 }}>
                      {label}
                    </span>
                    <Tag tone={lv.tone}>{lv.word}</Tag>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Thinking levels — the cognitive mix this topic has drawn on, as a
              donut of demonstrated work. A mix, never a grade. */}
          <section className="stack">
            <SecHead title="Your thinking levels" meta={<span className="overline">where the thinking sits</span>} />
            <BloomTaxonomy data={bloom} source={viz.sourceByKind.bloom} />
          </section>

          {/* Where this topic is heading — a direction read by SHAPE, from your
              own work. The dotted line projects the trend forward, never a promise. */}
          <section className="stack">
            <SecHead title="Where this is heading" meta={<span className="overline">direction, not a grade</span>} />
            <PerformanceTrend data={trend} source={viz.sourceByKind.trend} />
          </section>

          {/* Focuses — the confirmed gaps, never from a single bad score. */}
          {confirmedGaps.length > 0 ? (
            <section>
              <SecHead title="Your focuses" meta={<span className="overline">named, not failing</span>} />
              <div className="panel">
                {confirmedGaps.map((g, i) => (
                  <FlagRow
                    key={i}
                    flag={{
                      icon: 'target',
                      title: gapLabel(g.evidence.gapType),
                      caption: g.evidence.rationale,
                    }}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {/* Prerequisites — what this topic rests on, with their own live reads. */}
          {prereqReads.length > 0 ? (
            <section>
              <SecHead title="What it rests on" meta={<span className="overline">prerequisites</span>} />
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Prerequisite</th>
                      <th>Subject</th>
                      <th>Where you are</th>
                      <th className="num">Open</th>
                    </tr>
                  </thead>
                  <tbody>
                    {prereqReads.map((r) => {
                      const pInfo = topicInfo(r.topicId);
                      const indep = r.mastery.reading.independent;
                      return (
                        <tr key={r.topicId}>
                          <td>
                            <Link href={`/student/topic/${r.topicId}`} className="row roster-name" style={{ gap: 'var(--space-2)' }}>
                              {indep ? <CrystallizeNode variant="b" inline resolved label="On your own" /> : null}
                              {pInfo.name}
                            </Link>
                          </td>
                          <td className="muted">{pInfo.subjectName}</td>
                          <td className="muted">{BAND_SHORT[r.mastery.reading.band]}</td>
                          <td className="num">
                            <Link href={`/student/topic/${r.topicId}`} className="btn btn-ghost btn-sm">
                              <Icon name="arrow-right" size="sm" />
                            </Link>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ) : (
            <section>
              <SecHead title="What it rests on" meta={<span className="overline">prerequisites</span>} />
              <p className="body-sm muted">
                This topic does not rest on an earlier one — it is a foundation others build on.
              </p>
            </section>
          )}

          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
