'use client';

import { useState } from 'react';
import { Composer, Icon, SuggestionChip } from '@classess/design-system';
import { MessageThread, type ChatMessage } from './MessageThread';
import { useVidya } from '@/lib/useVidya';

export interface VidyaDockProps {
  /** Quiet starter chips shaped to the page. */
  chips?: string[];
  /** Opening line from Vidya for this page. */
  intro?: string;
}

/**
 * The docked, collapsible Vidya panel for destination pages. The conversation
 * keeps driving the page; it is never a dead end. Collapses to a slim spine so
 * the workspace can take the full width when wanted.
 */
export function VidyaDock({ chips = [], intro }: VidyaDockProps) {
  const [collapsed, setCollapsed] = useState(false);
  const initial: ChatMessage[] = intro ? [{ id: 'intro', role: 'vidya', text: intro }] : [];
  // The SAME orchestrator path the home uses — navigate + render actions, with
  // the offline responder only on degrade. One Vidya, never two behaviours.
  const { messages, thinking, send } = useVidya(initial);

  if (collapsed) {
    return (
      <aside className="vidya-dock collapsed" aria-label="Vidya">
        <div className="vidya-dock-head">
          <button
            type="button"
            className="rail-btn"
            aria-label="Expand Vidya"
            title="Expand Vidya"
            onClick={() => setCollapsed(false)}
          >
            <Icon name="spark" size="md" />
          </button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="vidya-dock" aria-label="Vidya">
      <div className="vidya-dock-head">
        <span className="vidya-dock-title row" style={{ gap: 'var(--space-2)' }}>
          <Icon name="spark" size="sm" />
          <span className="overline" style={{ margin: 0 }}>
            Vidya
          </span>
        </span>
        <button
          type="button"
          className="rail-btn"
          aria-label="Collapse Vidya"
          title="Collapse Vidya"
          onClick={() => setCollapsed(true)}
        >
          <Icon name="chevron-right" size="md" />
        </button>
      </div>

      <div className="vidya-dock-body">
        {messages.length > 0 ? (
          <MessageThread messages={messages} thinking={thinking} />
        ) : (
          <p className="muted body-sm">Ask about this page, or keep driving it from here.</p>
        )}
      </div>

      <div className="vidya-dock-foot">
        {chips.length > 0 ? (
          <div className="home-chips" style={{ justifyContent: 'flex-start', marginBottom: 'var(--space-3)' }}>
            {chips.map((c) => (
              <SuggestionChip key={c} spark onClick={() => send(c)}>
                {c}
              </SuggestionChip>
            ))}
          </div>
        ) : null}
        <Composer onSend={send} placeholder="Keep driving this page" />
      </div>
    </aside>
  );
}
