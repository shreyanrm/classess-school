'use client';

import Link from 'next/link';
import { Button, ConfidenceBand, Icon, SpotlightCard, Tag } from '@classess/design-system';
import { SurfaceShell } from '../_components/SurfaceShell';
import { AdminBriefingCard } from '../_components/AdminBriefingCard';
import { RecommendationItem } from '../_components/RecommendationItem';
import { SourceNote } from '../_components/SourceNote';
import { ADMIN_BRIEFINGS, ADMIN_CONCERNS, ADMIN_INTERVENTIONS, RECOMMENDATIONS } from '@/lib/mock';
import { useStore } from '@/lib/useStore';
import { useProactive } from '@/lib/useProactive';
import { useGatewaySource } from '@/lib/useGatewaySource';
import { countStructure } from '@/lib/setupDraft';

/**
 * The admin morning briefing. The cold-start stitch lives here: when no school
 * has been set up, the page is an honest first-step path (set up -> populate ->
 * teach -> loop -> report) rather than mock noise. Once a real school exists,
 * the briefing reflects it; where a surface still has only mock reads, it falls
 * back to mock so existing pages keep working — never a dead end.
 */
export function AdminHome() {
  const { school } = useStore();
  // The blocking approvals run through the same proactive loop write (the wall
  // authorizes; consequential ones still raise the ApprovalControl on the card).
  const { actioned } = useProactive();
  // The briefing / intervention / concern lists are the proactive observer's
  // intelligence. Probe the wall for the live class-insights read so the surface
  // can show the OBSERVABLE source marker — these seed lists render either way,
  // but never as if they were live when the spine did not answer.
  const { source } = useGatewaySource('intelligence-views', { view: 'class-insights' });

  if (!school?.confirmed) {
    return (
      <SurfaceShell
        eyebrow="Welcome"
        title="Let us set up your school"
        dockIntro="Your school is not set up yet. I can suggest a structure and draft a starter roster for you to approve. Start with the blueprint and I will guide you the whole way."
        dockChips={['Suggest a structure', 'What happens after setup', 'How long does this take']}
      >
        <SpotlightCard padLg>
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
            <Link href="/admin/setup">
              <Button variant="accent" size="sm">
                Set up your school
                <Icon name="arrow-right" size="sm" />
              </Button>
            </Link>
          </div>
        </SpotlightCard>
      </SurfaceShell>
    );
  }

  const counts = countStructure(school.structure);
  const teachers = school.roster.filter((m) => m.kind === 'teacher').length;
  const students = school.roster.filter((m) => m.kind === 'student').length;

  return (
    <SurfaceShell
      eyebrow={school.institution.name}
      title="Good morning. Here is what needs your attention."
      dockIntro={`This is the briefing for ${school.institution.name}. Ask which sections are behind, or what to do next.`}
      dockChips={['Which sections are behind', 'What needs my approval', 'What is my next step']}
    >
      <section className="stack">
        <p className="overline">Your school</p>
        <SpotlightCard>
          <div className="row-between" style={{ gap: 'var(--space-4)', alignItems: 'flex-start' }}>
            <div>
              <h3 className="body-lg" style={{ margin: 0 }}>
                {school.institution.name}
              </h3>
              <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
                {school.institution.board} · {counts.grades} grades · {counts.sections} sections ·{' '}
                {teachers} teachers · {students} students
              </p>
            </div>
            <Tag tone="success" dot>
              Set up
            </Tag>
          </div>
          <div className="divider" />
          <p className="overline">Your next step</p>
          <p className="caption muted">
            Populate is done. Move a section into teaching: assign a first quick check, then watch it
            flow through the live loop into a report.
          </p>
          <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
            <Link href="/teacher/assign">
              <Button variant="accent" size="sm">
                Assign a first quick check
                <Icon name="arrow-right" size="sm" />
              </Button>
            </Link>
            <Link href="/loop">
              <Button variant="secondary" size="sm">
                Open the live loop
              </Button>
            </Link>
          </div>
        </SpotlightCard>
      </section>

      <section className="stack">
        <p className="overline">What needs attention</p>
        <p className="caption quiet">
          A calm read while your school fills with real activity. These reflect typical attention
          items until your own events accrue.
        </p>
        {ADMIN_BRIEFINGS.map((b) => (
          <AdminBriefingCard key={b.id} briefing={b} />
        ))}
      </section>

      <section className="stack">
        <p className="overline">Students for possible intervention</p>
        {ADMIN_INTERVENTIONS.map((iv) => (
          <SpotlightCard key={iv.id}>
            <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
              <div>
                <h3 className="body-lg" style={{ margin: 0 }}>
                  {iv.label} — {iv.section}
                </h3>
                <p className="body-sm muted" style={{ marginTop: 'var(--space-2)' }}>
                  {iv.reason}
                </p>
              </div>
              <ConfidenceBand level={iv.confidence} />
            </div>
          </SpotlightCard>
        ))}
      </section>

      <section className="stack">
        <p className="overline">Open concerns</p>
        <div className="admin-list">
          {ADMIN_CONCERNS.map((c) => (
            <div key={c.id} className="admin-list-row">
              <div>
                <div className="body-sm">{c.topic}</div>
                <div className="caption muted">
                  {c.from} · raised {c.raised}
                </div>
              </div>
              <Tag tone={c.status === 'new' ? 'warning' : 'info'}>
                {c.status === 'new' ? 'New' : 'In review'}
              </Tag>
            </div>
          ))}
        </div>
      </section>

      <section className="stack">
        <p className="overline">Blocking approvals</p>
        <p className="caption quiet">
          Prepared and waiting on your decision. Nothing runs until you approve it.
        </p>
        {RECOMMENDATIONS.map((r) => (
          <RecommendationItem key={r.id} rec={r} onActioned={actioned} />
        ))}
      </section>

      <SourceNote source={source} />
    </SurfaceShell>
  );
}
