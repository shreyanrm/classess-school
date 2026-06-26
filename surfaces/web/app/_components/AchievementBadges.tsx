'use client';

/* ============================================================================
   AchievementBadges — honest, motivating recognition. NEVER raw-score shaming.

   Every badge is earned from real EVIDENCE the learning engine already holds —
   an unaided demonstration, a streak of days returning, a faded topic brought
   back — not from a mark or a leaderboard rank. A badge a learner has not earned
   is shown as a calm, encouraging "in reach" tile (what unlocks it), never a
   locked padlock that reads as failure.

   v3 GRAMMAR:
     · Plain language, no percentages, no comparison to other students.
     · Earned vs in-reach — both phrased as encouragement.
     · Hairline + tonal + frost, NEVER a shadow. The earned glow is a tonal tint
       (the subject/accent), not a drop shadow.
     · Reduced-motion: the earned tiles use the shared reveal utility (snaps).
   ============================================================================ */

import { Icon, type IconName } from '@classess/design-system';

export interface BadgeModel {
  id: string;
  name: string;
  /** Plain description of what it recognises. */
  blurb: string;
  icon: IconName;
  /** True when the evidence to earn it is present. */
  earned: boolean;
  /** When earned: the plain evidence line. When not: what would unlock it. */
  note: string;
}

/**
 * Derive the badge set from calm evidence facts (counts already read from the
 * engine — no marks). Keeping derivation here means /student and /student/practice
 * read ONE coherent set rather than hardcoding tiles per page.
 */
export interface BadgeFacts {
  /** Topics with a verified unaided demonstration. */
  independentTopics: number;
  /** Consecutive days the learner returned to practise. */
  streakDays: number;
  /** Faded topics brought back with a review. */
  topicsRevived: number;
  /** Pieces of the learner's own work observed. */
  evidencePieces: number;
}

export function deriveBadges(f: BadgeFacts): BadgeModel[] {
  return [
    {
      id: 'quick-learner',
      name: 'Quick Learner',
      blurb: 'Showed a topic unaided soon after meeting it.',
      icon: 'spark',
      earned: f.independentTopics >= 1,
      note:
        f.independentTopics >= 1
          ? `${f.independentTopics} ${f.independentTopics === 1 ? 'topic' : 'topics'} you can already do on your own.`
          : 'One unaided demonstration lights this — you are close.',
    },
    {
      id: 'streak-master',
      name: 'Streak Master',
      blurb: 'Came back to learn several days running.',
      icon: 'flame',
      earned: f.streakDays >= 3,
      note:
        f.streakDays >= 3
          ? `${f.streakDays} days in a row — turning up is most of it.`
          : `${f.streakDays} of 3 days. Returning tomorrow keeps it going — no pressure if you miss one.`,
    },
    {
      id: 'memory-keeper',
      name: 'Memory Keeper',
      blurb: 'Brought back a topic that was starting to fade.',
      icon: 'clock',
      earned: f.topicsRevived >= 1,
      note:
        f.topicsRevived >= 1
          ? `${f.topicsRevived} faded ${f.topicsRevived === 1 ? 'topic' : 'topics'} kept fresh by reviewing in time.`
          : 'Review a topic the moment it starts to fade to earn this.',
    },
    {
      id: 'evidence-builder',
      name: 'Evidence Builder',
      blurb: 'Built up a real record of your own work.',
      icon: 'chart',
      earned: f.evidencePieces >= 8,
      note:
        f.evidencePieces >= 8
          ? `${f.evidencePieces} pieces of your own work — this is your portfolio growing.`
          : `${f.evidencePieces} pieces so far. Every attempt adds to it.`,
    },
  ];
}

export function AchievementBadges({ badges }: { badges: BadgeModel[] }) {
  const earned = badges.filter((b) => b.earned).length;
  return (
    <div className="badge-board">
      <div className="row-between" style={{ marginBottom: 'var(--space-3)' }}>
        <p className="overline" style={{ margin: 0 }}>
          Your badges
        </p>
        <span className="caption muted">
          {earned} earned · {badges.length - earned} in reach
        </span>
      </div>
      <div className="badge-grid">
        {badges.map((b, i) => (
          <div
            key={b.id}
            className={`badge-tile reveal reveal-${Math.min(i + 1, 8)}${b.earned ? ' earned' : ' in-reach'}`}
          >
            <span className="badge-ic" aria-hidden="true">
              <Icon name={b.icon} size="md" />
            </span>
            <div className="badge-body">
              <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
                <span className="body-sm" style={{ fontWeight: 500 }}>
                  {b.name}
                </span>
                {b.earned ? (
                  <span className="badge-earned-chip">
                    <Icon name="check" size="sm" /> Earned
                  </span>
                ) : (
                  <span className="badge-reach-chip">In reach</span>
                )}
              </div>
              <p className="caption" style={{ margin: '2px 0 0' }}>
                {b.note}
              </p>
            </div>
          </div>
        ))}
      </div>
      <p className="caption quiet" style={{ marginTop: 'var(--space-3)' }}>
        Badges come from your own evidence — never a mark, never a rank against anyone else.
      </p>
    </div>
  );
}
