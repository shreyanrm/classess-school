'use client';

/* ============================================================================
   app/_components/VidyaOrb.tsx — Vidya as a floating, Siri-style assistant.

   A small circular orb (~56px) FIXED to the bottom-right of every page, on a
   calm v4 treatment: a subtle living gradient/pulse in the SURFACE accent
   (var(--accent)). Ultramarine (var(--signature)) is reserved for the brand mark
   and the rare mastery-ignite, NEVER the idle orb.

   Tapping the orb ACTIVATES Vidya: it expands into a COMPACT panel anchored at
   the bottom-right (~360px wide — not a full-height side dock, not a side chat
   space) with a short greeting, the live conversation thread (compact), a
   composer, and the voice mic (VoiceCapsule) prominent so a tap can go straight
   to speaking. A close control collapses it back to the orb.

   It uses the shared useVidya orchestrator, so the orb can chat, navigate
   (router.push — the orb stays mounted across pages because it lives in the root
   layout), render inline result cards, and obey the permission ladder. Offline,
   useVidya degrades to the local responder. prefers-reduced-motion is respected
   in CSS (no pulse, no slide).
   ============================================================================ */

import { useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Composer, Icon } from '@classess/design-system';
import { MessageThread } from './MessageThread';
import { VoiceCapsule, type VoiceCapsuleHandle } from './VoiceCapsule';
import { VoiceBloom } from './VoiceBloom';
import { VidyaSteps } from './VidyaSteps';
import { VidyaSpotlight } from './VidyaSpotlight';
import { VidyaCanvas } from './VidyaCanvas';
import { VidyaWatch } from './VidyaWatch';
import { VidyaAttach } from './VidyaAttach';
import type { VidyaAttachment } from '@/lib/vidya';
import { useVidya } from '@/lib/useVidya';
import { useRole } from '@/lib/RoleContext';
import { useAuth } from '@/lib/useAuth';
import { GREETING, type Role } from '@/lib/mock';

/** Routes where the orb should NOT appear — the auth + onboarding flows. */
const HIDDEN_PREFIXES = ['/sign-in', '/sign-up', '/forgot-password', '/reset-password', '/welcome'];

/**
 * The window event the role landing (and anywhere else) dispatches to open the
 * orb, optionally with a starter message. Keeps the orb the single Vidya entry
 * while letting a chip on the page route straight into the conversation.
 */
export const VIDYA_OPEN_EVENT = 'vidya:open';

/**
 * The window event the rail's "New conversation" button dispatches. The orb owns
 * the thread (via useVidya), so the rail cannot reset it directly — it asks the
 * orb to clear the thread and open a fresh one.
 */
export const VIDYA_NEW_EVENT = 'vidya:new';

/** Fire the open event with an optional starter prompt. Safe on the server. */
export function openVidya(prompt?: string): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(VIDYA_OPEN_EVENT, { detail: { prompt } }));
}

/** Start a fresh Vidya conversation (reset the thread + open the orb). */
export function newVidyaConversation(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(VIDYA_NEW_EVENT));
}

/** Derive the surface accent from the route so the orb matches the page hue. */
function surfaceFromPath(pathname: string, role: Role): Role {
  if (pathname.startsWith('/teacher')) return 'teacher';
  if (pathname.startsWith('/student')) return 'student';
  if (pathname.startsWith('/admin')) return 'admin';
  if (pathname.startsWith('/parent')) return 'parent';
  return role;
}

/** The role landings — conversation-first homes, NOT deep pages. Vidya FLOATS
 *  here (the calm orb). Everything else with real work is a deep page. */
const ROLE_HOMES = new Set(['/', '/student', '/teacher', '/admin', '/parent']);

/**
 * A DEEP PAGE is a full workspace that produces or holds persistent state — the
 * place a Path-4 route lands. On these, Vidya DOCKS (spec 16.4/17): the same orb
 * logic, presented as a collapsible docked panel that drives the current page
 * rather than floating over it. The home + role landings are not deep — Vidya
 * floats there. Any path below a role root (e.g. /student/progress) or a
 * top-level workspace counts as deep.
 */
export function isDeepPage(pathname: string): boolean {
  if (ROLE_HOMES.has(pathname)) return false;
  if (HIDDEN_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return false;
  return true;
}

export function VidyaOrb() {
  const pathname = usePathname() ?? '/';
  const router = useRouter();
  const { role } = useRole();
  const { session } = useAuth();
  const surface = surfaceFromPath(pathname, role);
  // On a deep page Vidya DOCKS (spec 16.4/17): the SAME orb logic + thread +
  // permission ladder, presented as a right-edge docked panel driving the page
  // instead of floating over it. On the home + role landings it floats.
  const docked = isDeepPage(pathname);
  const [open, setOpen] = useState(false);

  // The ONE Vidya send path, shared with the home/landing via useVidya. Because
  // the orb is mounted in the root layout, this thread persists across routes.
  const {
    messages,
    thinking,
    send,
    applyVoiceTurn,
    reset,
    highlight,
    annotation,
    steps,
    canvas,
    closeCanvas,
    clearVisuals,
  } = useVidya();

  const panelRef = useRef<HTMLDivElement | null>(null);
  const orbRef = useRef<HTMLButtonElement | null>(null);
  const voiceRef = useRef<VoiceCapsuleHandle | null>(null);

  // Voice-first: tapping the orb open goes STRAIGHT into listening (mic active,
  // a calm listening pulse) — voice is the primary mode; text is the fallback.
  // When a starter prompt is sent (text) or there is no mic, it stays in text.
  const [voiceState, setVoiceState] = useState<string>('idle');
  const [transcript, setTranscript] = useState<string>('');
  const [textMode, setTextMode] = useState(false);
  // Staged multimodal attachments (image / document / screen still) sent with
  // the next turn, then cleared. Lives in the orb so the composer + voice path
  // both read it.
  const [attachments, setAttachments] = useState<VidyaAttachment[]>([]);

  // Open the orb (and optionally send a starter prompt) on the open event, so a
  // chip on the role landing routes straight into the conversation.
  useEffect(() => {
    function onOpen(e: Event) {
      setOpen(true);
      // Open straight into a ready text composer. Voice is OPT-IN (the mic, or
      // hold-Space) — never an auto getUserMedia on open, which stalls the
      // opening gesture and makes the orb feel broken / unresponsive.
      setTextMode(true);
      const prompt = (e as CustomEvent<{ prompt?: string }>).detail?.prompt;
      if (prompt) void send(prompt);
    }
    function onNew() {
      reset();
      setTextMode(true);
      setOpen(true);
    }
    window.addEventListener(VIDYA_OPEN_EVENT, onOpen);
    window.addEventListener(VIDYA_NEW_EVENT, onNew);
    return () => {
      window.removeEventListener(VIDYA_OPEN_EVENT, onOpen);
      window.removeEventListener(VIDYA_NEW_EVENT, onNew);
    };
  }, [send, reset]);

  // Voice-first: when the orb opens (and not into a text starter), go straight to
  // listening. Falls back to text silently when there is no mic.
  //
  // The auto-start is DEFERRED off the opening click's synchronous task: kicking
  // off mic capture (getUserMedia) inline with the same input event that opened
  // the panel can stall the input pipeline (the pointerup that follows the
  // pointerdown never settles) and freeze the orb. A macrotask hop lets the open
  // gesture complete first, then voice begins. It also never hangs the UI: if the
  // mic is missing we degrade to the typed composer immediately.
  useEffect(() => {
    if (!open || textMode) return;
    const handle = voiceRef.current;
    if (!handle) return;
    if (!handle.available()) {
      setTextMode(true); // graceful degrade: no mic -> text
      return;
    }
    const id = window.setTimeout(() => {
      // Re-read the handle: the panel may have closed during the hop.
      voiceRef.current?.start();
    }, 0);
    return () => window.clearTimeout(id);
  }, [open, textMode]);

  // Close on Escape; return focus to the orb so keyboard users are not stranded.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        closeOrb();
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  // Press-and-hold Space talks to Vidya (spec 17.2/17.4) — but ONLY when focus is
  // not in a text field, so typing a space is never hijacked. The first keydown
  // opens the orb (which voice-first auto-starts listening); releasing Space stops
  // the turn. Key-repeat is ignored so the hold reads as one gesture.
  const orbHidden =
    !session || HIDDEN_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  useEffect(() => {
    if (orbHidden) return; // no shell to talk to on auth/onboarding flows
    function isTextTarget(el: EventTarget | null): boolean {
      const node = el as HTMLElement | null;
      if (!node) return false;
      const tag = node.tagName;
      return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || node.isContentEditable;
    }
    function onDown(e: KeyboardEvent) {
      if (e.code !== 'Space' || e.repeat || isTextTarget(e.target)) return;
      e.preventDefault();
      setTextMode(false);
      setOpen(true);
    }
    function onUp(e: KeyboardEvent) {
      if (e.code !== 'Space' || isTextTarget(e.target)) return;
      // Release Space dismisses the bloom (spec 17.2): the field recedes back
      // toward the orb; never a hard cut. We only act if we were listening.
      if (voiceState === 'listening') closeOrb();
    }
    window.addEventListener('keydown', onDown);
    window.addEventListener('keyup', onUp);
    return () => {
      window.removeEventListener('keydown', onDown);
      window.removeEventListener('keyup', onUp);
    };
  }, [voiceState, orbHidden]);

  // The orb is hidden on the auth + onboarding flows (no signed-in shell there),
  // and until there is a session (so it never flashes during the sign-in redirect).
  if (orbHidden) return null;

  const hasThread = messages.length > 0 || thinking;
  const isListening = voiceState === 'listening';

  function closeOrb() {
    setOpen(false);
    voiceRef.current?.cancel(); // recede the bloom: stop listening, no send
    setTranscript('');
    clearVisuals();
    setAttachments([]);
    orbRef.current?.focus();
  }

  return (
    <div className="vidya-orb-root" data-surface={surface} data-docked={docked ? 'true' : undefined}>
      {/* The Siri-like voice bloom (spec 17.2): a fixed full-screen warm field +
          frosted panel, shown while Vidya is listening. It is a VISUAL layer over
          the existing voice path (VoiceCapsule → voiceConverse); dismiss recedes
          it back toward the orb (esc / release Space / click the field). */}
      <VoiceBloom open={isListening} transcript={transcript} onClose={closeOrb} />

      {/* Speak-and-show overlays render at the page level so they can ring any
          on-screen region while Vidya talks. Visual only — never mutating. */}
      {highlight ? (
        <VidyaSpotlight
          region={highlight.region}
          label={highlight.label}
          note={annotation && annotation.region === highlight.region ? annotation.note : undefined}
          onDismiss={clearVisuals}
        />
      ) : null}
      {annotation && (!highlight || annotation.region !== highlight.region) ? (
        <VidyaSpotlight region={annotation.region} note={annotation.note} onDismiss={clearVisuals} />
      ) : null}

      {/* The on-demand floating canvas — Vidya summons it ONLY when the answer
          needs to be SHOWN (drawn / derived / sketched). It renders at the page
          level so it is the centrepiece even when the orb panel is collapsed,
          and it is always dismissible. */}
      {canvas ? (
        <VidyaCanvas
          spec={canvas}
          onClose={closeCanvas}
          onOpenHref={(href) => router.push(href)}
        />
      ) : null}

      {/* VidyaWatch — the ambient, screen-aware proactive offer (Pillar 1). It
          watches the in-app state and surfaces ONE quiet, dismissible offer when
          the user looks stuck on a hard step; accepting hands off to THIS orb.
          Hidden while the panel is open (Vidya is already engaged) and on the
          auth/onboarding flows (no shell). It is the orb's quiet proactive layer,
          not a second Vidya. */}
      {!open ? <VidyaWatch /> : null}

      {open ? (
        <div
          className="vidya-orb-panel"
          role="dialog"
          aria-label="Vidya"
          aria-modal="false"
          ref={panelRef}
          data-testid="vidya-panel"
          data-voice-state={voiceState}
        >
          <div className="vidya-orb-head">
            <span className="vidya-orb-title">
              <Icon name="spark" size="sm" />
              <span className="overline" style={{ margin: 0 }}>
                Vidya
              </span>
            </span>
            <span className="vidya-orb-actions">
              <button
                type="button"
                className="rail-btn"
                aria-label="New conversation"
                title="New conversation"
                onClick={() => {
                  reset();
                  setTextMode(false);
                }}
              >
                <Icon name="plus" size="sm" />
              </button>
              <button
                type="button"
                className="rail-btn"
                aria-label="Minimise Vidya"
                title="Minimise Vidya"
                onClick={closeOrb}
              >
                <Icon name="close" size="sm" />
              </button>
            </span>
          </div>

          <div className="vidya-orb-body">
            {hasThread ? (
              <MessageThread
                messages={messages}
                thinking={thinking}
                onOpenHref={(href) => router.push(href)}
              />
            ) : (
              <p className="body-sm muted vidya-orb-greeting">
                {isListening ? 'Listening — speak when you are ready.' : GREETING[role]}
              </p>
            )}
            {/* The self-assembling, verified derivation — reveals step-by-step. */}
            {steps ? <VidyaSteps spec={steps} /> : null}
          </div>

          <div className="vidya-orb-foot">
            <VoiceCapsule
              ref={voiceRef}
              onReply={applyVoiceTurn}
              role={role}
              onStateChange={setVoiceState}
              onTranscript={setTranscript}
            />
            {/* Voice is primary; text is the fallback. The composer stays mounted
                (so its test hook + the typed path are always present) but is
                collapsed behind a small "type instead" affordance until used. */}
            {!textMode ? (
              <button
                type="button"
                className="vidya-type-instead body-sm"
                data-testid="vidya-type-instead"
                onClick={() => setTextMode(true)}
              >
                Type instead
              </button>
            ) : null}
            <div
              className="vidya-orb-composer"
              data-testid="vidya-composer"
              hidden={!textMode}
            >
              {/* Multimodal intake — attach an image/document or share the screen.
                  Degrades gracefully when the environment lacks the APIs. */}
              <VidyaAttach attachments={attachments} onChange={setAttachments} />
              <Composer
                onSend={(t) => {
                  setTextMode(true);
                  const staged = attachments;
                  setAttachments([]);
                  void send(t, staged.length > 0 ? staged : undefined);
                }}
                placeholder="Ask Vidya, or describe what you need"
                data-testid="vidya-composer-input"
              />
              {/* An attachment can be sent without typed text — a calm send-now. */}
              {attachments.length > 0 ? (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  data-testid="vidya-attach-send"
                  onClick={() => {
                    setTextMode(true);
                    const staged = attachments;
                    setAttachments([]);
                    void send('', staged);
                  }}
                >
                  Send attachment to Vidya
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      <button
        type="button"
        ref={orbRef}
        className={`vidya-orb${open ? ' is-open' : ''}`}
        aria-label={open ? 'Minimise Vidya' : 'Open Vidya'}
        aria-expanded={open}
        title="Vidya"
        data-testid="vidya-orb"
        onClick={() => {
          // Open text-ready (no auto getUserMedia — that hangs the open). Voice
          // is opt-in: the mic in the panel, or hold-Space.
          setTextMode(true);
          setOpen((v) => !v);
        }}
      >
        {/* The living presence: hairline ring + drifting/breathing gradient core
            + glass highlight + centered low-opacity spark. No shadow (spec 17.1). */}
        <span className="vidya-orb-ring" aria-hidden="true" />
        <span className="vidya-orb-core" aria-hidden="true" />
        <span className="vidya-orb-glass" aria-hidden="true" />
        <Icon name="spark" size="md" />
      </button>
    </div>
  );
}
