import { forwardRef, useId, type TextareaHTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
}

/** A multi-line text control. Same hairline + focus treatment as Input. */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, id, className, ...rest },
  ref,
) {
  const autoId = useId();
  const taId = id ?? autoId;
  const hasError = Boolean(error);
  const describedBy = error ? `${taId}-error` : hint ? `${taId}-hint` : undefined;

  const control = (
    <textarea
      ref={ref}
      id={taId}
      className={cx('textarea', hasError && 'is-error', className)}
      aria-invalid={hasError || undefined}
      aria-describedby={describedBy}
      {...rest}
    />
  );

  if (!label && !hint && !error) return control;

  return (
    <div className="field">
      {label ? (
        <label className="field-label" htmlFor={taId}>
          {label}
        </label>
      ) : null}
      {control}
      {error ? (
        <div id={`${taId}-error`} className="field-error">
          {error}
        </div>
      ) : hint ? (
        <div id={`${taId}-hint`} className="field-hint">
          {hint}
        </div>
      ) : null}
    </div>
  );
});
