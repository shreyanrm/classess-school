'use client';

import { Icon } from '@classess/design-system';
import { InlineResult, type InlineResultData } from './InlineResult';
import { VidyaSurface } from './VidyaSurface';
import type { SurfaceSpec, VidyaPath } from '@/lib/vidya';
import { pathSummary } from '@/lib/vidya';

export type ChatMessage =
  | { id: string; role: 'user'; text: string }
  | {
      id: string;
      role: 'vidya';
      text: string;
      inline?: InlineResultData;
      /**
       * An OPERABLE generative surface (quiz-builder / class-view / plan-board /
       * report-card) Vidya composed for this turn. When present it renders as a
       * real, interactive panel inline in the thread — not a flat card.
       */
      surface?: SurfaceSpec;
      /**
       * Which of the five generative-UI paths (spec 16.2) this turn took. Shown
       * as a quiet, plain-language line so the taxonomy is legible: answered
       * inline, composed a view, prepared for approval, routed + docked, or
       * routed + guided. Omitted for a plain answer with nothing to name.
       */
      path?: VidyaPath;
    };

export interface MessageThreadProps {
  messages: ChatMessage[];
  /** True while Vidya is composing the next turn — drives the loading state. */
  thinking?: boolean;
  /** Follow a consequential surface's review route (router.push). */
  onOpenHref?: (href: string) => void;
}

/**
 * The conversation thread. User turns are quiet right-aligned bubbles; Vidya
 * turns are plain text that may carry one inline generative result. A small task
 * renders inline here; a big task surfaces an "open in its page" control on the
 * inline result, routing to a dedicated workspace.
 */
export function MessageThread({ messages, thinking, onOpenHref }: MessageThreadProps) {
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
            {/* The quiet path line (spec 16.2): names which of the five paths
                this turn took, so the taxonomy is legible. Omitted for a plain
                inline answer, which needs no label. */}
            {m.path && m.path !== 'answer' ? (
              <div className="vidya-path overline muted" data-path={m.path}>
                {pathSummary(m.path)}
              </div>
            ) : null}
            {m.surface ? <VidyaSurface spec={m.surface} onOpenHref={onOpenHref} /> : null}
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
