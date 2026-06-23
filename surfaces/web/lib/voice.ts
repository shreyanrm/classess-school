/* ============================================================================
   lib/voice.ts — the Vidya voice client (speech-to-speech).

   A small, typed client that fetches a SHORT-LIVED ephemeral voice session
   token from the server route (/api/voice/token) and manages the session
   state machine. The provider wiring sits behind an interface so a missing or
   invalid key degrades cleanly: the client never holds a server secret, never
   sees the raw API key, and resolves to an "unavailable" state instead of
   crashing.

   INVARIANT (secrets are ENV-ONLY, server-only): the browser never reads
   CLSS_AIFABRIC_DEV_GEMINI_API_KEY. It only ever receives a minted, expiring
   ephemeral token from the gateway-backed route, and falls back gracefully when
   that route answers 503.
   ============================================================================ */

/** The lifecycle of a voice session, surfaced to the UI as first-class states. */
export type VoiceState =
  | 'idle' // no session; tap to speak
  | 'connecting' // requesting an ephemeral token
  | 'listening' // mic open, capturing speech
  | 'thinking' // utterance sent, awaiting Vidya
  | 'speaking' // Vidya is replying in voice
  | 'unavailable' // no token / no key — degrade calmly
  | 'error'; // a transient failure; retry is offered

/** The ephemeral session token shape returned by the server route. Never the raw key. */
export interface VoiceToken {
  /** The short-lived, opaque session token. Safe to hold in the browser. */
  token: string;
  /** ISO timestamp at which the token expires. */
  expiresAt: string;
  /** The provider that minted it (for client wiring), never a secret. */
  provider: string;
  /** The realtime model the session is bound to. */
  model: string;
}

/** A clean, non-throwing result for the token fetch. */
export type VoiceTokenResult =
  | { ok: true; token: VoiceToken }
  | { ok: false; reason: 'unavailable' | 'error'; message: string };

/**
 * The provider interface. The default implementation calls our server route;
 * tests inject a fake so the degraded path is covered WITHOUT network.
 */
export interface VoiceProvider {
  /** Mint (or fetch) an ephemeral session token. Must never throw. */
  fetchToken(signal?: AbortSignal): Promise<VoiceTokenResult>;
}

/** The route the browser asks for an ephemeral token. Server-only secret stays server-side. */
export const VOICE_TOKEN_ROUTE = '/api/voice/token';

/** The env var NAME the server route reads. Declared here for provisioning; never a value. */
export const VOICE_ENV_VAR = 'CLSS_AIFABRIC_DEV_GEMINI_API_KEY';

/**
 * The default provider: fetches the ephemeral token from our own server route.
 * A 503 means voice is unavailable (no key, by design) — that resolves to a
 * calm `unavailable`, never an error. Any other non-OK or network failure is a
 * transient `error` the UI can offer to retry.
 */
export function httpVoiceProvider(route: string = VOICE_TOKEN_ROUTE): VoiceProvider {
  return {
    async fetchToken(signal?: AbortSignal): Promise<VoiceTokenResult> {
      try {
        const res = await fetch(route, {
          method: 'POST',
          headers: { accept: 'application/json' },
          signal,
        });

        if (res.status === 503) {
          return {
            ok: false,
            reason: 'unavailable',
            message: 'Voice is unavailable right now. You can keep typing to Vidya.',
          };
        }

        if (!res.ok) {
          return {
            ok: false,
            reason: 'error',
            message: 'Voice could not start. Try again in a moment.',
          };
        }

        const body = (await res.json()) as Partial<VoiceToken>;
        if (!body || typeof body.token !== 'string' || typeof body.expiresAt !== 'string') {
          return {
            ok: false,
            reason: 'error',
            message: 'Voice could not start. Try again in a moment.',
          };
        }

        return {
          ok: true,
          token: {
            token: body.token,
            expiresAt: body.expiresAt,
            provider: body.provider ?? 'gemini',
            model: body.model ?? 'gemini-live',
          },
        };
      } catch {
        // Network error / abort — never crash the surface.
        return {
          ok: false,
          reason: 'error',
          message: 'Voice could not start. Check your connection and try again.',
        };
      }
    },
  };
}

/** A snapshot of the session for the UI to render. */
export interface VoiceSnapshot {
  state: VoiceState;
  /** The last transcript line (interim or final), shown beneath the mic. */
  transcript: string;
  /** A calm, plain-language message when unavailable or errored. */
  message?: string;
}

/**
 * The voice session — a tiny state machine over a provider. It does not own
 * the audio pipeline (that is the provider's realtime SDK in production); it
 * owns the connect -> listen -> think -> speak lifecycle and the graceful
 * degrade. UI subscribes to snapshots.
 *
 * Crucially, `connect()` resolves a token through the provider. If the token is
 * `unavailable` (no key) the session lands in `unavailable` — a designed state,
 * not a thrown error.
 */
export class VoiceSession {
  private provider: VoiceProvider;
  private snapshot: VoiceSnapshot = { state: 'idle', transcript: '' };
  private listeners = new Set<(s: VoiceSnapshot) => void>();
  private token: VoiceToken | null = null;

  constructor(provider: VoiceProvider = httpVoiceProvider()) {
    this.provider = provider;
  }

  /** Current snapshot (immutable copy). */
  get(): VoiceSnapshot {
    return { ...this.snapshot };
  }

  /** Subscribe to snapshot changes. Returns an unsubscribe fn. */
  subscribe(fn: (s: VoiceSnapshot) => void): () => void {
    this.listeners.add(fn);
    fn(this.get());
    return () => {
      this.listeners.delete(fn);
    };
  }

  private set(next: Partial<VoiceSnapshot>) {
    this.snapshot = { ...this.snapshot, ...next };
    const copy = this.get();
    this.listeners.forEach((fn) => fn(copy));
  }

  /**
   * Acquire an ephemeral token and move to `listening`. On a missing key the
   * session degrades to `unavailable`; on a transient failure, to `error`.
   * Returns the resulting state so callers can branch without re-reading.
   */
  async connect(signal?: AbortSignal): Promise<VoiceState> {
    this.set({ state: 'connecting', transcript: '', message: undefined });
    const result = await this.provider.fetchToken(signal);

    if (!result.ok) {
      this.token = null;
      this.set({ state: result.reason, message: result.message });
      return result.reason;
    }

    this.token = result.token;
    this.set({ state: 'listening', message: undefined });
    return 'listening';
  }

  /** Whether a usable, unexpired token is held. */
  hasToken(now: number = Date.now()): boolean {
    if (!this.token) return false;
    const expiry = Date.parse(this.token.expiresAt);
    if (Number.isNaN(expiry)) return false;
    return expiry > now;
  }

  /** Update the live transcript line as the provider streams it. */
  setTranscript(text: string) {
    this.set({ transcript: text });
  }

  /** Mark that the utterance is being processed. */
  think() {
    if (this.snapshot.state === 'listening') this.set({ state: 'thinking' });
  }

  /** Mark that Vidya is replying in voice. */
  speak() {
    this.set({ state: 'speaking' });
  }

  /** Stop the session and return to idle, discarding the token. */
  stop() {
    this.token = null;
    this.set({ state: 'idle', transcript: '', message: undefined });
  }
}
