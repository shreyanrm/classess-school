'use client';

/* ============================================================================
   app/proactive/ProactiveFeed.tsx — the approval queue, recomposed to the bar.

   The one manage-by-exception surface for everything Vidya has prepared and is
   waiting on a human decision. A count-up stat matrix opens it; the queue rides
   on .cols (1fr + 320px): the recommendation cards triage into "ready to act"
   and "worth a closer look" on the left, and a right aside carries the dark
   ignite-card (the crystallize moment), how-the-ladder-works, and a handnote.

   READS the feed gateway-first (lib/useProactive -> /api/proactive -> the spine,
   the local list on degrade), and renders the real RecommendationItem control:
   consequential items raise the ApprovalControl, reversible items execute with
   an undo, and a resolved gap plays the CrystallizeNode moment.

   Ships all FIVE designed states — empty / loading / error / offline /
   permission-denied — each with a real CTA. v4.1 tokens only; no shadow.
   ============================================================================ */

import { SurfaceShell } from '../_components/SurfaceShell';
import { RecommendationItem } from '../_components/RecommendationItem';
import { ReadStates } from '../_components/ReadStates';
import { Button, Icon, Tag } from '@classess/design-system';
import { Panel, FlagRow, HandnotePanel, SecHead, type FlagModel } from '../_components/StudentComposed';
import { StatMatrix } from '../_components/StudentComposed';
import { openVidya } from '../_components/VidyaOrb';
import { useProactive } from '@/lib/useProactive';

export function ProactiveFeed() {
  const { phase, recommendations, source, refresh, actioned } = useProactive();

  // Triage: highest-confidence, ready-to-act items first.
  const order: Record<string, number> = { high: 0, middle: 1, low: 2 };
  const queue = [...recommendations].sort(
    (a, b) => (order[a.confidence] ?? 3) - (order[b.confidence] ?? 3),
  );
  const ready = queue.filter((r) => r.confidence === 'high');
  const watch = queue.filter((r) => r.confidence !== 'high');
  const consequential = queue.filter((r) => r.consequential).length;

  // The crystallize moment for the aside — a recommendation that resolves a gap
  // into independent mastery (its plain-language line).
  const crystallizing = queue.find((r) => r.crystallizes);

  const flags: FlagModel[] = watch.slice(0, 3).map((r) => ({
    icon: r.consequential ? 'target' : 'spark',
    title: r.title,
    caption: r.evidenceSummary,
  }));

  const aside = (
    <>
      <div className="ignite-card reveal reveal-3">
        <div className="row-between" style={{ marginBottom: 14 }}>
          <span className="overline">{crystallizing ? 'On approve' : 'The principle'}</span>
          <Icon name="flame" size="sm" style={{ color: 'var(--accent)' }} />
        </div>
        <div className="who">
          {crystallizing ? crystallizing.crystallizes : 'Nothing fires on its own'}
        </div>
        <p className="body-sm" style={{ opacity: 0.82, marginTop: 8 }}>
          {crystallizing
            ? 'Approving this closes a support-dependency gap into independent mastery — the crystallize moment plays once it commits.'
            : 'Every item here is prepared and held. You hold the authority — Approve, Adjust, or Decline. Vidya never acts unasked.'}
        </p>
      </div>

      <Panel title="Worth a closer look" meta={<Tag tone="warning" dot>{String(watch.length)}</Tag>}>
        <p className="caption" style={{ marginBottom: 'var(--space-3)' }}>
          Lower-confidence items — review the evidence before acting.
        </p>
        {flags.length > 0 ? (
          flags.map((f, i) => <FlagRow key={i} flag={f} />)
        ) : (
          <p className="caption muted">Nothing lower-confidence is waiting — the queue is all high-confidence.</p>
        )}
      </Panel>

      <Panel title="The permission ladder" meta={<span className="overline">how it works</span>}>
        <div className="flag">
          <div className="flag-ic"><Icon name="target" size="sm" /></div>
          <div>
            <div className="body-sm" style={{ fontWeight: 500 }}>Consequential</div>
            <p className="caption">Send, publish, grade — raises the approval control, commits only on approve.</p>
          </div>
        </div>
        <div className="flag">
          <div className="flag-ic"><Icon name="check" size="sm" /></div>
          <div>
            <div className="body-sm" style={{ fontWeight: 500 }}>Reversible</div>
            <p className="caption">Safe, undoable steps execute with an undo — nothing irreversible without you.</p>
          </div>
        </div>
      </Panel>

      <HandnotePanel>approve the high-confidence ones first — the evidence is already strong</HandnotePanel>
    </>
  );

  return (
    <SurfaceShell
      eyebrow="Class 10-B"
      title="Approval queue"
      meta={[
        { value: queue.length, label: 'awaiting your decision' },
        { value: ready.length, label: 'ready to act' },
        { value: consequential, label: 'need explicit approval' },
      ]}
      tabs={[
        { label: 'Queue', active: true },
        { label: 'Class insights', href: '/insights' },
        { label: 'Live loop', href: '/loop' },
      ]}
      aside={phase === 'ready' && queue.length > 0 ? aside : undefined}
      dockIntro="This is everything I have prepared and am waiting on you to decide. Nothing runs until you approve it. Ask me to adjust or explain any item."
      dockChips={['Explain the fractions recommendation', 'Adjust the due dates', 'Approve the high-confidence items']}
    >
      {phase !== 'ready' ? (
        <ReadStates phase={phase} onRetry={refresh} />
      ) : queue.length === 0 ? (
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
          <StatMatrix
            columns={3}
            stats={[
              { label: 'Awaiting your decision', value: queue.length, delta: 'prepared, never sent', deltaDir: 'flat' },
              { label: 'Ready to act', value: ready.length, delta: 'corroborated evidence', deltaDir: 'up' },
              { label: 'Worth a closer look', value: watch.length, delta: 'review before acting', deltaDir: 'down' },
            ]}
          />

          {ready.length > 0 ? (
            <section className="stack reveal reveal-3" style={{ marginTop: 'var(--space-6)' }}>
              <SecHead title="Ready to act" meta={<Tag tone="success" dot>{String(ready.length)}</Tag>} />
              <p className="caption quiet">
                High-confidence, corroborated evidence. Prepared, never sent on their own — you hold
                the authority.
                {source === 'fallback' ? ' Showing the last-known feed.' : ''}
              </p>
              {ready.map((r) => (
                <RecommendationItem key={r.id} rec={r} onActioned={actioned} />
              ))}
            </section>
          ) : null}

          {watch.length > 0 ? (
            <section className="stack reveal reveal-4" style={{ marginTop: 'var(--space-6)' }}>
              <SecHead title="Worth a closer look" meta={<Tag tone="warning" dot>{String(watch.length)}</Tag>} />
              <p className="caption quiet">
                Lower confidence — review the evidence before acting. Adjust or decline if it does not fit.
              </p>
              {watch.map((r) => (
                <RecommendationItem key={r.id} rec={r} onActioned={actioned} />
              ))}
            </section>
          ) : null}
        </>
      )}
    </SurfaceShell>
  );
}
