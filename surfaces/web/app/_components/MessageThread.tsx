'use client';

import { Icon } from '@classess/design-system';
import { InlineResult, type InlineResultData } from './InlineResult';

export type ChatMessage =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'vidya'; text: string; inline?: InlineResultData };

export interface MessageThreadProps {
  messages: ChatMessage[];
  /** True while Vidya is composing the next turn — drives the loading state. */
  thinking?: boolean;
}

/**
 * The conversation thread. User turns are quiet right-aligned bubbles; Vidya
 * turns are plain text that may carry one inline generative result. A small task
 * renders inline here; a big task surfaces an "open in its page" control on the
 * inline result, routing to a dedicated workspace.
 */
export function MessageThread({ messages, thinking }: MessageThreadProps) {
  return (
    <div className="thread" aria-live="polite">
      {messages.map((m) =>
        m.role === 'user' ? (
          <div className="msg msg-user" key={m.id}>
            <div className="bubble body-sm">{m.text}</div>
          </div>
        ) : (
          <div className="msg msg-vidya" key={m.id}>
            <div className="who">
              <Icon name="spark" size="sm" />
              Vidya
            </div>
            <div className="vidya-text body">{m.text}</div>
            {m.inline ? <InlineResult data={m.inline} /> : null}
          </div>
        ),
      )}

      {thinking ? (
        <div className="msg msg-vidya">
          <div className="who">
            <Icon name="spark" size="sm" />
            Vidya
          </div>
          <div className="skeleton skeleton-line" style={{ width: '60%' }} />
          <div className="skeleton skeleton-line" style={{ width: '85%' }} />
        </div>
      ) : null}
    </div>
  );
}
