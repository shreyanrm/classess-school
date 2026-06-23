import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';
import { Icon } from './Icon';

export interface SuggestionChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Show a leading spark glyph (the quiet "AI suggestion" cue). */
  spark?: boolean;
  children?: ReactNode;
}

/**
 * A quiet, tappable prompt starter for the composer. Hairline, sharp, calm.
 * The optional spark uses the ultramarine signature as a small affordance.
 */
export const SuggestionChip = forwardRef<HTMLButtonElement, SuggestionChipProps>(
  function SuggestionChip({ spark, className, type = 'button', children, ...rest }, ref) {
    return (
      <button ref={ref} type={type} className={cx('suggestion-chip', className)} {...rest}>
        {spark ? <Icon name="spark" size="sm" /> : null}
        {children}
      </button>
    );
  },
);
