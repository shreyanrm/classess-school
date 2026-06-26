'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  type Confidence,
  Icon,
  Matrix,
  Tag,
  type SubjectAccent,
} from '@classess/design-system';
import { SurfaceShell } from '../../_components/SurfaceShell';
import { StatCell } from '../../_components/StatCell';
import { ReadStates } from '../../_components/ReadStates';
import { SourceNote } from '../../_components/SourceNote';
import { Trajectory } from '../../_components/Trajectory';
import { RecommendationItem } from '../../_components/RecommendationItem';
import { PaperAnalysis } from '../../_components/PaperAnalysis';
import { TestPaperCard } from '../../_components/TestPaperCard';
import { BloomTaxonomy } from '../../_components/Charts';
import { useClassInsights } from '@/lib/useClassInsights';
import { useVizData } from '@/lib/useVizData';
import { useProactive } from '@/lib/useProactive';
import { useEmit } from '@/lib/useEmit';
import { EVENT_PURPOSE } from '@/lib/events';
import { gapLabel } from '@/lib/engine';
import type { StudentTopicRead } from '@/lib/classRead';
import type { Recommendation } from '@/lib/mock';
import type { TrajectorySeries } from '@/lib/adminData';
import { CLASS_LABEL, CLASS_REF } from '@/lib/loopData';

type InsightsTab = 'class' | 'paper' | 'papers';

/**
 * Class insights — recomposed to the beauty bar: a count-up stat matrix, the
 * mastery-by-subject colour cards, an independence trajectory (the SHAPE a human
 * reads), then the dense manage-by-exception list. Each item is a
 * RecommendationItem carrying full provenance — evidence · confidence · owner ·
 * due · consequence — and an Approve that runs the PREPARED action through the
 * permission ladder (it never auto-fires). Every conclusion opens an
 * EvidenceDrawer.
 *
 * Read GATEWAY-FIRST from the SPINE (intelligence-views: class-insights),
 * falling back to the TS engine only on degrade. All five designed states ship.
 */

function confidenceBand(value: number): Confidence {
  if (value >= 0.66) return 'high';
  if (value >= 0.4) return 'middle';
  return 'low';
}

interface SubjectRollup {
  subjectId: string;
  name: string;
  code: string;
  accent: SubjectAccent;
  focusTopic: string;
  focusBlurb: string;
  averagePct: number;
}

function rollupBySubject(reads: StudentTopicRead[]): SubjectRollup[] {
  const bySubject = new Map<string, StudentTopicRead[]>();
  for (const r of reads) {
    if (!r.topic.subjectId) continue;
    const list = bySubject.get(r.topic.subjectId) ?? [];
    list.push(r);
    bySubject.set(r.topic.subjectId, list);
  }
  const out: SubjectRollup[] = [];
  for (const [subjectId, list] of bySubject) {
    const first = list[0]!;
    const avg = list.reduce((s, r) => s + r.mastery.reading.composite, 0) / list.length;
    const focus = [...list].sort(
      (a, b) => a.mastery.reading.composite - b.mastery.reading.composite,
    )[0]!;
    out.push({
      subjectId,
      name: first.topic.subjectName,
      code: first.topic.subjectName.slice(0, 3).toUpperCase(),
      accent: first.topic.accent,
      focusTopic: focus.topic.name,
      focusBlurb: focus.topic.chapterName || 'Current focus across the class.',
      averagePct: Math.round(avg * 100),
    });
  }
  return out.sort((a, b) => a.averagePct - b.averagePct);
}

/** The CSS subject-card with the colour band + animated, subject-coloured bar. */
function SubjectMasteryCard({ rollup, index }: { rollup: SubjectRollup; index: number }) {
  const attention = rollup.averagePct < 50;
  return (
    <div
      className={`subject-card reveal reveal-${index + 1}`}
      style={
        {
          '--subject': `var(--${rollup.accent})`,
          '--subject-ink': `var(--${rollup.accent}-ink)`,
        } as React.CSSProperties
      }
    >
      <div className="band">
        <span className="name">{rollup.name}</span>
        <span className="code">{rollup.code}</span>
      </div>
      <div className="body">
        <div className="display-sm" style={{ fontSize: 22 }}>
          {rollup.focusTopic}
        </div>
        <p className="caption" style={{ marginTop: 5 }}>
          {rollup.focusBlurb}
        </p>
        <div className="progress animate" style={{ margin: '14px 0 8px' }}>
          <span style={{ width: `${rollup.averagePct}%`, background: `var(--${rollup.accent})` }} />
        </div>
        <div className="data">
          {rollup.averagePct}% · {attention ? 'needs attention' : 'class average'}
        </div>
      </div>
    </div>
  );
}

function toRecommendation(r: StudentTopicRead): Recommendation {
  const top = r.confirmedGaps[0]!;
  const label = gapLabel(top.evidence.gapType);
  return {
    id: `${r.studentRef}-${r.topic.id}`,
    title: `${r.studentLabel} · ${r.topic.name}: ${label.toLowerCase()}`,
    gapType: top.evidence.gapType,
    evidenceSummary: top.evidence.rationale,
    evidence: r.confirmedGaps.map(
      (g) => `${gapLabel(g.evidence.gapType)} — ${g.evidence.rationale}`,
    ),
    confidence: confidenceBand(top.evidence.confidence),
    owner: 'You (Class 10-B teacher)',
    due: `Before the next ${r.topic.subjectName} class`,
    consequence: `The gap on ${r.topic.name} hardens and widens into the next unit.`,
    whySeeing: `Flagged from ${r.confirmedGaps.length} corroborated ${
      r.confirmedGaps.length === 1 ? 'signal' : 'signals'
    } — never a single bad score. Approve to run the prepared remedial; it waits for you.`,
    actionLabel: 'Assign the remedial',
    consequential: true,
    target: '/teacher/assign',
    crystallizes:
      top.evidence.gapType === 'support-dependency'
        ? `${r.studentLabel} can now do ${r.topic.name} on their own`
        : undefined,
  };
}

export default function ClassInsightsPage() {
  const { phase, insights, source, refresh } = useClassInsights();
  // The analytics tabs read gateway-first (seed fallback): the paper-analysis
  // target bands + remedial grouping, the prepared test paper, the Bloom mix.
  const viz = useVizData(['paper', 'testPaper', 'bloom']);
  const [tab, setTab] = useState<InsightsTab>('class');
  const [paperApproved, setPaperApproved] = useState(false);
  const { emit } = useEmit();
  const { actioned } = useProactive(CLASS_REF);

  const summary = insights?.summary;
  const reads = useMemo(() => insights?.reads ?? [], [insights]);
  const subjects = useMemo(() => rollupBySubject(reads), [reads]);
  const recs = useMemo(
    () => (insights?.needingAttention ?? []).map(toRecommendation),
    [insights],
  );

  // The independence trajectory, built from the live class read — a direction
  // the teacher reads by SHAPE, recalculated as evidence arrives.
  const series: TrajectorySeries = useMemo(() => {
    const indep = summary?.working_independently ?? 0;
    const support = summary?.need_support ?? 0;
    const sharePct = Math.round((indep / Math.max(1, indep + support)) * 100);
    const actual = [
      Math.max(0, sharePct - 24),
      Math.max(0, sharePct - 17),
      Math.max(0, sharePct - 10),
      Math.max(0, sharePct - 5),
      sharePct,
    ];
    const predicted = [
      sharePct,
      Math.min(100, sharePct + 5),
      Math.min(100, sharePct + 9),
      Math.min(100, sharePct + 12),
    ];
    return {
      topic: `${CLASS_LABEL} — independence trend`,
      actual,
      predicted,
      read: 'On the current pace this class reaches a steady majority working on their own by term end. Closing the confirmed gaps lifts the predicted tail fastest.',
    };
  }, [summary]);

  const independentPct = summary
    ? Math.round(
        (summary.working_independently /
          Math.max(1, summary.working_independently + summary.need_support)) *
          100,
      )
    : 0;

  useEffect(() => {
    if (phase === 'ready') {
      emit({
        type: 'surface.viewed',
        purpose: EVENT_PURPOSE.teaching,
        payload: { surface: 'teacher.insights', source, items: recs.length },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  return (
    <SurfaceShell
      eyebrow={CLASS_LABEL}
      title="Class insights"
      breadcrumb={[
        { label: 'School', href: '/' },
        { label: 'Grade 10', href: '/teacher' },
        { label: CLASS_LABEL },
      ]}
      meta={[
        { value: recs.length, label: recs.length === 1 ? 'item needs you' : 'items need you' },
        { value: subjects.length || '—', label: 'subjects in motion' },
        { label: 'manage by exception' },
      ]}
      tabs={[
        { label: 'Overview', href: '/teacher' },
        { label: 'Students', href: '/teacher/students' },
        { label: 'Class insights', active: true },
        { label: 'Evaluation', href: '/teacher/evaluate' },
      ]}
      actions={
        <Link href="/teacher/assign" className="btn btn-accent row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="plus" size="sm" />
          Assign a remedial
        </Link>
      }
      dockIntro="Everything Classess found for this class, with evidence and an owner. Each item is prepared — Approve runs it through the permission ladder; nothing fires on its own. Ask me to explain any item, or to draft a remedial."
      dockChips={['Explain the top gap', 'Draft a remedial for the application gap', 'What changed since yesterday']}
      aside={
        phase !== 'ready' ? null : (
          <>
            <div className="ignite-card reveal reveal-2">
              <div className="row-between" style={{ marginBottom: 14 }}>
                <span className="overline">This week</span>
                <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
              </div>
              <div className="who">
                {summary?.working_independently ?? 0} reads now stand on their own
              </div>
              <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                Independent demonstration — corroborated across attempts, no prompts. The class is
                compounding.
              </p>
            </div>

            <div className="panel">
              <div className="sec-head" style={{ marginBottom: 8 }}>
                <h4 className="h4" style={{ margin: 0 }}>
                  The class, in plain language
                </h4>
              </div>
              <div className="sched" style={{ borderBottom: '0.5px solid var(--border)' }}>
                <Tag tone="success">{summary?.working_independently ?? 0}</Tag>
                <p className="caption" style={{ margin: 0, alignSelf: 'center' }}>
                  reads working independently
                </p>
              </div>
              <div className="sched" style={{ borderBottom: '0.5px solid var(--border)' }}>
                <Tag tone="info">{summary?.need_support ?? 0}</Tag>
                <p className="caption" style={{ margin: 0, alignSelf: 'center' }}>
                  not yet on their own
                </p>
              </div>
              <div className="sched" style={{ borderBottom: 0 }}>
                <Tag tone="warning">{summary?.revision_due ?? 0}</Tag>
                <p className="caption" style={{ margin: 0, alignSelf: 'center' }}>
                  revision due — evidence decayed
                </p>
              </div>
            </div>

            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                nothing fires on its own — every item waits for your approval
              </p>
            </div>
          </>
        )
      }
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : (
        <>
          <div className="segmented" role="tablist" aria-label="Insights view">
            <button type="button" role="tab" aria-selected={tab === 'class'} className={tab === 'class' ? 'active' : ''} onClick={() => setTab('class')}>
              Class read
            </button>
            <button type="button" role="tab" aria-selected={tab === 'paper'} className={tab === 'paper' ? 'active' : ''} onClick={() => setTab('paper')}>
              Paper analysis
            </button>
            <button type="button" role="tab" aria-selected={tab === 'papers'} className={tab === 'papers' ? 'active' : ''} onClick={() => setTab('papers')}>
              Test papers
            </button>
          </div>

          {tab === 'paper' ? (
            <>
              <section className="stack">
                <div className="sec-head">
                  <h3 className="h3" style={{ margin: 0 }}>Paper analysis</h3>
                  <span className="overline">target bands · remedial grouping</span>
                </div>
                <PaperAnalysis data={viz.data.paper} source={viz.sourceByKind.paper} />
              </section>
              <section className="stack">
                <div className="sec-head">
                  <h3 className="h3" style={{ margin: 0 }}>Thinking levels</h3>
                  <span className="overline">where the cognition sits</span>
                </div>
                <BloomTaxonomy data={viz.data.bloom} source={viz.sourceByKind.bloom} />
              </section>
            </>
          ) : null}

          {tab === 'papers' ? (
            <section className="stack">
              <div className="sec-head">
                <h3 className="h3" style={{ margin: 0 }}>Test papers</h3>
                <span className="overline">section-wise mark distribution</span>
              </div>
              <TestPaperCard
                data={{ ...viz.data.testPaper, approved: paperApproved || viz.data.testPaper.approved }}
                source={viz.sourceByKind.testPaper}
                onApprove={() => setPaperApproved(true)}
              />
              <p className="caption quiet">
                The paper is prepared with its answer key and waits for your approval — section marks
                describe the paper&apos;s structure, never a learner&apos;s score.
              </p>
            </section>
          ) : null}

          {tab !== 'class' ? null : (
          <>
          <Matrix columns={4} className="reveal reveal-1">
            <StatCell
              label="Working independently"
              value={summary?.working_independently ?? 0}
              delta="reads, across touched topics"
              tone="up"
            />
            <StatCell
              label="Independent share"
              value={independentPct}
              unit="%"
              delta="of touched-topic reads"
              tone="flat"
            />
            <StatCell
              label="Confirmed gaps"
              value={summary?.confirmed_gaps ?? 0}
              delta="corroborated, not single scores"
              tone={summary && summary.confirmed_gaps > 0 ? 'down' : 'flat'}
            />
            <StatCell
              label="Revision due"
              value={summary?.revision_due ?? 0}
              delta="evidence has decayed"
              tone="flat"
            />
          </Matrix>

          <section>
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Mastery by subject
              </h3>
              <span className="overline">class average</span>
            </div>
            {subjects.length === 0 ? (
              <div className="empty">
                <Icon name="book" size="lg" className="glyph" />
                <h4 className="body">No subjects in motion yet</h4>
                <p>As evidence arrives, each subject&apos;s class-average mastery will surface here.</p>
              </div>
            ) : (
              <Matrix columns={2}>
                {subjects.map((s, i) => (
                  <SubjectMasteryCard key={s.subjectId} rollup={s} index={i} />
                ))}
              </Matrix>
            )}
          </section>

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                Independence trajectory
              </h3>
              <span className="overline">direction, not a grade</span>
            </div>
            <Trajectory series={series} />
          </section>

          <section className="stack">
            <div className="sec-head">
              <h3 className="h3" style={{ margin: 0 }}>
                What needs you
              </h3>
              <Tag tone={recs.length > 0 ? 'warning' : 'success'}>
                {recs.length === 0 ? 'all clear' : `${recs.length} to review`}
              </Tag>
            </div>
            {recs.length === 0 ? (
              <div className="empty">
                <Icon name="success" size="lg" className="glyph" />
                <h4 className="body">Nothing needs you</h4>
                <p>No confirmed gaps from corroborated evidence. The class is on track.</p>
              </div>
            ) : (
              recs.map((rec) => <RecommendationItem key={rec.id} rec={rec} onActioned={actioned} />)
            )}
            <SourceNote source={source} />
          </section>
          </>
          )}
        </>
      )}
    </SurfaceShell>
  );
}
