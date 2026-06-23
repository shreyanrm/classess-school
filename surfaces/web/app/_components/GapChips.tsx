'use client';

import { Tag } from '@classess/design-system';
import type { GapResult } from '@/lib/engine';
import { gapLabel } from '@/lib/engine';

/**
 * Gap chips — the ten-type classification, rendered as tags. Confirmed gaps are
 * solid (info tone); unconfirmed signals read as neutral "signal" chips, because
 * a learner judgment is NEVER confirmed from a single bad score. Each chip
 * carries its plain-language rationale on hover for explainability.
 */
export interface GapChipsProps {
  gaps: GapResult[];
  /** When empty, show this calm line instead of nothing. */
  emptyLabel?: string;
}

export function GapChips({ gaps, emptyLabel = 'No gaps detected yet' }: GapChipsProps) {
  if (gaps.length === 0) {
    return <span className="caption quiet">{emptyLabel}</span>;
  }
  return (
    <div className="chips">
      {gaps.map((g) => (
        <Tag
          key={g.evidence.gapType}
          tone={g.evidence.confirmed ? 'info' : 'neutral'}
          title={g.evidence.rationale}
        >
          {gapLabel(g.evidence.gapType)}
          {g.evidence.confirmed ? '' : ' signal'}
        </Tag>
      ))}
    </div>
  );
}
