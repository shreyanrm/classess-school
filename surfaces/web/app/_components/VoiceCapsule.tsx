'use client';

import { useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState, forwardRef } from 'react';
import {
  converse as defaultConverse,
  startRecording,
  blobToWavBase64,
  playWavBase64,
  micSupported,
  type Recording,
} from '@/lib/voiceConverse';
import type { VidyaAction } from '@/lib/vidya';
import type { Role } from '@/lib/mock';

type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'unavailable' | 'error';

export interface VoiceCapsuleProps {
  /**
   * Called when a spoken turn completes, with Vidya's reply text AND the same
   * navigate/render actions a typed turn returns — so the caller applies them
   * through the SAME path (useVidya.applyVoiceTurn).
   */
  onReply?: (text: string, actions: VidyaAction[]) => void;
  /** The viewer role, so voice shapes its help and navigation like text. */
  role?: Role;
  /** Injectable for tests/stories — defaults to the real /api/voice/converse client. */
  converseFn?: typeof defaultConverse;
  /** Notifies the parent of the live voice state (so the orb pulse can match). */
  onStateChange?: (state: VoiceState) => void;
  /**
   * Notifies the parent of the latest transcript line (the spoken reply, or a
   * status while thinking) so the voice bloom can show it live. Real STT interim
   * text wires here when the fabric exposes it; today it carries the reply.
   */
  onTranscript?: (text: string) => void;
}

/** An imperative handle so the orb can drive voice-first: tap the orb to go
 *  STRAIGHT into listening, without a second tap on the mic. */
export interface VoiceCapsuleHandle {
  /** Begin listening if the mic is available; no-op while busy. */
  start: () => void;
  /** Cancel an in-flight listen WITHOUT sending (the bloom's calm dismiss). */
  cancel: () => void;
  /** Whether the mic is supported in this environment. */
  available: () => boolean;
}

/** Plain-language status per state — calm, no exclamation, no emoji. */
const STATUS: Record<VoiceState, string> = {
  idle: 'Tap to speak with Vidya',
  listening: 'Listening — tap to send',
  thinking: 'Thinking',
  speaking: 'Vidya is speaking',
  unavailable: 'Voice is unavailable right now',
  error: 'Voice could not start',
};

function MicGlyph({ muted }: { muted?: boolean }) {
  return (
    <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v3" />
      {muted ? <path d="M4 4l16 16" /> : null}
    </svg>
  );
}

function Waveform({ active }: { active: boolean }) {
  const bars = useMemo(() => Array.from({ length: 7 }), []);
  return (
    <span className={`voice-wave${active ? ' active' : ''}`} aria-hidden="true">
      {bars.map((_, i) => (
        <i key={i} style={{ animationDelay: `${i * 90}ms` }} />
      ))}
    </span>
  );
}

/**
 * A calm, optional voice affordance for the Vidya home. Push-to-talk: tap to
 * record, tap again to send. The recorded turn is posted to /api/voice/converse,
 * which runs speech understanding + reply + text-to-speech SERVER-SIDE and
 * returns spoken audio — the provider key never reaches the browser. With no key
 * configured (or no mic), the capsule reads "unavailable" and typing still works.
 */
export const VoiceCapsule = forwardRef<VoiceCapsuleHandle, VoiceCapsuleProps>(function VoiceCapsule(
  { onReply, role, converseFn = defaultConverse, onStateChange, onTranscript }: VoiceCapsuleProps,
  ref,
) {
  const [state, setState] = useState<VoiceState>('idle');
  const [message, setMessage] = useState<string>('');
  const [reply, setReply] = useState<string>('');
  const recRef = useRef<Recording | null>(null);

  const active = state === 'listening' || state === 'speaking';
  const isDegraded = state === 'unavailable' || state === 'error';

  // Keep the parent (the orb) in step with the live voice state so its aura can
  // mirror listening / thinking / speaking.
  useEffect(() => {
    onStateChange?.(state);
  }, [state, onStateChange]);

  // Surface the live transcript line (reply, or a calm status) to the bloom.
  useEffect(() => {
    onTranscript?.(reply || message);
  }, [reply, message, onTranscript]);

  const sendTurn = useCallback(
    async (blob: Blob) => {
      setState('thinking');
      setMessage('');
      try {
        const audioBase64 = await blobToWavBase64(blob);
        const res = await converseFn({ audioBase64, mimeType: 'audio/wav', role });
        if (!res.available) {
          setState('unavailable');
          setMessage('');
          return;
        }
        if (res.reply) setReply(res.reply);
        // Forward the reply + actions even when the reply text is empty but an
        // action was returned, so a spoken navigate/render still lands.
        if (res.reply || (res.actions && res.actions.length > 0)) {
          onReply?.(res.reply ?? '', res.actions ?? []);
        }
        if (res.audioBase64) {
          setState('speaking');
          await playWavBase64(res.audioBase64);
        }
        setState('idle');
      } catch {
        setState('error');
      }
    },
    [converseFn, onReply, role],
  );

  // Begin listening. Shared by the mic tap and the orb's voice-first auto-start.
  const beginListening = useCallback(async () => {
    if (state === 'thinking' || state === 'speaking' || state === 'listening') return;
    if (!micSupported()) {
      setState('unavailable');
      return;
    }
    try {
      recRef.current = await startRecording();
      setState('listening');
      setReply('');
    } catch {
      setState('unavailable'); // permission denied / no device
    }
  }, [state]);

  const toggle = useCallback(async () => {
    if (state === 'listening') {
      const rec = recRef.current;
      recRef.current = null;
      if (rec) await sendTurn(await rec.stop());
      return;
    }
    await beginListening();
  }, [state, sendTurn, beginListening]);

  // Cancel listening without sending — discard the recording, return to idle.
  const cancel = useCallback(() => {
    const rec = recRef.current;
    recRef.current = null;
    void rec?.stop().catch(() => undefined);
    setReply('');
    setMessage('');
    setState('idle');
  }, []);

  // Voice-first: the orb can tap us straight into listening on open.
  useImperativeHandle(
    ref,
    () => ({
      start: () => {
        void beginListening();
      },
      cancel,
      available: () => micSupported(),
    }),
    [beginListening, cancel],
  );

  return (
    <div className={`voice-capsule${isDegraded ? ' degraded' : ''}`} role="group" aria-label="Voice" data-testid="vidya-voice">
      <button
        type="button"
        className={`voice-mic${active ? ' active' : ''}`}
        aria-pressed={state === 'listening'}
        aria-label={state === 'idle' ? 'Speak with Vidya' : state === 'listening' ? 'Send' : STATUS[state]}
        disabled={state === 'thinking'}
        data-testid="vidya-mic"
        onClick={toggle}
      >
        <MicGlyph muted={isDegraded} />
      </button>

      <Waveform active={active} />

      <span className="voice-status" aria-live="polite">
        {message || STATUS[state]}
      </span>

      {reply ? (
        <span className="voice-transcript" aria-live="polite">
          {reply}
        </span>
      ) : null}

      {state === 'error' ? (
        <button type="button" className="voice-retry" onClick={toggle}>
          Try again
        </button>
      ) : null}
    </div>
  );
});
