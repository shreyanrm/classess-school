import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'accent' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /**
   * primary  = ink (monochrome, the default action)
   * secondary= hairline outline
   * ghost    = quiet, text-only
   * accent   = ultramarine signature — the ONE hero action per surface
   * danger   = destructive
   */
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Full-width block button. */
  block?: boolean;
  /** Square icon-only button. Provide an aria-label for accessibility. */
  iconOnly?: boolean;
  children?: ReactNode;
}

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  accent: 'btn-accent',
  danger: 'btn-danger',
};

const SIZE_CLASS: Record<ButtonSize, string> = {
  sm: 'btn-sm',
  md: '',
  lg: 'btn-lg',
};

/**
 * The button. Token-driven, sharp-cornered, no drop shadow. Use `accent`
 * sparingly — it is the single ultramarine hero action on a surface.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', block, iconOnly, className, type = 'button', children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(
        'btn',
        VARIANT_CLASS[variant],
        SIZE_CLASS[size],
        block && 'btn-block',
        iconOnly && 'btn-icon',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
});
