'use client';

import { type ReactNode } from 'react';
import { Cell, useCountUp } from '@classess/design-system';

/* ============================================================================
   StatCell — one count-up stat in the page-head matrix grid. The label, the
   big sans-tabular value that counts up on view, an optional unit, and a mono
   delta with a state hue (up = success, down = danger, flat = quiet). Honours
   reduced-motion (the count jumps to its end value). Sits inside a <Matrix>.
   ============================================================================ */

export interface StatCellProps {
  label: ReactNode;
  /** The numeric value to count up to. */
  value: number;
  /** A trailing unit printed right after the value (e.g. "%"). */
  unit?: string;
  /** A mono delta caption beneath the value. */
  delta?: ReactNode;
  /** The delta's tone — drives its hue. */
  tone?: 'up' | 'down' | 'flat';
}

export function StatCell({ label, value, unit, delta, tone = 'flat' }: StatCellProps) {
  const { value: shown, ref } = useCountUp(value);
  return (
    <Cell>
      <div className="cell-label">{label}</div>
      <div className="cell-value">
        <span ref={ref}>{shown}</span>
        {unit ? unit : null}
      </div>
      {delta ? <div className={`cell-delta ${tone}`}>{delta}</div> : null}
    </Cell>
  );
}
