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
  classifyPath,
  type VidyaTurn,
  type VidyaAction,
  type HighlightRegion,
  type StepsCardSpec,
  type CanvasCardSpec,
  type SurfaceSpec,
  type VidyaAttachment,
} from './vidya';
import { readStore } from './store';
import {
  recallMemory,
  rememberTurn,
  rememberSalient,
  persistMemory,
  memoryInstruction,
} from './vidyaMemory';

/** A substantial derivation (this many verified steps or more) earns the canvas
 *  — a short result stays small inline in the orb. */
const CANVAS_STEPS_THRESHOLD = 3;

/** A calm, plain-language bubble for a turn that is just an attachment (no text). */
function attachmentSummary(attachments: VidyaAttachment[]): string {
  const kind = attachments[0]?.kind ?? 'document';
  const noun = kind === 'image' ? 'an image' : kind === 'screen' ? 'my screen' : 'a document';
  return attachments.length > 1 ? `Shared ${attachments.length} attachments` : `Shared ${noun}`;
}

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
  /**
   * Send a typed turn, optionally with MULTIMODAL attachments (image / document /
   * screen capture) bound to this turn. The orchestrator understands them and
   * degrades cleanly when no multimodal key is configured.
   */
  send: (text: string, attachments?: VidyaAttachment[]) => Promise<void>;
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
  /** The active self-assembling derivation in the orb, or null. */
  steps: StepsCardSpec | null;
  /** The active floating-canvas content Vidya has summoned, or null. */
  canvas: CanvasCardSpec | null;
  /** Dismiss the floating canvas (without clearing the conversation). */
  closeCanvas: () => void;
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
  const [canvas, setCanvas] = useState<CanvasCardSpec | null>(null);

  const closeCanvas = useCallback(() => setCanvas(null), []);

  const clearVisuals = useCallback(() => {
    setHighlight(null);
    setAnnotation(null);
    setSteps(null);
    setCanvas(null);
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
      // A canvas action is the explicit "show it" — Vidya summoned the floating
      // canvas to draw / derive / sketch. It is honoured directly.
      const canvasAction = actions.find((a) => a.type === 'canvas');
      let canvasSpec: CanvasCardSpec | null =
        canvasAction && canvasAction.type === 'canvas' ? canvasAction.spec : null;

      // A self-assembling derivation prefers the dedicated steps overlay; any
      // other render spec becomes the inline card in the thread.
      const stepsAction = actions.find(
        (a) => a.type === 'render' && a.spec.kind === 'steps',
      );
      let stepsSpec =
        stepsAction && stepsAction.type === 'render' && stepsAction.spec.kind === 'steps'
          ? stepsAction.spec
          : null;

      // A SUBSTANTIAL derivation is promoted to the floating canvas (rendered
      // large, self-assembling). A short result stays small inline in the orb.
      if (!canvasSpec && stepsSpec && stepsSpec.steps.length >= CANVAS_STEPS_THRESHOLD) {
        canvasSpec = {
          kind: 'canvas',
          title: stepsSpec.title,
          content: { type: 'derivation', steps: stepsSpec.steps },
        };
        stepsSpec = null; // it lives on the canvas now, not the inline overlay
      }

      // An OPERABLE surface (quiz-builder / class-view / plan-board / report-card)
      // is rendered as a real interactive panel inline — not a flat card. It is
      // attached to the message so MessageThread mounts <VidyaSurface>.
      const surfaceAction = actions.find(
        (a) => a.type === 'render' && a.spec.kind === 'surface',
      );
      const surface: SurfaceSpec | undefined =
        surfaceAction && surfaceAction.type === 'render' && surfaceAction.spec.kind === 'surface'
          ? surfaceAction.spec.surface
          : undefined;

      // Any OTHER render spec (mastery / gaps / draft / recommendation / explain)
      // becomes the calm inline card. The surface and the steps are handled above.
      const renderAction = actions.find(
        (a) => a.type === 'render' && a.spec.kind !== 'steps' && a.spec.kind !== 'surface',
      );
      const inline =
        renderAction && renderAction.type === 'render'
          ? specToInline(renderAction.spec) ?? undefined
          : undefined;

      const replyText =
        text.trim().length > 0
          ? text
          : inline || surface || stepsSpec || canvasSpec
            ? 'Here is what I found.'
            : emptyFallback;

      // The 5-path classifier CONTRACT (spec 16.2): project this turn's actions
      // onto exactly one path. Pure + deterministic, so the home and the dock
      // describe the same turn identically. The thread shows a quiet path line.
      const path = classifyPath(actions);

      setMessages((prev) => [
        ...prev,
        { id: messageId(), role: 'vidya', text: replyText, inline, surface, path },
      ]);

      setCanvas(canvasSpec);

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
    async (text: string, attachments?: VidyaAttachment[]) => {
      setMessages((prev) => {
        // Build the conversation the orchestrator sees, including this new turn.
        const history: VidyaTurn[] = prev.map((m) => ({
          role: m.role === 'user' ? 'user' : 'vidya',
          text: m.text,
        }));
        history.push({ role: 'user', text });
        // Fire the orchestrator with the freshest history.
        void run(history);
        // A turn with an attachment but no typed text still shows a quiet bubble.
        const userText =
          text.trim().length > 0
            ? text
            : attachments && attachments.length > 0
              ? attachmentSummary(attachments)
              : text;
        return [...prev, { id: messageId(), role: 'user', text: userText }];
      });

      async function run(history: VidyaTurn[]) {
        setThinking(true);

        // PERSISTENT PER-USER MEMORY (web-native, PII-free, consent-gated): recall
        // what Vidya already knows about this opaque account and distil it into a
        // short note that conditions the orchestrator across sessions. With consent
        // off, recall is empty and nothing is remembered.
        const store = readStore();
        const accountId = store.account?.id ?? '';
        const consent = store.consent?.personalization === true;
        const memory = recallMemory(accountId, consent);
        const memoryNote = memoryInstruction(memory);

        const result = await vidyaChat({
          messages: history,
          role,
          memoryNote,
          accountId: accountId || undefined,
          memoryConsent: consent,
          attachments: attachments && attachments.length > 0 ? attachments : undefined,
        });
        setThinking(false);

        // Degraded (no key / provider failure / network): fall back locally.
        if (result.degraded) {
          fallback(text);
          return;
        }

        // Remember this exchange for next time: the bounded thread + the salient
        // facts (the topic of the turn, the role's recurring intent). Persisted
        // only when consent is on. PII is redacted inside the memory slice.
        if (consent && accountId) {
          let next = rememberTurn(memory, 'user', text);
          if (result.text) next = rememberTurn(next, 'vidya', result.text);
          next = rememberSalient(next, { lastIntent: text.slice(0, 80) });
          persistMemory(next, consent);
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
    canvas,
    closeCanvas,
    clearVisuals,
    reset,
  };
}
