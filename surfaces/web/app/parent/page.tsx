'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Button, ConfidenceBand, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { ChildSwitcher } from '../_components/ChildSwitcher';
import { ConsentGated } from '../_components/ConsentGated';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import { ReadStates } from '../_components/ReadStates';
import { LanguageBadge } from '../_components/LanguageBadge';
import { useParentRead } from '@/lib/useParentRead';
import { useReaderText } from '@/lib/useReaderText';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { routeToTask } from '@/lib/commData';
import { useT } from '@/lib/i18n';
import {
  DEFAULT_CHILD_ID,
  findChild,
  TONE_TAG,
  type ParentBriefing,
} from '@/lib/parentData';

/**
 * The Parent Today — three actions that need attention this week, in the
 * parent's language. Calm, never a dashboard, never surveillance. The Child
 * switcher re-renders the whole view for the selected child; a child whose view
 * is not consented shows the consent-gated state instead of data.
 */
export default function ParentTodayPage() {
  const [childId, setChildId] = useState(DEFAULT_CHILD_ID);
  const child = findChild(childId);
  // Gateway-first governed read for the selected child; the mock bundle answers
  // on degrade. Switching child re-reads the whole surface. The hook exposes the
  // five designed states (loading / error / offline / permission-denied / ready).
  const { phase, data, source } = useParentRead(childId);
  const { emit } = useEmit();
  const { t } = useT();

  // The absolution-engine briefings are composed in English by the read; render
  // their generated free-text into the parent's language through the TRANSLATE
  // capability (subject terms preserved). English readers skip the network. The
  // original stands until/unless a render lands — nothing ever blanks.
  const briefings = data?.briefings ?? [];
  const { tx, rendering, rendered, locale } = useReaderText(
    briefings.flatMap((b) => [
      b.title,
      b.why,
      b.builds,
      b.consequence,
      b.nextAction,
      b.whySeeing,
      ...b.evidence,
    ]),
  );

  // The surface viewed event — attributed, consent-stamped, with the read source.
  useEffect(() => {
    if (phase === 'ready') {
      emit({
        type: 'surface.viewed',
        purpose: EVENT_PURPOSE.learning,
        payload: { surface: 'parent.this-week', child: childId, source },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, childId]);

  return (
    <SurfaceShell
      eyebrow={t('parent.week.eyebrow')}
      title={t('parent.week.title')}
      dockIntro={t('parent.week.dockIntro')}
      dockChips={[t('parent.week.chip1'), t('parent.week.chip2'), t('parent.week.chip3')]}
    >
      <section className="stack">
        <div className="row-between" style={{ alignItems: 'flex-end', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          <p className="overline" style={{ margin: 0 }}>{t('parent.week.whose')}</p>
          <LanguageBadge locale={locale} rendering={rendering} rendered={rendered} />
        </div>
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
          <section className="stack">
            <p className="overline">{t('parent.week.three')}</p>
            <p className="caption quiet">
              {t('parent.week.threeNote', { child: child.label })}
            </p>
            {data.briefings.map((b) => (
              <ParentBriefingCard key={b.id} briefing={b} childId={childId} childLabel={child.label} tx={tx} />
            ))}
          </section>

          <section className="stack">
            <p className="overline">{t('parent.week.next')}</p>
            <div className="parent-links">
              <Link href="/parent/child" className="card parent-link c-spot">
                <Icon name="chart" size="md" />
                <div>
                  <div className="body">{t('parent.week.linkChild')}</div>
                  <div className="caption muted">{t('parent.week.linkChildSub')}</div>
                </div>
                <Icon name="chevron-right" size="sm" />
              </Link>
              <Link href="/parent/reports" className="card parent-link c-spot">
                <Icon name="book" size="md" />
                <div>
                  <div className="body">{t('parent.week.linkReports')}</div>
                  <div className="caption muted">{t('parent.week.linkReportsSub')}</div>
                </div>
                <Icon name="chevron-right" size="sm" />
              </Link>
              <Link href="/parent/together" className="card parent-link c-spot">
                <Icon name="spark" size="md" />
                <div>
                  <div className="body">{t('parent.week.linkTogether')}</div>
                  <div className="caption muted">{t('parent.week.linkTogetherSub')}</div>
                </div>
                <Icon name="chevron-right" size="sm" />
              </Link>
            </div>
          </section>

          <section className="stack">
            <p className="caption quiet row" style={{ gap: 'var(--space-2)' }}>
              <Icon name="info" size="sm" />
              {t('parent.week.partnership', { child: child.label })}
            </p>
          </section>
        </>
      )}
    </SurfaceShell>
  );
}

/** A single Today item, in the parent's language. Supportive, never an order. */
function ParentBriefingCard({
  briefing,
  childId,
  childLabel,
  tx,
}: {
  briefing: ParentBriefing;
  childId: string;
  childLabel: string;
  /** Render generated text into the reader's language (falls back to original). */
  tx: (text: string) => string;
}) {
  const [deferred, setDeferred] = useState(false);
  const { emit } = useEmit();
  const { t } = useT();
  // GAP#11 — the one action triggers a REAL outcome, not just navigation. Taking
  // it on a support item routes the concern into an owned, tracked task through
  // the wall (communication.make_tasks -> hub.route_to_task, a persisted
  // communication.task_created event) AND emits an attributed parent event. A
  // celebration/on-track item has no task to route; it emits the action taken.
  const [acting, setActing] = useState(false);
  const [taken, setTaken] = useState(false);

  async function takeAction() {
    setActing(true);
    if (briefing.tone === 'support') {
      await routeToTask({
        body: `${briefing.title}. ${briefing.why}`,
        title: `Support at home — ${childLabel}`,
        ownerRole: 'parent',
        why: briefing.builds,
        dueDate: briefing.due,
        surface: 'parent',
        contextRef: childId,
        senderRef: childId,
        consentRef: childId,
      });
    }
    await emit({
      type: 'parent.action_taken',
      purpose: EVENT_PURPOSE.learning,
      payload: { surface: 'parent.this-week', child: childId, briefing: briefing.id, tone: briefing.tone },
      canonicalUuid: childId,
    });
    setActing(false);
    setTaken(true);
  }

  if (deferred) {
    return (
      <SpotlightCard>
        <div className="row-between">
          <span className="muted body-sm">{t('parent.week.setAside')} — {tx(briefing.title)}</span>
          <Button variant="ghost" size="sm" onClick={() => setDeferred(false)}>
            {t('parent.week.bringBack')}
          </Button>
        </div>
      </SpotlightCard>
    );
  }

  return (
    <SpotlightCard padLg>
      <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
        <h3 className="body-lg" style={{ margin: 0 }}>
          {tx(briefing.title)}
        </h3>
        <Tag tone={TONE_TAG[briefing.tone]}>
          {briefing.tone === 'celebrate'
            ? 'A win'
            : briefing.tone === 'support'
              ? 'A little help'
              : 'On track'}
        </Tag>
      </div>

      <div className="row" style={{ marginTop: 'var(--space-3)', color: 'var(--text-secondary)' }}>
        <span className="row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="clock" size="sm" />
          <span className="caption">About {briefing.minutes} min</span>
        </span>
      </div>

      <p className="body-sm" style={{ marginTop: 'var(--space-3)' }}>
        <span className="quiet">Why. </span>
        {tx(briefing.why)}
      </p>
      <p className="body-sm" style={{ marginTop: 'var(--space-2)' }}>
        <span className="quiet">It helps build. </span>
        {tx(briefing.builds)}
      </p>

      <div className="rec-meta">
        <div>
          <div className="k">Confidence</div>
          <div className="v">
            <ConfidenceBand level={briefing.confidence} />
          </div>
        </div>
        <div>
          <div className="k">Owner</div>
          <div className="v">{briefing.owner}</div>
        </div>
        <div>
          <div className="k">Best by</div>
          <div className="v">{briefing.due}</div>
        </div>
        <div>
          <div className="k">If left</div>
          <div className="v">{tx(briefing.consequence)}</div>
        </div>
      </div>

      <EvidenceDrawer
        evidence={briefing.evidence.map((line) => tx(line))}
        whySeeing={briefing.whySeeing ? tx(briefing.whySeeing) : undefined}
      />

      {taken ? (
        <div className="rec-actions" style={{ marginTop: 'var(--space-4)', alignItems: 'center' }}>
          <Tag tone="success">{t('parent.week.actionTaken')}</Tag>
          <span className="caption muted">
            {briefing.tone === 'support'
              ? t('parent.week.actionTakenSupport')
              : t('parent.week.actionTakenNoted')}
          </span>
          <Link href={briefing.target} className="caption row" style={{ gap: 4 }}>
            {t('parent.week.open')} <Icon name="arrow-right" size="sm" />
          </Link>
        </div>
      ) : (
        <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
          <Button variant="primary" size="sm" disabled={acting} onClick={takeAction}>
            {acting ? t('parent.week.acting') : tx(briefing.nextAction)}
            <Icon name="arrow-right" size="sm" />
          </Button>
          <Link href={briefing.target} className="btn btn-ghost btn-sm row" style={{ gap: 'var(--space-2)' }}>
            {t('parent.week.open')}
          </Link>
          <Button variant="ghost" size="sm" onClick={() => setDeferred(true)}>
            {t('parent.week.setAside')}
          </Button>
        </div>
      )}
    </SpotlightCard>
  );
}
