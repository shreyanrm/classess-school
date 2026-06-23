'use client';

import { useState } from 'react';
import { Cell, Icon, Matrix, SpotlightCard, Stat, SuggestionChip } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { SCHOOL_STATS, SCHOOL_TRENDS } from '@/lib/mock';

const DIRECTION: Record<'up' | 'flat' | 'down', { tone: string; word: string; icon: 'arrow-up-right' | 'arrow-right' }> = {
  up: { tone: 'var(--success)', word: 'Improving', icon: 'arrow-up-right' },
  flat: { tone: 'var(--text-tertiary)', word: 'Holding', icon: 'arrow-right' },
  down: { tone: 'var(--hot-red)', word: 'Slipping', icon: 'arrow-right' },
};

/**
 * School-wide intelligence — a tight matrix of plain-language reads and mastery
 * trends, board-agnostic and never a raw formula. The ask-anything chips answer
 * inline from the SAME shared data layer (lib/mock), exactly like the inline
 * answer on /student/progress — so the page keeps its promise without sending
 * the admin off to the dock for a basic read. Vidya stays docked for the open,
 * follow-up conversation.
 */
type Query = 'behind' | 'slipping' | 'support' | 'improved';

const QUERIES: { id: Query; label: string }[] = [
  { id: 'behind', label: 'Which sections are behind' },
  { id: 'slipping', label: 'What is slipping this fortnight' },
  { id: 'support', label: 'Where is teacher support most needed' },
  { id: 'improved', label: 'What improved after the May resets' },
];

function answerFor(q: Query): string {
  const behind = SCHOOL_STATS.find((s) => s.label === 'Sections behind');
  const teacherSupport = SCHOOL_STATS.find((s) => s.label === 'Teachers needing support');
  const slipping = SCHOOL_TRENDS.filter((t) => t.direction === 'down');
  const improving = SCHOOL_TRENDS.filter((t) => t.direction === 'up');
  switch (q) {
    case 'behind':
      return behind
        ? `${behind.value} sections are behind — ${behind.detail}. They are flagged here so you can manage by exception rather than read every section.`
        : 'Every section is inside the calm band against the current pacing plan right now.';
    case 'slipping':
      return slipping.length > 0
        ? `${slipping.map((t) => t.topic).join(' and ')} ${slipping.length === 1 ? 'is' : 'are'} slipping. ${slipping[0]!.note}`
        : 'Nothing is slipping this fortnight — the trends are holding or improving.';
    case 'support':
      return teacherSupport
        ? `${teacherSupport.value} teachers are surfaced from the coaching layer as possibly needing support — a private note, never a performance score. Start with the longest-stalled evaluation flow.`
        : 'No teacher is flagged for support right now.';
    case 'improved':
      return improving.length > 0
        ? `${improving.map((t) => t.topic).join(' and ')} improved. ${improving[0]!.note}`
        : 'No clear improvement has registered since the resets yet — give it another fortnight of evidence.';
  }
}

export default function AdminIntelligencePage() {
  const [query, setQuery] = useState<Query | null>(null);

  return (
    <SurfaceShell
      eyebrow="Campus North"
      title="School-wide intelligence"
      dockIntro="Ask the school anything. Which sections are behind, which topics are slipping, what unlocks a unit — I will answer in plain language and show the evidence."
      dockChips={[
        'Which sections are behind',
        'What is slipping this fortnight',
        'Where is teacher support most needed',
        'What improved after the May resets',
      ]}
    >
      <section className="stack">
        <p className="overline">Ask the school</p>
        <p className="caption quiet">
          A plain-language read, answered here from the same intelligence the matrix below shows. For
          a deeper follow-up, keep the conversation going with Vidya.
        </p>
        <div className="home-chips" style={{ justifyContent: 'flex-start' }}>
          {QUERIES.map((q) => (
            <SuggestionChip key={q.id} spark onClick={() => setQuery(q.id)}>
              {q.label}
            </SuggestionChip>
          ))}
        </div>
        {query ? (
          <SpotlightCard>
            <p className="overline" style={{ margin: 0 }}>
              Answer
            </p>
            <p className="body" style={{ marginTop: 'var(--space-3)' }}>
              {answerFor(query)}
            </p>
            <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
              Read in plain language from school-wide signals — no scores or formulas. Ask Vidya for
              the evidence behind any line.
            </p>
          </SpotlightCard>
        ) : null}
      </section>

      <section>
        <p className="overline">Across the school, this week</p>
        <Matrix columns={3}>
          {SCHOOL_STATS.map((s) => (
            <Cell key={s.label}>
              <Stat label={s.label} value={s.value} />
              <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                {s.detail}
              </p>
            </Cell>
          ))}
        </Matrix>
      </section>

      <section className="stack">
        <p className="overline">Mastery trends, in plain language</p>
        <div className="admin-list">
          {SCHOOL_TRENDS.map((t) => {
            const d = DIRECTION[t.direction];
            return (
              <div key={t.topic} className="admin-list-row">
                <div>
                  <div className="body-sm">{t.topic}</div>
                  <div className="caption muted">{t.note}</div>
                </div>
                <span className="row" style={{ gap: 'var(--space-2)', color: d.tone, whiteSpace: 'nowrap' }}>
                  <Icon name={d.icon} size="sm" />
                  <span className="caption">{d.word}</span>
                </span>
              </div>
            );
          })}
        </div>
        <p className="caption quiet">
          Trends read what learners can now do unprompted versus with support. No scores or formulas
          are shown — only movement in plain language, with the evidence one tap away in Vidya.
        </p>
      </section>
    </SurfaceShell>
  );
}
