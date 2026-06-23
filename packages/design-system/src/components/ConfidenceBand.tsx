import { forwardRef, type HTMLAttributes } from 'react';
import { cx } from './cx';
import type { Confidence } from '../types';

export interface ConfidenceBandProps extends HTMLAttributes<HTMLSpanElement> {
  /** The verification confidence level — the generate-and-verify gate, surfaced. */
  level: Confidence;
  /**
   * Override the label text. Defaults to a plain-language phrase. Learners
   * never see raw scores — only "high / building / needs review" style copy.
   */
  label?: string;
}

const DEFAULT_LABEL: Record<Confidence, string> = {
  high: 'High confidence',
  middle: 'Building confidence',
  low: 'Needs review',
};

/**
 * Surfaces the confidence gate from generate-and-verify as a small band with a
 * three-bar meter. high / middle / low map to success / warning / danger
 * tints. Plain language only — never a numeric score.
 */
export const ConfidenceBand = forwardRef<HTMLSpanElement, ConfidenceBandProps>(
  function ConfidenceBand({ level, label, className, ...rest }, ref) {
    const text = label ?? DEFAULT_LABEL[level];
    return (
      <span
        ref={ref}
        className={cx('confidence', level, className)}
        title={text}
        {...rest}
      >
        <span className="bars" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        {text}
      </span>
    );
  },
);
