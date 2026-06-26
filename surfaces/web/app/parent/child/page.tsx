'use client';

import { useEffect, useMemo, useState } from 'react';
import { CrystallizeNode, Icon, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ChildSwitcher } from '../../_components/ChildSwitcher';
import { ProofArtifact } from '../../_components/ProofArtifact';
import { ConsentGated } from '../../_components/ConsentGated';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { useParentRead } from '@/lib/useParentRead';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { useT } from '@/lib/i18n';
import {
  DEFAULT_CHILD_ID,
  findChild,
  TONE_TAG,
  type ParentChildData,
  type PlainPoint,
  type TimelineMoment,
} from '@/lib/parentData';

/**
 * The child view — recomposed to the sample-page bar. A reassurance stat matrix
 * (moments, strengths, support, now-independent), then a .cols layout:
 *   · main — the proud moment as a designed ProofArtifact, the calm timeline as
 *     a real composed view, and the going-well / support areas as designed cards.
 *   · aside — the dark ignite-card (the independent-mastery moment, the one
 *     ultramarine signature), a per-subject snapshot, and a Caveat handnote.
 *
 * Gateway-first read; mock bundle on degrade; SourceNote degrades honestly. All
 * plain language — never a number, score, or formula. Five designed states ship.
 */
export default function ParentChildPage() {
  const [childId, setChildId] = useState(DEFAULT_CHILD_ID);
  const child = findChild(childId);
  const { phase, data, source } = useParentRead(childId);
  const { emit } = useEmit();
  const { t } = useT();

  useEffect(() => {
    if (phase === 'ready') {
      emit({
        type: 'surface.viewed',
        purpose: EVENT_PURPOSE.learning,
        payload: { surface: 'parent.child', child: childId, source },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, childId]);

  const counts = useMemo(() => {
    if (!data) return { moments: 0, strengths: 0, support: 0, independent: 0 };
    const independent =
      data.strengths.filter((p) => p.independent).length +
      data.proof.filter((p) => p.independent).length;
    return {
      moments: data.timeline.length,
      strengths: data.strengths.length,
      support: data.supportAreas.length,
      independent,
    };
  }, [data]);

  // The most recent independent moment — what lights the ignite signature.
  const igniteMoment = data?.strengths.find((p) => p.independent) ?? data?.strengths[0];

  return (
    <SurfaceShell
      eyebrow={child ? child.section : t('parent.child.eyebrow')}
      title={child ? t('parent.child.titleChild', { child: child.label }) : t('parent.child.title')}
      breadcrumb={[
        { label: 'Family', href: '/parent' },
        { label: t('parent.child.eyebrow') },
      ]}
      meta={[
        { value: counts.strengths || '—', label: 'strengths growing' },
        { value: counts.independent || '—', label: 'now on their own' },
        { label: 'drawn from their own work' },
      ]}
      tabs={[
        { label: 'This week', href: '/parent' },
        { label: 'The child', active: true },
        { label: 'Reports', href: '/parent/reports' },
        { label: 'Together', href: '/parent/together' },
      ]}
      dockIntro={t('parent.child.dockIntro')}
      dockChips={[t('parent.child.chip1'), t('parent.child.chip2'), t('parent.child.chip3')]}
      aside={
        phase !== 'ready' || !child || !data ? null : (
          <>
            {igniteMoment ? (
              <div className="ignite-card reveal reveal-2">
                <div className="row-between" style={{ marginBottom: 14 }}>
                  <span className="overline">{t('parent.child.independent')}</span>
                  <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
                </div>
                <div className="who">{igniteMoment.topic}</div>
                <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                  {igniteMoment.note}
                </p>
              </div>
            ) : null}

            <SubjectSnapshotPanel data={data} />

            <div className="panel reveal reveal-4" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                celebrate one of these out loud — pride makes it stick
              </p>
            </div>
          </>
        )
      }
    >
      <section className="stack">
        <p className="overline">{t('parent.child.choose')}</p>
        <ChildSwitcher selectedId={childId} onSelect={setChildId} />
      </section>

      {phase === 'permission-denied' ? (
        <ConsentGated label={child?.label} />
      ) : phase !== 'ready' ? (
        <ReadStates phase={phase} />
      ) : !child || !data ? (
        <ConsentGated label={child?.label} />
      ) : (
        <>
          <Matrix columns={4} className="reveal reveal-1">
            <ChildStat label="Moments this week" value={counts.moments} delta="the calm timeline below" />
            <ChildStat label="Going well" value={counts.strengths} tone="up" delta="strengths in their own work" />
            <ChildStat label="Now on their own" value={counts.independent} tone="up" delta="independent, no prompts" />
            <ChildStat label="Places to support" value={counts.support} delta="next small steps" />
          </Matrix>

          {/* The Proof artifact — the most recent proud moment, drawn from the
              child's own learning. Child-triggerable; shareable by the parent. */}
          {data.proof.length > 0 ? (
            <section className="stack">
              <div className="sec-head">
                <h3 className="h3" style={{ margin: 0 }}>
                  {t('parent.child.proud')}
                </h3>
                <span className="overline">to share</span>
              </div>
              <ProofArtifact proof={data.proof[0]!} />
            </section>
          ) : null}

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                {t('parent.child.timeline')}
              </h3>
              <span className="overline">most recent first</span>
            </div>
            <div className="panel">
              <div className="parent-timeline">
                {data.timeline.map((m) => (
                  <TimelineRow key={m.id} moment={m} />
                ))}
              </div>
            </div>
          </section>

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                {t('parent.child.goingWell')}
              </h3>
              <span className="overline">strengths, in their own work</span>
            </div>
            {data.strengths.length === 0 ? (
              <p className="body-sm muted">{t('parent.child.noStrengths')}</p>
            ) : (
              <Matrix columns={2}>
                {data.strengths.map((p, i) => (
                  <PlainPointCell key={p.id} point={p} kind="strength" index={i} />
                ))}
              </Matrix>
            )}
          </section>

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                {t('parent.child.support')}
              </h3>
              <span className="overline">next small steps, not problems</span>
            </div>
            <p className="caption quiet">{t('parent.child.supportNote')}</p>
            {data.supportAreas.length === 0 ? (
              <p className="body-sm muted">{t('parent.child.noSupport')}</p>
            ) : (
              <Matrix columns={2}>
                {data.supportAreas.map((p, i) => (
                  <PlainPointCell key={p.id} point={p} kind="support" index={i} />
                ))}
              </Matrix>
            )}
          </section>

          <p className="caption quiet row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="info" size="sm" />
            {t('parent.child.note', { child: child.label })}
          </p>
          <SourceNote source={source} />
        </>
      )}
    </SurfaceShell>
  );
}

/** A plain-language count stat for the child view. A count, never a score. */
function ChildStat({
  label,
  value,
  delta,
  tone = 'flat',
}: {
  label: string;
  value: number;
  delta?: string;
  tone?: 'up' | 'down' | 'flat';
}) {
  return (
    <div className="cell">
      <div className="cell-label">{label}</div>
      <div className="cell-value">
        <span>{value}</span>
      </div>
      {delta ? <div className={`cell-delta ${tone}`}>{delta}</div> : null}
    </div>
  );
}

/** A per-subject snapshot card panel for the aside — the hit of cool colour. */
function SubjectSnapshotPanel({ data }: { data: ParentChildData }) {
  const bySubject = new Map<
    string,
    { topic: string; note: string; independent: boolean; mood: number }
  >();
  const consider = (p: PlainPoint, independent: boolean, mood: number) => {
    if (bySubject.has(p.subject)) return;
    bySubject.set(p.subject, { topic: p.topic, note: p.note, independent, mood });
  };
  data.strengths.forEach((p) => consider(p, p.independent ?? true, 0.9));
  data.supportAreas.forEach((p) => consider(p, false, 0.55));
  const cards = Array.from(bySubject.entries()).slice(0, 4);
  if (cards.length === 0) return null;

  return (
    <div className="panel reveal reveal-3">
      <div className="sec-head" style={{ marginBottom: 'var(--space-3)' }}>
        <h4 className="h4" style={{ margin: 0 }}>
          By subject
        </h4>
        <span className="overline">a calm snapshot</span>
      </div>
      <div className="stack" style={{ gap: 'var(--space-3)' }}>
        {cards.map(([accent, c], i) => (
          <div
            key={accent}
            className={`subject-card reveal reveal-${Math.min(i + 1, 4)}`}
            style={
              {
                '--subject': `var(--${accent})`,
                '--subject-ink': `var(--${accent}-ink)`,
                '--subject-fill': `var(--${accent})`,
              } as React.CSSProperties
            }
          >
            <div className="band">
              <span className="name">{c.topic}</span>
              <span className="code">{c.independent ? 'OWN' : 'GROW'}</span>
            </div>
            <div className="body" style={{ padding: '14px 16px 16px' }}>
              <p className="caption" style={{ margin: 0 }}>
                {c.note}
              </p>
              <div
                className="progress animate subject-progress"
                style={{ '--val': `${Math.round(c.mood * 100)}%`, margin: '12px 0 8px' } as React.CSSProperties}
              >
                <span />
              </div>
              <div className="data">
                {c.independent ? 'doing this on their own' : 'a little support helps'}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** One moment on the child's calm timeline. */
function TimelineRow({ moment }: { moment: TimelineMoment }) {
  return (
    <div className={`parent-timeline-row tone-${moment.tone}`}>
      <div className="parent-timeline-marker" aria-hidden>
        <span className={`dot tone-${moment.tone}`} />
      </div>
      <div>
        <div className="row-between" style={{ gap: 'var(--space-3)' }}>
          <span className="body">{moment.title}</span>
          <span className="caption muted">{moment.when}</span>
        </div>
        <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
          {moment.detail}
        </p>
      </div>
    </div>
  );
}

/** A plain-language strength or support area, as a composed cell in a matrix. */
function PlainPointCell({
  point,
  kind,
  index,
}: {
  point: PlainPoint;
  kind: 'strength' | 'support';
  index: number;
}) {
  const { t } = useT();
  return (
    <div className={`cell reveal reveal-${Math.min(index + 1, 4)}`} style={{ padding: 'var(--space-5)' }}>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-3)' }}>
        <div className="row" style={{ gap: 'var(--space-2)' }}>
          {point.independent ? (
            <CrystallizeNode variant="b" inline resolved label={t('parent.child.independent')} />
          ) : null}
          <span className="body" style={{ fontWeight: 500 }}>
            {point.topic}
          </span>
        </div>
        <Tag tone={kind === 'strength' ? TONE_TAG.celebrate : TONE_TAG.support}>
          {kind === 'strength' ? t('parent.child.goingWellTag') : t('parent.child.nextStepTag')}
        </Tag>
      </div>
      <p className="body-sm muted" style={{ marginTop: 'var(--space-3)' }}>
        {point.note}
      </p>
    </div>
  );
}
