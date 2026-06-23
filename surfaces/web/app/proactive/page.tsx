import { SurfaceShell } from '../_components/SurfaceShell';
import { RecommendationItem } from '../_components/RecommendationItem';
import { Cell, Matrix, Stat } from '@classess/design-system';
import { RECOMMENDATIONS } from '@/lib/mock';

export const metadata = { title: 'Approval queue — Classess School' };

/**
 * The approval queue — the one manage-by-exception surface for everything Vidya
 * has prepared and is waiting on a human decision. This is distinct from the
 * home Today briefings: it is the full triage queue, ordered by confidence, with
 * an Approve / Adjust / Decline control that NEVER auto-fires. The Today
 * briefings live on the home and the role pages; they are not repeated here.
 */
export default function ProactivePage() {
  // Triage: highest-confidence, ready-to-act items first.
  const order: Record<string, number> = { high: 0, middle: 1, low: 2 };
  const queue = [...RECOMMENDATIONS].sort(
    (a, b) => (order[a.confidence] ?? 3) - (order[b.confidence] ?? 3),
  );
  const high = queue.filter((r) => r.confidence === 'high').length;
  const watch = queue.filter((r) => r.confidence !== 'high').length;

  return (
    <SurfaceShell
      eyebrow="Class 10-B"
      title="Approval queue"
      dockIntro="This is everything I have prepared and am waiting on you to decide. Nothing runs until you approve it. Ask me to adjust or explain any item."
      dockChips={['Explain the fractions recommendation', 'Adjust the due dates', 'Approve the high-confidence items']}
    >
      <section>
        <p className="overline">The queue, at a glance</p>
        <Matrix columns={3}>
          <Cell>
            <Stat label="Awaiting your decision" value={queue.length} />
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              prepared, never sent on their own
            </p>
          </Cell>
          <Cell>
            <Stat label="Ready to act" value={high} />
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              high-confidence, corroborated evidence
            </p>
          </Cell>
          <Cell>
            <Stat label="Worth a closer look" value={watch} />
            <p className="caption muted" style={{ marginTop: 'var(--space-2)' }}>
              lower confidence — review before acting
            </p>
          </Cell>
        </Matrix>
      </section>

      <section className="stack">
        <p className="overline">Triaged by confidence</p>
        <p className="caption quiet">
          Every item is prepared, never sent on its own. You hold the authority — Approve, Adjust,
          or Decline. The strongest, ready-to-act items come first.
        </p>
        {queue.map((r) => (
          <RecommendationItem key={r.id} rec={r} />
        ))}
      </section>
    </SurfaceShell>
  );
}
