'use client';

/* ============================================================================
   lib/useVidya.ts — the ONE Vidya send path, shared by the home and the dock.

   Both VidyaHome and VidyaDock drive the same orchestrator: post the
   conversation + role to vidyaChat(), render a single inline spec, follow a
   navigate action with next/navigation, and fall back to the offline responder
   ONLY when the route degrades. Factoring this into a hook keeps the home and
   the docked panel on one path — never two divergent Vidya behaviours.
   ============================================================================ */

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { respond, messageId } from '@/app/_components/respond';
import type { ChatMessage } from '@/app/_components/MessageThread';
import { useRole } from './RoleContext';
import { vidyaChat, specToInline, type VidyaTurn, type VidyaAction } from './vidya';

export interface UseVidyaResult {
  messages: ChatMessage[];
  thinking: boolean;
  send: (text: string) => Promise<void>;
  /** Append a Vidya line directly (e.g. a spoken voice reply). */
  appendVidya: (text: string) => void;
  /**
   * Apply a spoken Vidya turn from the voice route: render its text + a single
   * inline spec, and follow a navigate action — the SAME handling as text, so
   * voice and chat behave identically. The permission ladder is enforced server
   * side (a consequential action only prepares), so navigate here is safe.
   */
  applyVoiceTurn: (text: string, actions: VidyaAction[]) => void;
  reset: () => void;
}

/**
 * The shared Vidya conversation engine. `initial` seeds the thread (the dock's
 * intro line); the home passes nothing. Returns the live thread plus the single
 * send path both surfaces use.
 */
export function useVidya(initial: ChatMessage[] = []): UseVidyaResult {
  const router = useRouter();
  const { role } = useRole();
  const [messages, setMessages] = useState<ChatMessage[]>(initial);
  const [thinking, setThinking] = useState(false);

  // The offline fallback — used ONLY when the orchestrator degrades. Typing must
  // always work, so this never throws and always lands a calm reply.
  const fallback = useCallback((text: string) => {
    const reply = respond(text);
    setMessages((prev) => [
      ...prev,
      { id: messageId(), role: 'vidya', text: reply.text, inline: reply.inline },
    ]);
  }, []);

  // Render a Vidya turn (text + a single inline render spec) and follow a
  // navigate action. The ONE place actions are applied, so text and voice share
  // identical behaviour. Used by both send() and applyVoiceTurn().
  const applyTurn = useCallback(
    (text: string, actions: VidyaAction[], emptyFallback: string) => {
      const renderAction = actions.find((a) => a.type === 'render');
      const inline =
        renderAction && renderAction.type === 'render'
          ? specToInline(renderAction.spec) ?? undefined
          : undefined;

      const replyText =
        text.trim().length > 0 ? text : inline ? 'Here is what I found.' : emptyFallback;

      setMessages((prev) => [...prev, { id: messageId(), role: 'vidya', text: replyText, inline }]);

      const navAction = actions.find((a) => a.type === 'navigate');
      if (navAction && navAction.type === 'navigate') router.push(navAction.target);
    },
    [router],
  );

  const send = useCallback(
    async (text: string) => {
      setMessages((prev) => {
        // Build the conversation the orchestrator sees, including this new turn.
        const history: VidyaTurn[] = prev.map((m) => ({
          role: m.role === 'user' ? 'user' : 'vidya',
          text: m.text,
        }));
        history.push({ role: 'user', text });
        // Fire the orchestrator with the freshest history.
        void run(history);
        return [...prev, { id: messageId(), role: 'user', text }];
      });

      async function run(history: VidyaTurn[]) {
        setThinking(true);
        const result = await vidyaChat({ messages: history, role });
        setThinking(false);

        // Degraded (no key / provider failure / network): fall back locally.
        if (result.degraded) {
          fallback(text);
          return;
        }

        applyTurn(
          result.text,
          result.actions,
          'I can help you read where the class is, prepare a check, or take you to the right page.',
        );
      }
    },
    [applyTurn, fallback, role],
  );

  const appendVidya = useCallback((text: string) => {
    setMessages((prev) => [...prev, { id: messageId(), role: 'vidya', text }]);
  }, []);

  const applyVoiceTurn = useCallback(
    (text: string, actions: VidyaAction[]) => {
      applyTurn(text, actions, 'I heard you. Tell me where you would like to start.');
    },
    [applyTurn],
  );

  const reset = useCallback(() => {
    setMessages([]);
    setThinking(false);
  }, []);

  return { messages, thinking, send, appendVidya, applyVoiceTurn, reset };
}
