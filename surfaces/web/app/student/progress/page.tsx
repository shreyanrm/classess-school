'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { CrystallizeNode, Icon, SuggestionChip, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { useEvidenceDrawer } from '../../_components/EvidenceDrawer';
import { masteryEvidence } from '../../_components/MasteryConclusion';
import {
  StatMatrix,
  SubjectGrid,
  IgniteCard,
  Panel,
  FlagRow,
  HandnotePanel,
  SecHead,
  type SubjectCardModel,
} from '../../_components/StudentComposed';
import { useDeepReads, type TopicRead } from '@/lib/useDeepReads';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { BAND_SHORT, gapLabel } from '@/lib/engine';
import {
  topicInfo,
  topicsForSubject,
  subjectCode,
  bandFill,
  MATH_SUBJECT_ID,
  PHYS_SUBJECT_ID,
  LOOP_TOPIC_ID,
} from '@/lib/loopData';

/**
 * Progress — the knowledge profile in plain language, composed dense: a four-up
 * read of the map, the subject-card grid (the hit of cool pigment), a mastery
 * matrix of every topic with evidence on demand, and an aside carrying the
 * Crystallize moment, what unlocks next, and a human note. Never a number,
 * never the formula. Read GATEWAY-FIRST; the engine answers only on degrade.
 */

const MATH_TOPICS = topicsForSubject(MATH_SUBJECT_ID).map((t) => t.id);
const PHYS_TOPICS = topicsForSubject(PHYS_SUBJECT_ID).map((t) => t.id);
const PROFILE_TOPICS = [...MATH_TOPICS, ...PHYS_TOPICS];

// One lead topic per subject for the colour-band cards.
const SUBJECT_LEADS = [MATH_TOPICS[0], PHYS_TOPICS[0]].filter(Boolean) as string[];

type Query = 'weakest' | 'unlocks' | 'independent' | null;

// State tones stay cool/brand: success for independent, info (cool blue) for the
// developing path. Amber/warning is reserved for the one genuinely-fading case
// (set on the row below) so the page never leans warm.
const BAND_TONE = {
  independent: 'success',
  secure: 'info',
  developing: 'info',
  emerging: 'info',
  'not-started': 'neutral',
} as const;

export default function ProgressPage() {
  const { phase, reads, source } = useDeepReads(PROFILE_TOPICS);
  const { emit } = useEmit();
  const drawer = useEvidenceDrawer();
  const [query, setQuery] = useState<Query>(null);

  // Only show topics we have evidence on (the spine omits the rest too).
  const rows = useMemo(() => reads.filter((r) => r.mastery.observationCount > 0), [reads]);
  const independent = rows.filter((r) => r.mastery.reading.independent);
  const weakest = [...rows].sort(
    (a, b) => a.mastery.reading.composite - b.mastery.reading.composite,
  )[0];
  const revisionDue = rows.filter((r) => r.mastery.revisionDue);
  const focuses = rows.reduce((n, r) => n + r.gaps.filter((g) => g.evidence.confirmed).length, 0);

  // The subject-card grid — built from the live reads, cool hues only.
  const subjects: SubjectCardModel[] = useMemo(
    () =>
      SUBJECT_LEADS.map((tid) => {
        const info = topicInfo(tid);
        // Read the strongest topic in this subject for the card's headline focus.
        const subjectRows = rows.filter((r) => topicInfo(r.topicId).subjectId === info.subjectId);
        const lead = [...subjectRows].sort(
          (a, b) => b.mastery.reading.composite - a.mastery.reading.composite,
        )[0];
        const r = lead ?? rows.find((x) => x.topicId === tid);
        const band = r?.mastery.reading.band ?? 'not-started';
        const focusInfo = r ? topicInfo(r.topicId) : info;
        return {
          topicId: r?.topicId ?? tid,
          subjectName: info.subjectName,
          code: subjectCode(info.subjectId),
          accent: info.accent,
          focus: focusInfo.name,
          caption: r ? capitalise(r.mastery.plainLanguage) : 'No evidence here yet.',
          progress: bandFill(band),
          progressLabel: r?.mastery.reading.independent
            ? 'On your own'
            : `${subjectRows.length} ${subjectRows.length === 1 ? 'topic' : 'topics'} in motion`,
          independent: r?.mastery.reading.independent,
        };
      }),
    [rows],
  );

  // The surface viewed event — attributed, consent-stamped (learning purpose).
  useEffect(() => {
    if (phase === 'ready')
      emit({ type: 'surface.viewed', purpose: EVENT_PURPOSE.learning, payload: { surface: 'student.progress', source } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  function ask(q: Exclude<Query, null>) {
    setQuery(q);
    emit({ type: 'knowledge.queried', purpose: EVENT_PURPOSE.learning, payload: { query: q } });
  }

  function openEvidence(r: TopicRead) {
    drawer.open({
      claim: `${topicInfo(r.topicId).name} — ${capitalise(r.mastery.plainLanguage)}`,
      evidence: masteryEvidence(r.mastery, r.gaps),
      whySeeing:
        source === 'fallback'
          ? 'This is the last reading kept on your device — it refreshes from the live engine when the connection is back.'
          : 'This reading comes from your own attempts and checks, read live from the learning engine.',
    });
  }

  return (
    <SurfaceShell
      breadcrumb={[{ label: 'Learning', href: '/student' }, { label: 'Progress' }]}
      eyebrow="Your progress"
      title="What you can do"
      meta={[
        { value: rows.length, label: 'topics with evidence' },
        { value: independent.length, label: 'on your own' },
        { label: 'plain language only' },
      ]}
      dockIntro="This is your profile in plain language — what you can do on your own, and what still leans on support. Ask me anything about it."
      dockChips={['What am I weakest at', 'What unlocks identities', 'What can I do on my own']}
      aside={
        phase === 'ready' && rows.length > 0 ? (
          <>
            <IgniteCard
              when="The spark"
              who={
                independent.length > 0
                  ? `${independent.length} ${independent.length === 1 ? 'topic' : 'topics'} on your own`
                  : 'One unaided win from the spark'
              }
              detail="Each one is a real, unaided demonstration — no hints, verified across attempts. That is the line that matters."
            />

            <Panel title="What unlocks next" meta={<span className="overline">prerequisite</span>}>
              <p className="caption" style={{ marginBottom: 12 }}>
                Doing one topic on your own opens the next.
              </p>
              <FlagRow
                flag={{
                  icon: 'target',
                  title: 'Trigonometric Identities',
                  caption: 'Built on the ratios — doing the ratios unaided opens it.',
                  href: `/student/topic/${LOOP_TOPIC_ID}`,
                }}
              />
              {revisionDue[0] ? (
                <FlagRow
                  flag={{
                    icon: 'clock',
                    title: `${topicInfo(revisionDue[0].topicId).name} is fading`,
                    caption: 'You had this solid — a short review keeps it.',
                    href: '/student/mocks',
                  }}
                />
              ) : null}
            </Panel>

            <HandnotePanel>naming a focus is not a failing — it is how we close it</HandnotePanel>
          </>
        ) : undefined
      }
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : rows.length === 0 ? (
        <div className="empty">
          <Icon name="target" size="lg" className="glyph" />
          <h4 className="body">Let us find where to start</h4>
          <p>
            There is no evidence on your map yet. A short diagnostic seeds it, and from then on this
            view grows from your real attempts.
          </p>
          <Link href="/student/learn" className="btn btn-accent btn-sm">
            Start your first topic
            <Icon name="arrow-right" size="sm" />
          </Link>
        </div>
      ) : (
        <>
          <StatMatrix
            stats={[
              { label: 'On your own', value: independent.length, delta: independent.length > 0 ? 'the green spark' : 'almost there', deltaDir: independent.length > 0 ? 'up' : 'flat' },
              { label: 'With support', value: rows.length - independent.length, delta: 'leaning on a nudge', deltaDir: 'flat' },
              { label: 'Your evidence', value: rows.reduce((n, r) => n + r.mastery.observationCount, 0), delta: 'pieces of work', deltaDir: 'up' },
              { label: 'Focuses', value: focuses, delta: focuses ? 'named, not failing' : 'none right now', deltaDir: 'flat' },
            ]}
          />

          <section className="reveal reveal-3">
            <SecHead title="Your subjects" meta={<span className="overline">mastery by subject</span>} />
            <SubjectGrid subjects={subjects} />
          </section>

          <section className="stack">
            <p className="overline">Ask about your progress</p>
            <div className="row" style={{ flexWrap: 'wrap', gap: 'var(--space-2)' }}>
              <SuggestionChip spark onClick={() => ask('weakest')}>
                What am I weakest at
              </SuggestionChip>
              <SuggestionChip spark onClick={() => ask('unlocks')}>
                What unlocks the next topic
              </SuggestionChip>
              <SuggestionChip spark onClick={() => ask('independent')}>
                What can I do on my own
              </SuggestionChip>
            </div>
            {query ? (
              <div className="next-step-hero" style={{ padding: 'var(--space-5)' }}>
                <p className="overline" style={{ margin: 0 }}>
                  Answer
                </p>
                <p className="body" style={{ marginTop: 'var(--space-3)' }}>
                  {answerFor(query, { weakest, independent: independent.length })}
                </p>
              </div>
            ) : null}
          </section>

          <section>
            <SecHead title="Every topic" meta={<span className="overline">tap a row for the evidence</span>} />
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Topic</th>
                    <th>Subject</th>
                    <th>Where you are</th>
                    <th>Status</th>
                    <th className="num">Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {[...rows]
                    .sort((a, b) => b.mastery.reading.composite - a.mastery.reading.composite)
                    .map((r) => {
                      const info = topicInfo(r.topicId);
                      const indep = r.mastery.reading.independent;
                      return (
                        <tr key={r.topicId}>
                          <td>
                            <Link href={`/student/topic/${r.topicId}`} className="row roster-name" style={{ gap: 'var(--space-2)' }}>
                              {indep ? <CrystallizeNode variant="b" inline resolved label="On your own" /> : null}
                              {info.name}
                            </Link>
                          </td>
                          <td className="muted">{info.subjectName}</td>
                          <td className="muted">{BAND_SHORT[r.mastery.reading.band]}</td>
                          <td>
                            <Tag tone={r.mastery.revisionDue ? 'warning' : BAND_TONE[r.mastery.reading.band]}>
                              <span className="dot" />
                              {indep ? 'On your own' : statusWord(r)}
                            </Tag>
                          </td>
                          <td className="num">
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              onClick={() => openEvidence(r)}
                              aria-haspopup="dialog"
                            >
                              <Icon name="info" size="sm" /> Why
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </section>

          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}

function statusWord(r: TopicRead): string {
  if (r.mastery.revisionDue) return 'Fading';
  const band = r.mastery.reading.band;
  if (band === 'secure') return 'Reliable';
  if (band === 'developing') return 'Developing';
  if (band === 'emerging') return 'With support';
  return 'Starting';
}

function answerFor(
  q: Exclude<Query, null>,
  ctx: { weakest?: TopicRead; independent: number },
): string {
  switch (q) {
    case 'weakest': {
      if (!ctx.weakest) return 'You do not have a clear weak spot yet — keep practising and this will sharpen.';
      const gap = ctx.weakest.gaps.find((g) => g.evidence.confirmed) ?? ctx.weakest.gaps[0];
      const name = topicInfo(ctx.weakest.topicId).name;
      return `Right now, ${name} needs the most attention${
        gap ? ` — the focus is ${gapLabel(gap.evidence.gapType).toLowerCase()}` : ''
      }. That is where a little practice goes furthest.`;
    }
    case 'unlocks':
      return 'Doing Trigonometric Ratios on your own unlocks Trigonometric Identities — the identities are built on the ratios, so the ratios come first.';
    case 'independent':
      return ctx.independent > 0
        ? `You can do ${ctx.independent} ${ctx.independent === 1 ? 'topic' : 'topics'} on your own so far. Each one is a real, unaided demonstration — not a lucky score.`
        : 'You are close on at least one topic. The moment you do one unaided, it moves into "on your own".';
  }
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
