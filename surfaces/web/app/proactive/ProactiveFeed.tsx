'use client';

/* ============================================================================
   app/proactive/ProactiveFeed.tsx — the approval queue, wired to the live
   proactive loop (recommend -> approve -> execute, spec 13 b11 + ladder 11).

   The one manage-by-exception surface for everything Vidya has prepared and is
   waiting on a human decision. It READS the recommendation feed gateway-first
   (lib/useProactive -> /api/proactive -> the spine, the local list on degrade),
   triages by confidence, and renders the real RecommendationItem control:
   consequential items raise the ApprovalControl, reversible items execute with
   an undo, and a resolved gap plays the CrystallizeNode moment.

   Ships all FIVE designed states — empty / loading / error / offline /
   permission-denied — each with a real CTA. v4.1 tokens only; no shadow.
   ============================================================================ */

import { SurfaceShell } from '../_components/SurfaceShell';
import { RecommendationItem } from '../_components/RecommendationItem';
import { ReadStates } from '../_components/ReadStates';
import { Button, Cell, Icon, Matrix, Stat } from '@classess/design-system';
import { openVidya } from '../_components/VidyaOrb';
import { useProactive } from '@/lib/useProactive';

export function ProactiveFeed() {
  const { phase, recommendations, source, refresh, actioned } = useProactive();

  // Triage: highest-confidence, ready-to-act items first.
  const order: Record<string, number> = { high: 0, middle: 1, low: 2 };
  const queue = [...recommendations].sort(
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
      {phase !== 'ready' ? (
        // loading / error / offline / permission-denied — the four non-ready
        // states, each with its real CTA (retry / ask Vidya / last-synced read).
        <ReadStates phase={phase} onRetry={refresh} />
      ) : queue.length === 0 ? (
        // The empty state — a real, calm outcome, not a dead end.
        <div className="empty">
          <Icon name="info" size="lg" className="glyph" />
          <h4 className="body">Nothing waiting on you</h4>
          <p>
            The queue is clear — I have nothing prepared that needs a decision right now. I will
            surface anything the moment the evidence is strong enough.
          </p>
          <Button variant="secondary" size="sm" onClick={() => openVidya('What are you watching for Class 10-B')}>
            <Icon name="spark" size="sm" /> Ask what I am watching
          </Button>
        </div>
      ) : (
        <>
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
              Every item is prepared, never sent on its own. You hold the authority — Approve,
              Adjust, or Decline. The strongest, ready-to-act items come first.
              {source === 'fallback' ? ' Showing the last-known feed.' : ''}
            </p>
            {queue.map((r) => (
              <RecommendationItem key={r.id} rec={r} onActioned={actioned} />
            ))}
          </section>
        </>
      )}
    </SurfaceShell>
  );
}
