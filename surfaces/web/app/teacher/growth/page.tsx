'use client';

import { useMemo, useState } from 'react';
import { Button, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { useSurfaceState } from '@/lib/useSurfaceState';
import { useGatewaySource } from '@/lib/useGatewaySource';
import {
  GROWTH_SIGNALS,
  GROWTH_DIRECTION_META,
  nextGrowthInsight,
  type GrowthSignal,
} from '@/lib/ring2Data';

/**
 * The private teacher coaching view — talk ratio, questioning, equity of voice,
 * wait time. This is growth, never judgement: one insight at a time, never a
 * score, never a ranking, never a comparison to other teachers. It is yours
 * alone. The signals come from classroom signals attributed only to the opaque
 * canonical id, never to named students.
 */
export default function TeacherGrowthPage() {
  // Private coaching read — carries the same five designed states from one place.
  const { phase, refresh } = useSurfaceState();
  // The coaching signals are the spine's teacher-growth.coaching read (private,
  // non-punitive). Probe the wall so the OBSERVABLE source marker sits on the
  // surface — the seed signals render either way, but never as if they were live
  // when the spine was silent.
  const { source } = useGatewaySource('teacher-growth');
  const lead = useMemo(() => nextGrowthInsight(GROWTH_SIGNALS), []);
  const [focusId, setFocusId] = useState<string | null>(lead?.id ?? null);

  const focus = GROWTH_SIGNALS.find((s) => s.id === focusId) ?? lead;

  return (
    <SurfaceShell
      eyebrow="Your growth"
      title="One thing to grow this week"
      dockIntro="This view is private to you. It is here to help you grow, not to rank you. We surface one idea at a time. Ask me to explain any signal or to suggest a small experiment."
      dockChips={['What is talk ratio', 'Give me a wait-time experiment', 'Why this insight first']}
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : (
      <>
      <section className="stack">
        <SpotlightCard padLg>
          <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
            <Icon name="spark" size="sm" />
            <span className="overline" style={{ margin: 0 }}>
              Private to you
            </span>
          </div>
          <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
            No one else sees this. There is no score and no leaderboard — just your own teaching,
            reflected calmly, one idea at a time.
          </p>
        </SpotlightCard>
      </section>

      {focus ? (
        <section className="stack">
          <p className="overline">This week&apos;s focus</p>
          <FocusInsight signal={focus} />
        </section>
      ) : (
        <section className="stack">
          <SpotlightCard>
            <div className="empty">
              <Icon name="spark" size="lg" className="glyph" />
              <h4 className="body">No coaching signals yet</h4>
              <p>After a few lessons with classroom signals on, a gentle insight will appear here.</p>
            </div>
          </SpotlightCard>
        </section>
      )}

      <section className="stack">
        <p className="overline">Your other signals</p>
        <p className="caption quiet">
          You can look at any of these when you are ready. They are a calm read of your practice,
          never a grade. Pick one to make it this week&apos;s focus.
        </p>
        <div className="growth-list">
          {GROWTH_SIGNALS.map((s) => {
            const meta = GROWTH_DIRECTION_META[s.direction];
            const active = s.id === focus?.id;
            return (
              <button
                key={s.id}
                type="button"
                className={`growth-row${active ? ' active' : ''}`}
                aria-pressed={active}
                onClick={() => setFocusId(s.id)}
              >
                <div>
                  <div className="body-sm">{s.label}</div>
                  <div className="caption muted">{s.meaning}</div>
                </div>
                <Tag tone={meta.tone}>{meta.label}</Tag>
              </button>
            );
          })}
        </div>
        <SourceNote source={source} />
      </section>
      </>
      )}
    </SurfaceShell>
  );
}

function FocusInsight({ signal }: { signal: GrowthSignal }) {
  const meta = GROWTH_DIRECTION_META[signal.direction];
  const [tried, setTried] = useState(false);

  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
        <div>
          <h3 className="display-sm" style={{ margin: 0 }}>
            {signal.label}
          </h3>
          <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
            {signal.meaning}
          </p>
        </div>
        <Tag tone={meta.tone}>{meta.label}</Tag>
      </div>

      <div className="cols-2" style={{ marginTop: 'var(--space-5)' }}>
        <div>
          <div className="caption muted">Your lesson</div>
          <div className="body" style={{ marginTop: 'var(--space-1)' }}>
            {signal.yourValue}
          </div>
        </div>
        <div>
          <div className="caption muted">What tends to work</div>
          <div className="body" style={{ marginTop: 'var(--space-1)' }}>
            {signal.healthyRange}
          </div>
        </div>
      </div>

      <div
        className="stack"
        style={{
          marginTop: 'var(--space-5)',
          paddingTop: 'var(--space-4)',
          borderTop: '1px solid var(--border)',
        }}
      >
        <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
          <Icon name="target" size="sm" />
          <span className="overline" style={{ margin: 0 }}>
            One small experiment
          </span>
        </div>
        <p className="body" style={{ margin: 0 }}>
          {signal.tryThis}
        </p>
        <div className="rec-actions">
          {tried ? (
            <span className="state-pill correct">
              <span className="dot" />
              You are giving this a try this week
            </span>
          ) : (
            <Button variant="primary" size="sm" onClick={() => setTried(true)}>
              I will try this
            </Button>
          )}
        </div>
      </div>
    </SpotlightCard>
  );
}
