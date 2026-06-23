/* ============================================================================
   lib/realtime.ts — live messaging + presence over Supabase Realtime.

   CLIENT-SAFE. Uses the PUBLIC anon Supabase client (lib/supabaseClient.ts) —
   the anon key + url are public by design (RLS is the wall), so Realtime
   broadcast + presence run in the browser. The durable history lives behind the
   server-only /api/messages route (lib/opData.ts); this module is the live
   fan-out that makes two open clients see each other's messages and presence in
   real time, plus a small notification hook.

   GRACEFUL DEGRADATION: when Supabase is not configured (no NEXT_PUBLIC vars)
   joinChannel() returns a no-op handle, so app/messages keeps working entirely
   on its local thread. Nothing here ever throws, and no secret is read.

   LAWS honoured here:
     - no secret value read; only the public anon client is used.
     - sender/presence refs are OPAQUE canonical_uuids, never PII.
     - the live path is additive — the safety + consent gates still run upstream
       in the surface before a message is ever broadcast.
   ============================================================================ */

import { getSupabaseClient, isSupabaseConfigured } from './supabaseClient';

/** A live message as it travels over the broadcast channel. Opaque refs only. */
export interface LiveMessage {
  /** Client-minted opaque message id (dedupe key across clients). */
  id: string;
  /** Opaque sender ref (canonical_uuid) — never PII. */
  senderRef: string;
  /** Already safety-screened body (the gate ran before broadcast). */
  body: string;
  /** Whether the safety gate flagged it for a responsible adult. */
  flagged?: boolean;
  /** ISO timestamp the message was posted. */
  postedAt: string;
}

/** A presence entry — who is currently in the channel. Opaque ref + a handle. */
export interface LivePresence {
  ref: string;
  /** Non-identifying display handle (e.g. a role label) — never raw PII. */
  handle: string;
}

/** The handle a caller holds onto; calling leave() tears the channel down. */
export interface ChannelHandle {
  /** Broadcast a message to everyone in the channel. Best-effort, never throws. */
  send(message: LiveMessage): Promise<void>;
  /** Current presence snapshot (who is here). Empty on the degraded path. */
  presence(): LivePresence[];
  /** Whether this is a live channel or the degraded no-op. */
  live: boolean;
  /** Leave the channel and release resources. Idempotent. */
  leave(): Promise<void>;
}

export interface JoinChannelOptions {
  /** The channel/topic name — scope by an opaque id (e.g. `msg:<channelId>`). */
  topic: string;
  /** This client's presence identity (opaque ref + handle). */
  self: LivePresence;
  /** Fired when a remote message arrives (not your own echo). */
  onMessage?: (message: LiveMessage) => void;
  /** Fired when presence changes (someone joins/leaves). */
  onPresence?: (present: LivePresence[]) => void;
  /** Fired once with a calm toast line when a remote message arrives. */
  onNotify?: (line: string) => void;
}

const MESSAGE_EVENT = 'message' as const;

/** True when the live realtime path is available (public Supabase configured). */
export function isRealtimeConfigured(): boolean {
  return isSupabaseConfigured();
}

/** The degraded no-op handle — used when Supabase is unconfigured. */
function noopHandle(): ChannelHandle {
  return {
    async send() {
      /* local-only: the surface keeps its own thread; nothing to broadcast */
    },
    presence() {
      return [];
    },
    live: false,
    async leave() {
      /* nothing to tear down */
    },
  };
}

/**
 * Join a live messaging channel: subscribes to broadcast messages + presence,
 * and returns a handle to send + read presence + leave. On the degraded path
 * (no Supabase) it resolves to a no-op handle so the surface still runs.
 *
 * Pure-ish and defensive: any failure resolves to the no-op handle rather than
 * throwing, so a flaky network never breaks the messages surface.
 */
export async function joinChannel(opts: JoinChannelOptions): Promise<ChannelHandle> {
  if (!isSupabaseConfigured()) return noopHandle();

  const supabase = await getSupabaseClient();
  if (!supabase || typeof supabase.channel !== 'function') return noopHandle();

  try {
    const channel = supabase.channel(opts.topic, {
      config: { presence: { key: opts.self.ref }, broadcast: { self: false } },
    });

    const readPresence = (): LivePresence[] => {
      try {
        const state = channel.presenceState();
        const out: LivePresence[] = [];
        for (const key of Object.keys(state)) {
          const entries = state[key] ?? [];
          const first = entries[0] as Partial<LivePresence> | undefined;
          out.push({ ref: key, handle: typeof first?.handle === 'string' ? first.handle : 'Someone' });
        }
        return out;
      } catch {
        return [];
      }
    };

    channel.on('broadcast', { event: MESSAGE_EVENT }, (payload: unknown) => {
      const msg = (payload as { payload?: LiveMessage })?.payload;
      if (!msg || typeof msg.id !== 'string') return;
      opts.onMessage?.(msg);
      opts.onNotify?.('New message');
    });

    channel.on('presence', { event: 'sync' }, () => {
      opts.onPresence?.(readPresence());
    });

    await Promise.resolve(
      channel.subscribe((status: string) => {
        if (status === 'SUBSCRIBED') {
          void Promise.resolve(channel.track({ handle: opts.self.handle }));
        }
      }),
    );

    return {
      async send(message: LiveMessage) {
        try {
          await Promise.resolve(
            channel.send({ type: 'broadcast', event: MESSAGE_EVENT, payload: message }),
          );
        } catch {
          /* best-effort: a failed broadcast does not break the surface */
        }
      },
      presence: readPresence,
      live: true,
      async leave() {
        try {
          await Promise.resolve(supabase.removeChannel(channel));
        } catch {
          /* idempotent teardown */
        }
      },
    };
  } catch {
    return noopHandle();
  }
}
