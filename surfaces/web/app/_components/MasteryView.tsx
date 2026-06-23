'use client';

import { IgniteDot } from '@classess/design-system';
import type { MasteryRow } from '@/lib/mock';
import { BAND_PHRASE } from '@/lib/mock';

export interface MasteryViewProps {
  rows: MasteryRow[];
}

/**
 * The knowledge profile rendered as independent vs support-dependent, in plain
 * language — never a number or formula. The ignite signature marks the topics a
 * learner can now do on their own; everything else reads as "with support."
 */
export function MasteryView({ rows }: MasteryViewProps) {
  return (
    <div>
      {rows.map((row) => (
        <div className="mastery-row" key={row.topic}>
          <div>
            <div className="body" style={{ marginBottom: 2 }}>
              {row.topic}
            </div>
            <div className="caption muted">{row.note}</div>
          </div>
          <div className="mastery-band">
            {row.independent ? (
              <>
                <IgniteDot label="Now independent" />
                <span>{BAND_PHRASE[row.band]}</span>
              </>
            ) : (
              <span className="muted">{BAND_PHRASE[row.band]}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
