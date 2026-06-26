'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { ConfidenceBand, Icon, Matrix, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { StatCell } from '../_components/StatCell';
import { AdminBriefingCard } from '../_components/AdminBriefingCard';
import { RecommendationItem } from '../_components/RecommendationItem';
import { SourceNote } from '../_components/SourceNote';
import {
  ADMIN_BRIEFINGS,
  ADMIN_CONCERNS,
  ADMIN_INTERVENTIONS,
  RECOMMENDATIONS,
  SCHOOL_STATS,
} from '@/lib/mock';
import { useStore } from '@/lib/useStore';
import { ensureDemoSchool } from '@/lib/store';
import { useProactive } from '@/lib/useProactive';
import { useGatewaySource } from '@/lib/useGatewaySource';
import { countStructure } from '@/lib/setupDraft';
import { LEAVE_FALLBACK, SUPPORT_LOG_FALLBACK, leaveCounts, supportCounts } from '@/lib/opsData';

/**
 * The admin morning briefing — recomposed to the sample-page bar so it reads as
 * a dense, composed leadership surface, not a colourless stack: a page-head with
 * a mono meta line + tab strip, a count-up school stat matrix, then a cols layout
 * (the attention briefings + the intervention roster on the main; the
 * improvement ignite-card, a Vidya-flagged concerns panel, today's leadership
 * schedule, and a handnote on the 320px aside). The cold-start stitch stays: an
 * honest first-step path when the school is empty. Every read is preserved —
 * gateway-probed source marker, persistent proactive approvals, SourceNote.
 */
export function AdminHome() {
  const { school } = useStore();
  const { actioned } = useProactive();
  const { source } = useGatewaySource('intelligence-views', { view: 'class-insights' });

  // Demo convenience: a fresh DEMO admin (account.demo, onboarding done, no
  // school) is auto-loaded a representative sample school so it lands on the
  // populated briefing rather than the sparse cold-start. A real brand-new admin
  // never trips this — ensureDemoSchool no-ops unless the account is demo — so
  // the genuine cold-start path below stays intact. Runs once after mount, on
  // the client only (the server snapshot is always the empty state).
  useEffect(() => {
    ensureDemoSchool();
  }, []);

  if (!school?.confirmed) {
    return (
      <SurfaceShell
        eyebrow="Welcome"
        title="Let us set up your school"
        breadcrumb={[{ label: 'School', href: '/' }, { label: 'Set up' }]}
        meta={[
          { label: 'no school created yet' },
          { value: '5', label: 'steps, no dead ends' },
        ]}
        dockIntro="Your school is not set up yet. I can suggest a structure and draft a starter roster for you to approve. Start with the blueprint and I will guide you the whole way."
        dockChips={['Suggest a structure', 'What happens after setup', 'How long does this take']}
        aside={
          <>
            <div className="ignite-card reveal reveal-2">
              <div className="row-between" style={{ marginBottom: 14 }}>
                <span className="overline">Where this goes</span>
                <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
              </div>
              <div className="who">A school that compounds, on its own.</div>
              <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
                Once it is set up, this briefing fills with the few things that need you — and nothing
                else. You manage by exception.
              </p>
            </div>
            <div className="panel" style={{ padding: '18px 20px' }}>
              <p className="handnote" style={{ fontSize: 22 }}>
                start with the blueprint — it takes a few minutes and nothing commits until you confirm
              </p>
            </div>
          </>
        }
      >
        <section>
          <div className="sec-head">
            <h3 className="h3" style={{ margin: 0 }}>
              The path
            </h3>
            <span className="overline">cold start</span>
          </div>
          <div className="panel">
            <p className="body" style={{ marginTop: 0, color: 'var(--text-secondary)' }}>
              There is nothing here yet because no school has been created. The path is short and there
              are no dead ends — each step leads to the next.
            </p>
            <ol className="loop-steps" aria-label="Cold-start path" style={{ marginTop: 'var(--space-4)' }}>
              <li className="loop-step active">
                <span className="num">1</span> Set up the blueprint
              </li>
              <li className="loop-step">
                <span className="num">2</span> Populate classes and roster
              </li>
              <li className="loop-step">
                <span className="num">3</span> Teach a first lesson or quick check
              </li>
              <li className="loop-step">
                <span className="num">4</span> Watch the live loop
              </li>
              <li className="loop-step">
                <span className="num">5</span> Read the first report
              </li>
            </ol>
            <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
              <Link href="/admin/setup" className="btn btn-accent btn-sm row" style={{ gap: 'var(--space-2)' }}>
                Set up your school
                <Icon name="arrow-right" size="sm" />
              </Link>
            </div>
          </div>
        </section>
      </SurfaceShell>
    );
  }

  const counts = countStructure(school.structure);
  const teachers = school.roster.filter((m) => m.kind === 'teacher').length;
  const students = school.roster.filter((m) => m.kind === 'student').length;

  // The four headline school numbers for the count-up matrix — drawn from the
  // school-wide signals, plain counts never a formula.
  const onTrack = SCHOOL_STATS.find((s) => s.label === 'Sections on track');
  const behind = SCHOOL_STATS.find((s) => s.label === 'Sections behind');
  const independent = SCHOOL_STATS.find((s) => s.label === 'Students working independently');
  const teacherSupport = SCHOOL_STATS.find((s) => s.label === 'Teachers needing support');

  // Operational read for the leadership panel — leave at the gate + support items.
  const leave = leaveCounts(LEAVE_FALLBACK);
  const support = supportCounts(SUPPORT_LOG_FALLBACK);
  const leaveAwaiting = leave.pending + leave.flagged;

  return (
    <SurfaceShell
      eyebrow={school.institution.name}
      title="Good morning. Here is what needs your attention."
      breadcrumb={[{ label: 'School', href: '/' }, { label: 'Morning briefing' }]}
      meta={[
        { value: counts.grades, label: 'grades' },
        { value: counts.sections, label: 'sections' },
        { value: teachers, label: 'teachers' },
        { value: students, label: 'students' },
        { label: 'manage by exception' },
      ]}
      tabs={[
        { label: 'Briefing', active: true },
        { label: 'Intelligence', href: '/admin/intelligence' },
        { label: 'Control centre', href: '/admin/control-centre' },
        { label: 'Governance', href: '/admin/governance' },
      ]}
      actions={
        <>
          <Link href="/admin/operations" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="clock" size="sm" />
            Operations
          </Link>
          <Link href="/admin/intelligence" className="btn btn-secondary row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="chart" size="sm" />
            School intelligence
          </Link>
          <Link href="/admin/setup" className="btn btn-accent row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="settings" size="sm" />
            Open setup
          </Link>
        </>
      }
      dockIntro={`This is the briefing for ${school.institution.name}. Ask which sections are behind, or what to do next.`}
      dockChips={['Which sections are behind', 'What needs my approval', 'What is my next step']}
      aside={
        <>
          <div className="ignite-card reveal reveal-2">
            <div className="row-between" style={{ marginBottom: 14 }}>
              <span className="overline">Worth recognising</span>
              <Icon name="flame" size="md" style={{ color: 'var(--accent)' }} />
            </div>
            <div className="who">Two crossed into reliable on linear equations</div>
            <p className="body-sm" style={{ opacity: 0.8, marginTop: 8 }}>
              A targeted reset two weeks ago moved both from support-dependent to independent on a fresh
              check — a working intervention worth repeating.
            </p>
          </div>

          <div className="panel">
            <div className="sec-head" style={{ marginBottom: 8 }}>
              <h4 className="h4" style={{ margin: 0 }}>
                Open concerns
              </h4>
              <Tag tone="info">{ADMIN_CONCERNS.length}</Tag>
            </div>
            <p className="caption" style={{ marginBottom: 12 }}>
              Raised by families, queued for a human — generic relationship labels, never personal
              information.
            </p>
            {ADMIN_CONCERNS.map((c) => (
              <div className="flag" key={c.id}>
                <div className="flag-ic">
                  <Icon name={c.status === 'new' ? 'bell' : 'clock'} size="sm" />
                </div>
                <div>
                  <div className="body-sm" style={{ fontWeight: 500 }}>
                    {c.topic}
                  </div>
                  <p className="caption">
                    {c.from} · raised {c.raised}
                  </p>
                </div>
              </div>
            ))}
            <Link
              href="/admin/governance"
              className="btn btn-secondary btn-sm btn-block"
              style={{ marginTop: 16 }}
            >
              Review in governance
            </Link>
          </div>

          <div className="panel">
            <div className="sec-head" style={{ marginBottom: 8 }}>
              <h4 className="h4" style={{ margin: 0 }}>
                Today
              </h4>
              <span className="overline">leadership</span>
            </div>
            {[
              { t: '09:30', subject: 'Pacing review', note: 'Section 10-B Mathematics — two units behind.' },
              { t: '11:00', subject: 'Coaching note', note: 'Section 9-A — new evaluation flow support.' },
              { t: '15:00', subject: 'Approvals', note: `${RECOMMENDATIONS.length} prepared actions awaiting your decision.` },
            ].map((s) => (
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
            <Link
              href="/admin/operations"
              className="btn btn-secondary btn-sm btn-block"
              style={{ marginTop: 16 }}
            >
              {leaveAwaiting > 0 || support.needsLook > 0
                ? `Operations — ${leaveAwaiting} leave, ${support.needsLook} support items`
                : 'Open daily operations'}
            </Link>
          </div>

          <div className="panel" style={{ padding: '18px 20px' }}>
            <p className="handnote" style={{ fontSize: 22 }}>
              two parents still owe consent — nudge before Friday
            </p>
          </div>
        </>
      }
    >
      <Matrix columns={4} className="reveal reveal-1">
        <StatCell
          label="Sections on track"
          value={onTrack ? Number(onTrack.value) : 0}
          delta="against the current pacing plan"
          tone="up"
        />
        <StatCell
          label="Sections behind"
          value={behind ? Number(behind.value) : 0}
          delta="flagged for a coordinator review"
          tone={behind && Number(behind.value) > 0 ? 'down' : 'flat'}
        />
        <StatCell
          label="Working independently"
          value={independent ? Number(independent.value) : 0}
          delta="across the school, this week"
          tone="up"
        />
        <StatCell
          label="Teachers needing support"
          value={teacherSupport ? Number(teacherSupport.value) : 0}
          delta="surfaced from the coaching layer"
          tone="flat"
        />
      </Matrix>

      <section>
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>
            What needs attention
          </h3>
          <span className="overline">manage by exception</span>
        </div>
        <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
          A calm read while your school fills with real activity. These reflect typical attention items
          until your own events accrue.
        </p>
        <div className="stack" style={{ gap: 'var(--space-3)' }}>
          {ADMIN_BRIEFINGS.map((b) => (
            <AdminBriefingCard key={b.id} briefing={b} />
          ))}
        </div>
      </section>

      <section>
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>
            Students for possible intervention
          </h3>
          <span className="overline">evidence-led</span>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Student</th>
                <th>Section</th>
                <th>Why surfaced</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {ADMIN_INTERVENTIONS.map((iv) => {
                const ref = iv.section.replace(/^Section\s+/i, '').toLowerCase();
                return (
                  <tr key={iv.id}>
                    <td>
                      <div className="row" style={{ gap: 'var(--space-3)' }}>
                        <span className="avatar avatar-sm">
                          {iv.label.replace(/[^A-Za-z]/g, '').slice(-2).toUpperCase()}
                        </span>
                        {iv.label}
                      </div>
                    </td>
                    <td className="muted">
                      <Link href={`/admin/section/${ref}`} className="roster-name">
                        {iv.section}
                      </Link>
                    </td>
                    <td className="muted" style={{ maxWidth: 360 }}>
                      {iv.reason}
                    </td>
                    <td>
                      <ConfidenceBand level={iv.confidence} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <div className="sec-head">
          <h3 className="h3" style={{ margin: 0 }}>
            Blocking approvals
          </h3>
          <Tag tone="warning">{RECOMMENDATIONS.length}</Tag>
        </div>
        <p className="caption quiet" style={{ marginTop: 'calc(var(--space-4) * -1)', marginBottom: 'var(--space-4)' }}>
          Prepared and waiting on your decision. Nothing runs until you approve it.
        </p>
        <div className="stack" style={{ gap: 'var(--space-3)' }}>
          {RECOMMENDATIONS.map((r) => (
            <RecommendationItem key={r.id} rec={r} onActioned={actioned} />
          ))}
        </div>
      </section>

      <SourceNote source={source} />
    </SurfaceShell>
  );
}
