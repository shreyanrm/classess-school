'use client';

import { use } from 'react';
import Link from 'next/link';
import { Icon, Matrix, Tag } from '@classess/design-system';
import { DetailShell } from '../../../_components/DetailShell';
import { StatCell } from '../../../_components/StatCell';
import { EvidenceDrawer } from '../../../_components/EvidenceDrawer';
import { SurfaceShell } from '../../../_components/SurfaceShell';
import { sectionDetail, STANDING_META, type SectionSubject } from '@/lib/adminData';

/**
 * The per-class / per-cohort INTERNAL DETAIL drill-down. When the admin opens a
 * flagged section from the briefing, the network rollup, or intelligence, this
 * is where it lands — composed to the sample-page bar exactly like the gold
 * teacher day: a DetailShell page-head with a mono meta line + a back
 * affordance, a count-up section stat matrix, then cols (the cool subject-band
 * cards + the learner roster table on the main; the independent-mastery
 * ignite-card, the Vidya-flagged gaps panel, today's timetable, and a handnote
 * on the 320px aside). A drill-down always has a way up; nothing acts on its own.
 */
export default function SectionDetailPage({ params }: { params: Promise<{ ref: string }> }) {
  const { ref } = use(params);
  const section = sectionDetail(ref);

  if (!section) {
    return (
      <SurfaceShell
        eyebrow="Section detail"
        title="That section is not here"
        breadcrumb={[{ label: 'School', href: '/' }, { label: 'Briefing', href: '/admin' }, { label: 'Unknown section' }]}
      >
        <div className="empty">
          <Icon name="info" size="lg" className="glyph" />
          <h4 className="body">No detail for this section</h4>
          <p>
            The section reference did not match a known class. Return to the briefing and open one of the
            flagged sections.
          </p>
          <div className="rec-actions" style={{ marginTop: 'var(--space-4)', justifyContent: 'center' }}>
            <Link href="/admin" className="btn btn-accent btn-sm row" style={{ gap: 'var(--space-2)' }}>
              Back to briefing
              <Icon name="arrow-right" size="sm" />
            </Link>
          </div>
        </div>
      </SurfaceShell>
    );
  }

  return (
    <DetailShell
      eyebrow={section.grade}
      title={section.label}
      backHref="/admin"
      backLabel="Briefing"
      breadcrumb={[
        { label: 'School', href: '/' },
        { label: 'Briefing', href: '/admin' },
        { label: section.label },
      ]}
      meta={[
        { value: section.learners, label: 'learners' },
        { value: section.subjects.length, label: 'subjects in motion' },
        { label: section.teacher },
        { label: section.behindPlan ? 'behind plan' : 'on plan' },
      ]}
      tabs={[
        { label: 'Overview', active: true },
        { label: 'Intelligence', href: '/admin/intelligence' },
        { label: 'Network', href: '/admin/network' },
      ]}
      aside={
        <>
          <div className="ignite-card reveal reveal-2">
            <div className="row-between" style={{ marginBottom: 14 }}>
              <span className="overline">Just now</span>
              <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
            </div>
            <div className="who">{section.ignite.who}</div>
            <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
              {section.ignite.note}
            </p>
          </div>

          <div className="panel">
            <div className="sec-head" style={{ marginBottom: 8 }}>
              <h4 className="h4" style={{ margin: 0 }}>
                Vidya flagged
              </h4>
              <Tag tone="info">{section.flags.length}</Tag>
            </div>
            <p className="caption" style={{ marginBottom: 12 }}>
              Gaps detected this week in this section, ranked by impact — never a single bad score.
            </p>
            {section.flags.map((f) => (
              <div className="flag" key={f.id}>
                <div className="flag-ic">
                  <Icon name="target" size="sm" />
                </div>
                <div>
                  <div className="body-sm" style={{ fontWeight: 500 }}>
                    {f.topic}
                  </div>
                  <p className="caption">{f.note}</p>
                </div>
              </div>
            ))}
            <Link
              href="/admin/intelligence"
              className="btn btn-secondary btn-sm btn-block"
              style={{ marginTop: 16 }}
            >
              Review interventions
            </Link>
          </div>

          <div className="panel">
            <div className="sec-head" style={{ marginBottom: 8 }}>
              <h4 className="h4" style={{ margin: 0 }}>
                Today
              </h4>
              <span className="overline">timetable</span>
            </div>
            {section.schedule.map((s) => (
              <div className="sched" key={s.t}>
                <span className="t">{s.t}</span>
                <div>
                  <div className="body-sm" style={{ fontWeight: 500 }}>
                    {s.subject}
                  </div>
                  <p className="caption">{s.note}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="panel" style={{ padding: '18px 20px' }}>
            <p className="handnote" style={{ fontSize: 22 }}>
              {section.handnote}
            </p>
          </div>
        </>
      }
    >
      <Matrix columns={4} className="reveal reveal-1">
        <StatCell label="Class mastery" value={section.mastery} unit="%" delta="composite, plain language" tone="up" />
        <StatCell label="Working independently" value={section.independent} unit="%" delta="on their own" tone="up" />
        <StatCell label="Attendance" value={section.attendance} unit="%" delta="this week" tone="flat" />
        <StatCell label="At risk" value={section.atRisk} delta="needs a review" tone={section.atRisk > 0 ? 'down' : 'flat'} />
      </Matrix>

      {section.behindPlan ? (
        <div className="panel" style={{ borderColor: 'var(--warning)' }}>
          <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
            <div>
              <p className="overline" style={{ margin: 0 }}>
                Pacing
              </p>
              <p className="body-sm" style={{ margin: 'var(--space-2) 0 0' }}>
                {section.pacingNote}
              </p>
            </div>
            <Tag tone="warning" dot>
              Behind plan
            </Tag>
          </div>
          <EvidenceDrawer
            evidence={[
              'Planned versus delivered periods are tracked so a behind section is recovered early, not at exam time.',
              'A low-risk recovery stays inside the pacing policy and can be automated once you approve it.',
            ]}
            whySeeing="This section drifted past the pacing threshold, so it surfaces in your briefing and here, with a staged recovery."
          />
        </div>
      ) : null}

      <section>
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>
            Subjects
          </h3>
          <span className="overline">mastery by subject</span>
        </div>
        <Matrix columns={2}>
          {section.subjects.map((s, i) => (
            <SubjectBandCard key={s.code} subject={s} index={i} />
          ))}
        </Matrix>
      </section>

      <section>
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>
            Learners
          </h3>
          <span className="overline">{section.roster.length} shown</span>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Learner</th>
                <th>Current focus</th>
                <th className="num">Mastery</th>
                <th className="num">Independent</th>
                <th>Standing</th>
              </tr>
            </thead>
            <tbody>
              {section.roster.map((l) => {
                const meta = STANDING_META[l.standing];
                return (
                  <tr key={l.id}>
                    <td>
                      <div className="row" style={{ gap: 'var(--space-3)' }}>
                        <span className="avatar avatar-sm">
                          {l.label.replace(/[^A-Za-z]/g, '').slice(-2).toUpperCase()}
                        </span>
                        {l.label}
                      </div>
                    </td>
                    <td className="muted">{l.focus}</td>
                    <td className="num">
                      <span className="data">{l.mastery}%</span>
                    </td>
                    <td className="num">
                      <span className="data">{l.independent}%</span>
                    </td>
                    <td>
                      <Tag tone={meta.tone} dot>
                        {meta.label}
                      </Tag>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="caption quiet" style={{ margin: 0 }}>
          Generic labels only — this is an internal leadership read; no personal information leaves the
          section.
        </p>
      </section>
    </DetailShell>
  );
}

/** A cool subject-band card — the colour band carries the subject, the body the
 *  focus topic + the animated, subject-coloured class-average bar. Never coral. */
function SubjectBandCard({ subject, index }: { subject: SectionSubject; index: number }) {
  return (
    <div
      className={`subject-card reveal reveal-${index + 1}`}
      style={
        {
          '--subject': `var(--${subject.accent})`,
          '--subject-ink': `var(--${subject.accent}-ink)`,
        } as React.CSSProperties
      }
    >
      <div className="band">
        <span className="name">{subject.name}</span>
        <span className="code">{subject.code}</span>
      </div>
      <div className="body">
        <div className="display-sm" style={{ fontSize: 22 }}>
          {subject.focus}
        </div>
        <p className="caption" style={{ marginTop: 5 }}>
          {subject.blurb}
        </p>
        <div className="progress animate" style={{ margin: '14px 0 8px' }}>
          <span style={{ width: `${subject.average}%`, background: `var(--${subject.accent})` }} />
        </div>
        <div className="data">{subject.average}% · class average</div>
      </div>
    </div>
  );
}
