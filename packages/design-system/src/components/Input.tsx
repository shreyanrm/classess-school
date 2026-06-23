import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Optional field label rendered above the control. */
  label?: ReactNode;
  /** Quiet hint below the field. */
  hint?: ReactNode;
  /** Error message below the field; also flips the border to danger. */
  error?: ReactNode;
}

/**
 * A text input. Hairline-strong border, sharp corners, functional focus ring
 * (a token-tinted ring, not a drop shadow). Wraps in a labelled field when a
 * `label`, `hint`, or `error` is supplied.
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, id, className, ...rest },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hasError = Boolean(error);
  const describedBy = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;

  const control = (
    <input
      ref={ref}
      id={inputId}
      className={cx('input', hasError && 'is-error', className)}
      aria-invalid={hasError || undefined}
      aria-describedby={describedBy}
      {...rest}
    />
  );

  if (!label && !hint && !error) return control;

  return (
    <div className="field">
      {label ? (
        <label className="field-label" htmlFor={inputId}>
          {label}
        </label>
      ) : null}
      {control}
      {error ? (
        <div id={`${inputId}-error`} className="field-error">
          {error}
        </div>
      ) : hint ? (
        <div id={`${inputId}-hint`} className="field-hint">
          {hint}
        </div>
      ) : null}
    </div>
  );
});
