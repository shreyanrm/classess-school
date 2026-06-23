import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';

export type TagTone = 'neutral' | 'success' | 'danger' | 'warning' | 'info' | 'molten';

export interface TagProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: TagTone;
  /** Show a leading status dot. */
  dot?: boolean;
  children?: ReactNode;
}

const TONE_CLASS: Record<TagTone, string> = {
  neutral: '',
  success: 'tag-success',
  danger: 'tag-danger',
  warning: 'tag-warning',
  info: 'tag-info',
  molten: 'tag-molten',
};

/** A sharp, mono, uppercase tag. Tone carries meaning, never decoration. */
export const Tag = forwardRef<HTMLSpanElement, TagProps>(function Tag(
  { tone = 'neutral', dot, className, children, ...rest },
  ref,
) {
  return (
    <span ref={ref} className={cx('tag', TONE_CLASS[tone], className)} {...rest}>
      {dot ? <span className="dot" /> : null}
      {children}
    </span>
  );
});
