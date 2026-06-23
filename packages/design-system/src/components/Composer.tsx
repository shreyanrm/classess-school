"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type KeyboardEvent,
  type TextareaHTMLAttributes,
} from 'react';
import { cx } from './cx';
import { Icon } from './Icon';

export interface ComposerProps
  extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'onChange' | 'value' | 'onSubmit'> {
  /** Controlled value. Omit for uncontrolled use. */
  value?: string;
  /** Change handler for controlled use. */
  onValueChange?: (value: string) => void;
  /**
   * Called with the trimmed text when the user sends (Enter without Shift, or
   * the send button). The composer clears itself afterward in uncontrolled
   * mode; in controlled mode, clear via onValueChange.
   */
  onSend?: (value: string) => void;
  /** Placeholder copy. Calm, no exclamation. */
  placeholder?: string;
  /** Disable input and sending. */
  disabled?: boolean;
  /** Accessible label for the send button. Default "Send message". */
  sendLabel?: string;
}

/**
 * A calm chat composer: an auto-growing textarea with a send button. Enter
 * sends, Shift+Enter inserts a newline. The send button is disabled while the
 * field is empty. Sharp, hairline, no drop shadow; the focus state lifts the
 * border, not a glow.
 */
export const Composer = forwardRef<HTMLTextAreaElement, ComposerProps>(function Composer(
  {
    value,
    onValueChange,
    onSend,
    placeholder = 'Ask anything, or describe where you are stuck',
    disabled,
    sendLabel = 'Send message',
    className,
    onKeyDown,
    rows = 1,
    ...rest
  },
  ref,
) {
  const innerRef = useRef<HTMLTextAreaElement>(null);
  useImperativeHandle(ref, () => innerRef.current as HTMLTextAreaElement, []);

  const isControlled = value !== undefined;
  const [internal, setInternal] = useState('');
  const text = isControlled ? value : internal;

  // Auto-grow the textarea to fit content, capped by the CSS max-height.
  const resize = useCallback(() => {
    const el = innerRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  useEffect(() => {
    resize();
  }, [text, resize]);

  const setText = useCallback(
    (next: string) => {
      if (isControlled) onValueChange?.(next);
      else setInternal(next);
    },
    [isControlled, onValueChange],
  );

  const send = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend?.(trimmed);
    if (!isControlled) setInternal('');
  }, [text, disabled, onSend, isControlled]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      onKeyDown?.(event);
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        send();
      }
    },
    [onKeyDown, send],
  );

  const canSend = text.trim().length > 0 && !disabled;

  return (
    <div className={cx('composer', className)}>
      <textarea
        ref={innerRef}
        className="composer-input"
        placeholder={placeholder}
        value={text}
        disabled={disabled}
        rows={rows}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        {...rest}
      />
      <button
        type="button"
        className="composer-send"
        onClick={send}
        disabled={!canSend}
        aria-label={sendLabel}
      >
        <Icon name="send" size="sm" />
      </button>
    </div>
  );
});