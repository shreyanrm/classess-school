'use client';

import { useEffect, useState } from 'react';
import { CrystallizeNode, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { ChildSwitcher } from '../../_components/ChildSwitcher';
import { ProofArtifact } from '../../_components/ProofArtifact';
import { ConsentGated } from '../../_components/ConsentGated';
import { ReadStates } from '../../_components/ReadStates';
import { useParentRead } from '@/lib/useParentRead';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { useT } from '@/lib/i18n';
import {
  DEFAULT_CHILD_ID,
  findChild,
  TONE_TAG,
  type PlainPoint,
  type TimelineMoment,
} from '@/lib/parentData';

/**
 * The child view — one calm timeline per child, with a Child switcher. A
 * one-click switch re-renders the surface for the selected child. Progress,
 * strengths and support areas are all in plain language — never a number, score,
 * or formula. The ignite signature marks what a child can now do on their own.
 */
export default function ParentChildPage() {
  const [childId, setChildId] = useState(DEFAULT_CHILD_ID);
  const child = findChild(childId);
  // Gateway-first governed read; the mock bundle answers on degrade. Switching
  // child re-reads the whole timeline. Five designed states via the hook.
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

  return (
    <SurfaceShell
      eyebrow={child ? child.section : t('parent.child.eyebrow')}
      title={child ? t('parent.child.titleChild', { child: child.label }) : t('parent.child.title')}
      dockIntro={t('parent.child.dockIntro')}
      dockChips={[t('parent.child.chip1'), t('parent.child.chip2'), t('parent.child.chip3')]}
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
          {/* The Proof artifact — the most recent proud moment, drawn from the
              child's own learning. Child-triggerable; shareable by the parent. */}
          {data.proof.length > 0 ? (
            <section className="stack">
              <p className="overline">{t('parent.child.proud')}</p>
              <ProofArtifact proof={data.proof[0]!} />
            </section>
          ) : null}

          <section className="stack">
            <p className="overline">{t('parent.child.timeline')}</p>
            <div className="parent-timeline">
              {data.timeline.map((m) => (
                <TimelineRow key={m.id} moment={m} />
              ))}
            </div>
          </section>

          <section className="stack">
            <p className="overline">{t('parent.child.goingWell')}</p>
            {data.strengths.length === 0 ? (
              <p className="body-sm muted">{t('parent.child.noStrengths')}</p>
            ) : (
              <div className="stack">
                {data.strengths.map((p) => (
                  <PlainPointRow key={p.id} point={p} kind="strength" />
                ))}
              </div>
            )}
          </section>

          <section className="stack">
            <p className="overline">{t('parent.child.support')}</p>
            <p className="caption quiet">{t('parent.child.supportNote')}</p>
            {data.supportAreas.length === 0 ? (
              <p className="body-sm muted">{t('parent.child.noSupport')}</p>
            ) : (
              <div className="stack">
                {data.supportAreas.map((p) => (
                  <PlainPointRow key={p.id} point={p} kind="support" />
                ))}
              </div>
            )}
          </section>

          <p className="caption quiet row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="info" size="sm" />
            {t('parent.child.note', { child: child.label })}
          </p>
        </>
      )}
    </SurfaceShell>
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

/** A plain-language strength or support area. */
function PlainPointRow({ point, kind }: { point: PlainPoint; kind: 'strength' | 'support' }) {
  const { t } = useT();
  return (
    <SpotlightCard>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <div>
          <div className="row" style={{ gap: 'var(--space-2)' }}>
            {point.independent ? (
              <CrystallizeNode variant="b" inline resolved label={t('parent.child.independent')} />
            ) : null}
            <span className="body">{point.topic}</span>
          </div>
          <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
            {point.note}
          </p>
        </div>
        <Tag tone={kind === 'strength' ? TONE_TAG.celebrate : TONE_TAG.support}>
          {kind === 'strength' ? t('parent.child.goingWellTag') : t('parent.child.nextStepTag')}
        </Tag>
      </div>
    </SpotlightCard>
  );
}
