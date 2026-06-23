'use client';

import { useMemo, useState } from 'react';
import { IgniteDot, SpotlightCard, SuggestionChip, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import {
  computeMastery,
  detectGaps,
  gapLabel,
  BAND_SHORT,
  type MasteryResult,
} from '@/lib/engine';
import {
  CURRENT_STUDENT,
  EDGES,
  SCENARIO_NOW,
  SEED_EVENTS,
  topicInfo,
  topicsForSubject,
  MATH_SUBJECT_ID,
  PHYS_SUBJECT_ID,
} from '@/lib/loopData';

/**
 * Progress — the knowledge profile in plain language: what you can do on your
 * own versus with support. Never a number, never the formula. Queryable: a few
 * plain questions ("what am I weakest at", "what unlocks this") answer from the
 * learner's own live reads. The ignite marks a genuine, independent mastery
 * moment.
 */

const SUBJECT = CURRENT_STUDENT.ref;

interface ProfileRow {
  topicId: string;
  topicName: string;
  subjectName: string;
  mastery: MasteryResult;
  topGapLabel: string | null;
}

function buildProfile(): ProfileRow[] {
  const topicIds = [
    ...topicsForSubject(MATH_SUBJECT_ID).map((t) => t.id),
    ...topicsForSubject(PHYS_SUBJECT_ID).map((t) => t.id),
  ];
  const rows: ProfileRow[] = [];
  for (const topicId of topicIds) {
    const mastery = computeMastery(SEED_EVENTS, SUBJECT, topicId, SCENARIO_NOW);
    if (mastery.observationCount === 0) continue; // only show what we have evidence on
    const gaps = detectGaps(SEED_EVENTS, SUBJECT, topicId, EDGES, SCENARIO_NOW, undefined, mastery);
    const topGap = gaps.find((g) => g.evidence.confirmed) ?? gaps[0];
    const info = topicInfo(topicId);
    rows.push({
      topicId,
      topicName: info.name,
      subjectName: info.subjectName,
      mastery,
      topGapLabel: topGap ? gapLabel(topGap.evidence.gapType) : null,
    });
  }
  return rows;
}

type Query = 'weakest' | 'unlocks' | 'independent' | null;

export default function ProgressPage() {
  const rows = useMemo(buildProfile, []);
  const [query, setQuery] = useState<Query>(null);

  const independent = rows.filter((r) => r.mastery.reading.independent);
  const withSupport = rows.filter((r) => !r.mastery.reading.independent);
  const weakest = [...rows].sort((a, b) => a.mastery.reading.composite - b.mastery.reading.composite)[0];

  return (
    <SurfaceShell
      eyebrow="Your progress"
      title="What you can do"
      dockIntro="This is your profile in plain language — what you can do on your own, and what still leans on support. Ask me anything about it."
      dockChips={['What am I weakest at', 'What unlocks identities', 'What can I do on my own']}
    >
      <section className="stack">
        <p className="overline">Ask about your progress</p>
        <div className="home-chips" style={{ justifyContent: 'flex-start' }}>
          <SuggestionChip spark onClick={() => setQuery('weakest')}>
            What am I weakest at
          </SuggestionChip>
          <SuggestionChip spark onClick={() => setQuery('unlocks')}>
            What unlocks the next topic
          </SuggestionChip>
          <SuggestionChip spark onClick={() => setQuery('independent')}>
            What can I do on my own
          </SuggestionChip>
        </div>
        {query ? (
          <SpotlightCard>
            <p className="overline" style={{ margin: 0 }}>
              Answer
            </p>
            <p className="body" style={{ marginTop: 'var(--space-3)' }}>
              {answerFor(query, { weakest, independent: independent.length })}
            </p>
          </SpotlightCard>
        ) : null}
      </section>

      <section className="stack">
        <p className="overline">You can do these on your own</p>
        {independent.length === 0 ? (
          <p className="body-sm quiet">
            Not yet — but you are close on at least one. The green spark appears the moment you do one
            unaided.
          </p>
        ) : (
          independent.map((r) => (
            <SpotlightCard key={r.topicId}>
              <div className="row-between">
                <div className="ignite-row">
                  <IgniteDot label="On your own" />
                  <span className="body">{r.topicName}</span>
                </div>
                <Tag tone="success">On your own</Tag>
              </div>
              <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
                {r.subjectName} · {capitalise(r.mastery.plainLanguage)}.
              </p>
            </SpotlightCard>
          ))
        )}
      </section>

      <section className="stack">
        <p className="overline">These still lean on support</p>
        {withSupport.length === 0 ? (
          <p className="body-sm quiet">Nothing here right now.</p>
        ) : (
          withSupport.map((r) => (
            <div className="mastery-row" key={r.topicId}>
              <div>
                <div className="body" style={{ marginBottom: 2 }}>
                  {r.topicName}
                </div>
                <div className="caption muted">
                  {r.subjectName} · {BAND_SHORT[r.mastery.reading.band]}
                  {r.mastery.revisionDue ? ' · revision is due' : ''}
                </div>
              </div>
              <span className="muted body-sm">{capitalise(r.mastery.plainLanguage)}</span>
            </div>
          ))
        )}
      </section>
    </SurfaceShell>
  );
}

function answerFor(
  q: Exclude<Query, null>,
  ctx: { weakest?: ProfileRow; independent: number },
): string {
  switch (q) {
    case 'weakest':
      return ctx.weakest
        ? `Right now, ${ctx.weakest.topicName} needs the most attention${
            ctx.weakest.topGapLabel ? ` — the focus is ${ctx.weakest.topGapLabel.toLowerCase()}` : ''
          }. That is where a little practice goes furthest.`
        : 'You do not have a clear weak spot yet — keep practising and this will sharpen.';
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
