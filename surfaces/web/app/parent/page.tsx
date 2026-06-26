'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Button,
  Cell,
  ConfidenceBand,
  Icon,
  Matrix,
  SpotlightCard,
  Tag,
  type SubjectAccent,
} from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { ChildSwitcher } from '../_components/ChildSwitcher';
import { ProofArtifact } from '../_components/ProofArtifact';
import { ConsentGated } from '../_components/ConsentGated';
import { EvidenceDrawer } from '../_components/EvidenceDrawer';
import { ReadStates } from '../_components/ReadStates';
import { SourceNote } from '../_components/SourceNote';
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
  type ParentChildData,
  type PlainPoint,
} from '@/lib/parentData';

/**
 * The Parent · This week — recomposed to the sample-page bar. A reassurance lead
 * (the calm header line as a real ignite-style hero), a 4-up count-up stat
 * matrix of plain-language counts (never a raw score), then a .cols layout:
 *   · main — the three things this week, each a designed action card; and a
 *     "where to go next" rail of real, navigable links.
 *   · aside — the shareable win as a designed ProofArtifact, a subject-card
 *     snapshot (the hit of cool/brand colour), and a Caveat handnote.
 *
 * Every read is GATEWAY-FIRST (intelligence-views via useParentRead) and falls
 * back to the typed mock bundle on degrade; the SourceNote degrades honestly.
 * Generated free-text renders into the parent's preferred language through tx().
 * Consent gates the whole surface. All five designed states ship.
 */
export default function ParentTodayPage() {
  const [childId, setChildId] = useState(DEFAULT_CHILD_ID);
  const child = findChild(childId);
  const { phase, data, source } = useParentRead(childId);
  const { emit } = useEmit();
  const { t } = useT();

  const briefings = useMemo(() => data?.briefings ?? [], [data]);
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

  // Plain-language counts for the meta line + the stat matrix. Counts, never
  // scores — a parent reads how many wins, support areas, on-track signals, and
  // minutes of suggested home time this week.
  const counts = countParentWeek(data);

  return (
    <SurfaceShell
      eyebrow={child ? child.section : t('parent.week.eyebrow')}
      title={t('parent.week.title')}
      breadcrumb={[{ label: 'Family', href: '/parent' }, { label: t('parent.week.eyebrow') }]}
      meta={[
        { value: counts.celebrate || '—', label: 'wins this week' },
        { value: counts.support || '—', label: 'places to support' },
        { label: 'a partnership, not a watch list' },
      ]}
      tabs={[
        { label: 'This week', active: true },
        { label: 'The child', href: '/parent/child' },
        { label: 'Reports', href: '/parent/reports' },
        { label: 'Together', href: '/parent/together' },
      ]}
      dockIntro={t('parent.week.dockIntro')}
      dockChips={[t('parent.week.chip1'), t('parent.week.chip2'), t('parent.week.chip3')]}
      aside={
        phase !== 'ready' || !child || !data ? null : (
          <>
            {data.proof.length > 0 ? (
              <div className="reveal reveal-2">
                <div className="sec-head" style={{ marginBottom: 'var(--space-3)' }}>
                  <h4 className="h4" style={{ margin: 0 }}>
                    {t('parent.child.proud')}
                  </h4>
                  <span className="overline">to share</span>
                </div>
                <ProofArtifact proof={data.proof[0]!} />
              </div>
            ) : null}

            <SubjectSnapshotPanel data={data} />

            <div className="panel reveal reveal-4" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                {child.label.toLowerCase()} is doing well — notice one win out loud at home
              </p>
            </div>
          </>
        )
      }
    >
      <section className="stack">
        <div
          className="row-between"
          style={{ alignItems: 'flex-end', gap: 'var(--space-3)', flexWrap: 'wrap' }}
        >
          <p className="overline" style={{ margin: 0 }}>
            {t('parent.week.whose')}
          </p>
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
          {/* The reassurance lead — a calm, tonal hero. Not a number; a sentence
              of confidence drawn from this week's shape. The one accent moment. */}
          <div className="ignite-card reveal reveal-1">
            <div className="row-between" style={{ marginBottom: 14 }}>
              <span className="overline">{t('parent.week.eyebrow')}</span>
              <Icon name="spark" size="md" style={{ color: 'var(--accent)' }} />
            </div>
            <div className="who">{reassurance(child.label, counts)}</div>
            <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
              {t('parent.week.threeNote', { child: child.label })}
            </p>
          </div>

          <Matrix columns={4} className="reveal reveal-1">
            <ParentStat label="Wins this week" value={counts.celebrate} tone="up" delta="drawn from their own work" />
            <ParentStat label="Places to support" value={counts.support} tone="flat" delta="next small steps, not problems" />
            <ParentStat label="On track" value={counts.steady} tone="flat" delta="steady and reliable" />
            <ParentStat label="Home time" value={counts.minutes} unit=" min" tone="flat" delta="suggested this week" />
          </Matrix>

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                {t('parent.week.three')}
              </h3>
              <span className="overline">this week, ranked by where you help most</span>
            </div>
            {data.briefings.map((b) => (
              <ParentBriefingCard
                key={b.id}
                briefing={b}
                childId={childId}
                childLabel={child.label}
                tx={tx}
              />
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
            <SourceNote source={source} />
          </section>
        </>
      )}
    </SurfaceShell>
  );
}

/** Plain-language counts for the week, derived from the consented bundle. */
function countParentWeek(data: ParentChildData | null): {
  celebrate: number;
  support: number;
  steady: number;
  minutes: number;
} {
  if (!data) return { celebrate: 0, support: 0, steady: 0, minutes: 0 };
  const celebrate = data.briefings.filter((b) => b.tone === 'celebrate').length;
  const support = data.briefings.filter((b) => b.tone === 'support').length;
  const steady = data.briefings.filter((b) => b.tone === 'steady').length;
  const minutes = data.learnAlongside.reduce((s, a) => s + a.minutes, 0);
  return { celebrate, support, steady, minutes };
}

/** A calm, honest reassurance line — confidence without a number. */
function reassurance(
  childLabel: string,
  counts: { celebrate: number; support: number },
): string {
  if (counts.celebrate > 0 && counts.support === 0) {
    return `A bright week for ${childLabel} — only wins to enjoy.`;
  }
  if (counts.celebrate > 0) {
    return `${childLabel} is doing well — a win to enjoy, and one small place to help.`;
  }
  if (counts.support > 0) {
    return `A steady week for ${childLabel} — one gentle place a little home time helps.`;
  }
  return `A calm, steady week for ${childLabel}. Nothing needs your attention right now.`;
}

/**
 * One stat in the parent week matrix — a plain-language count, never a score.
 * The big value counts up on view (the sample-page signature), but begins at its
 * final value so it never reads a stale "0" before the count starts: these are
 * small, calm numbers, and an honest readout matters more than the animation.
 */
function ParentStat({
  label,
  value,
  unit,
  delta,
  tone = 'flat',
}: {
  label: string;
  value: number;
  unit?: string;
  delta?: string;
  tone?: 'up' | 'down' | 'flat';
}) {
  return (
    <Cell>
      <div className="cell-label">{label}</div>
      <div className="cell-value">
        <span>{value}</span>
        {unit ?? null}
      </div>
      {delta ? <div className={`cell-delta ${tone}`}>{delta}</div> : null}
    </Cell>
  );
}

/** A subject-card snapshot for the aside — the hit of cool/brand colour. */
function SubjectSnapshotPanel({ data }: { data: ParentChildData }) {
  // Build a per-subject snapshot from this child's strengths + support areas:
  // one card per subject, with a plain phrase and a calm progress mood.
  const bySubject = new Map<
    SubjectAccent,
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
              <div className="data">{c.independent ? 'doing this on their own' : 'a little support helps'}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
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
      payload: {
        surface: 'parent.this-week',
        child: childId,
        briefing: briefing.id,
        tone: briefing.tone,
      },
      canonicalUuid: childId,
    });
    setActing(false);
    setTaken(true);
  }

  if (deferred) {
    return (
      <SpotlightCard>
        <div className="row-between">
          <span className="muted body-sm">
            {t('parent.week.setAside')} — {tx(briefing.title)}
          </span>
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
          <Link
            href={briefing.target}
            className="btn btn-ghost btn-sm row"
            style={{ gap: 'var(--space-2)' }}
          >
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
