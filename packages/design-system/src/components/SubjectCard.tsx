import { forwardRef, type CSSProperties, type HTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';
import type { SubjectAccent } from '../types';

export interface SubjectCardProps extends HTMLAttributes<HTMLDivElement> {
  /** Subject name shown in the colour band. */
  name: string;
  /** Optional short code shown right of the name (mono). */
  code?: string;
  /**
   * The subject identity accent — one vivid per surface. Ultramarine is NOT
   * available here: the signature is reserved for brand + ignite. Provide a
   * SubjectAccent token name; the band paints var(--<accent>) with the
   * matching var(--<accent>-ink) text.
   */
  accent: SubjectAccent;
  children?: ReactNode;
}

// The -ink token name differs by hue (hot-red -> hot-red-ink, etc.).
function inkVar(accent: SubjectAccent): string {
  // Special-cased token names whose -ink suffix is not a simple "<name>-ink".
  const map: Partial<Record<SubjectAccent, string>> = {
    'hot-red': '--hot-red-ink',
  };
  return map[accent] ?? `--${accent}-ink`;
}

/**
 * The colour-on-top subject card. A vivid band carries the subject identity;
 * the body stays on the calm surface. Set the accent via the `accent` prop —
 * exactly one vivid per surface, and never the ultramarine signature.
 */
export const SubjectCard = forwardRef<HTMLDivElement, SubjectCardProps>(function SubjectCard(
  { name, code, accent, className, style, children, ...rest },
  ref,
) {
  const vars = {
    '--subject': `var(--${accent})`,
    '--subject-ink': `var(${inkVar(accent)})`,
    ...style,
  } as CSSProperties;

  return (
    <div ref={ref} className={cx('subject-card', className)} style={vars} {...rest}>
      <div className="band">
        <span className="name">{name}</span>
        {code ? <span className="code">{code}</span> : null}
      </div>
      <div className="body">{children}</div>
    </div>
  );
});
