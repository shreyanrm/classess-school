'use client';

/* ============================================================================
   lib/useVidya.ts — the ONE Vidya send path, shared by the home and the dock.

   Both VidyaHome and VidyaDock drive the same orchestrator: post the
   conversation + role to vidyaChat(), render a single inline spec, follow a
   navigate action with next/navigation, apply the SPEAK-AND-SHOW visual actions
   (highlight / annotate / self-assembling steps), and fall back to the offline
   responder ONLY when the route degrades. Factoring this into a hook keeps the
   home and the docked panel on one path — never two divergent Vidya behaviours,
   and the VOICE path applies the exact same actions as the typed path.
   ============================================================================ */

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { respond, messageId } from '@/app/_components/respond';
import type { ChatMessage } from '@/app/_components/MessageThread';
import { useRole } from './RoleContext';
import {
  vidyaChat,
  specToInline,
  type VidyaTurn,
  type VidyaAction,
  type HighlightRegion,
  type StepsCardSpec,
} from './vidya';

/** A live highlight directive the orb spotlights on the page. */
export interface ActiveHighlight {
  region: HighlightRegion;
  label?: string;
}

/** A live margin note the orb pins near a region. */
export interface ActiveAnnotation {
  region: HighlightRegion;
  note: string;
}

export interface UseVidyaResult {
  messages: ChatMessage[];
  thinking: boolean;
  send: (text: string) => Promise<void>;
  /** Append a Vidya line directly (e.g. a spoken voice reply). */
  appendVidya: (text: string) => void;
  /**
   * Apply a spoken Vidya turn from the voice route: render its text + a single
   * inline spec, follow a navigate action, AND apply the speak-and-show visuals
   * — the SAME handling as text, so voice and chat behave identically. The
   * permission ladder is enforced server side (a consequential action only
   * prepares), so navigate here is safe.
   */
  applyVoiceTurn: (text: string, actions: VidyaAction[]) => void;
  /** The active highlight (one at a time), or null. Visual only. */
  highlight: ActiveHighlight | null;
  /** The active margin annotation, or null. Visual only. */
  annotation: ActiveAnnotation | null;
  /** The active self-assembling derivation, or null. */
  steps: StepsCardSpec | null;
  /** Clear the current speak-and-show visuals (e.g. on close / new turn). */
  clearVisuals: () => void;
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
  const [highlight, setHighlight] = useState<ActiveHighlight | null>(null);
  const [annotation, setAnnotation] = useState<ActiveAnnotation | null>(null);
  const [steps, setSteps] = useState<StepsCardSpec | null>(null);

  const clearVisuals = useCallback(() => {
    setHighlight(null);
    setAnnotation(null);
    setSteps(null);
  }, []);

  // The offline fallback — used ONLY when the orchestrator degrades. Typing must
  // always work, so this never throws and always lands a calm reply.
  const fallback = useCallback((text: string) => {
    const reply = respond(text);
    setMessages((prev) => [
      ...prev,
      { id: messageId(), role: 'vidya', text: reply.text, inline: reply.inline },
    ]);
  }, []);

  // Render a Vidya turn (text + a single inline render spec), follow a navigate
  // action, and apply the speak-and-show visuals. The ONE place actions are
  // applied, so text and voice share identical behaviour. Used by both send()
  // and applyVoiceTurn().
  const applyTurn = useCallback(
    (text: string, actions: VidyaAction[], emptyFallback: string) => {
      // A self-assembling derivation prefers the dedicated steps overlay; any
      // other render spec becomes the inline card in the thread.
      const stepsAction = actions.find(
        (a) => a.type === 'render' && a.spec.kind === 'steps',
      );
      const stepsSpec =
        stepsAction && stepsAction.type === 'render' && stepsAction.spec.kind === 'steps'
          ? stepsAction.spec
          : null;

      const renderAction = actions.find(
        (a) => a.type === 'render' && a.spec.kind !== 'steps',
      );
      const inline =
        renderAction && renderAction.type === 'render'
          ? specToInline(renderAction.spec) ?? undefined
          : undefined;

      const replyText =
        text.trim().length > 0
          ? text
          : inline || stepsSpec
            ? 'Here is what I found.'
            : emptyFallback;

      setMessages((prev) => [...prev, { id: messageId(), role: 'vidya', text: replyText, inline }]);

      // Speak-and-show: a fresh turn replaces the prior visuals.
      const highlightAction = actions.find((a) => a.type === 'highlight');
      setHighlight(
        highlightAction && highlightAction.type === 'highlight'
          ? { region: highlightAction.region, label: highlightAction.label }
          : null,
      );
      const annotateAction = actions.find((a) => a.type === 'annotate');
      setAnnotation(
        annotateAction && annotateAction.type === 'annotate'
          ? { region: annotateAction.region, note: annotateAction.note }
          : null,
      );
      setSteps(stepsSpec);

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
    clearVisuals();
  }, [clearVisuals]);

  return {
    messages,
    thinking,
    send,
    appendVidya,
    applyVoiceTurn,
    highlight,
    annotation,
    steps,
    clearVisuals,
    reset,
  };
}
