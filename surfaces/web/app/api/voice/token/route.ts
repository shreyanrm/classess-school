/* ============================================================================
   app/api/voice/token/route.ts — mint a short-lived ephemeral voice token.

   SERVER-ONLY. Reads CLSS_AIFABRIC_DEV_GEMINI_API_KEY from process.env on the
   server and NEVER returns it to the client. The browser receives only an
   opaque, expiring session token it can use to open a realtime voice session.

   INVARIANTS:
   - Secrets are ENV-ONLY and server-only. The raw key is never serialised into
     the response, never logged, never exposed as a NEXT_PUBLIC var.
   - Degrade gracefully: if the key is unset or obviously invalid, respond 503
     with a clean "voice unavailable" body. Never crash, never leak.
   - In production the ephemeral token is minted by the AI fabric THROUGH the
     gateway (every cross-service call passes the wall). This route is the
     server-side broker for that exchange; until the live mint endpoint is
     provisioned it issues a locally-signed, short-lived stand-in so the surface
     is runnable and the degraded path is exercised — it still never reveals the
     server key.
   ============================================================================ */

import { randomUUID, createHmac } from 'node:crypto';

/** The env var NAME the route reads. Declared for provisioning; value stays in env. */
const VOICE_KEY_ENV = 'CLSS_AIFABRIC_DEV_GEMINI_API_KEY';

/** Ephemeral tokens live briefly — long enough to open a session, short enough to be low-risk. */
const TOKEN_TTL_MS = 60_000;

/** This route must run on the Node server runtime (it reads a server secret + uses crypto). */
export const runtime = 'nodejs';
/** Never cache a minted token. */
export const dynamic = 'force-dynamic';

function voiceUnavailable(reason: string): Response {
  // A clean, non-leaking 503. The body carries no key material and no stack.
  return new Response(
    JSON.stringify({
      available: false,
      reason,
      message: 'Voice is unavailable right now. You can keep typing to Vidya.',
    }),
    {
      status: 503,
      headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
    },
  );
}

/**
 * Validate the server key without revealing it. We only check that it is
 * present and plausibly shaped — we never echo it. A real mint would exchange
 * it with the AI fabric via the gateway; here we derive an opaque ephemeral
 * token whose secret material is the server key, so the key itself never
 * crosses the wire.
 */
function isPlausibleKey(value: string | undefined): value is string {
  return typeof value === 'string' && value.trim().length >= 16;
}

function mintEphemeralToken(serverKey: string): { token: string; expiresAt: string } {
  const issuedAt = Date.now();
  const expiresAt = new Date(issuedAt + TOKEN_TTL_MS).toISOString();
  const nonce = randomUUID();
  // The token is an opaque, signed handle. The server key is used ONLY as the
  // HMAC secret and is never embedded in the output. The client cannot recover
  // the key from this value.
  const payload = `${nonce}.${expiresAt}`;
  const signature = createHmac('sha256', serverKey).update(payload).digest('base64url');
  const token = `${Buffer.from(payload).toString('base64url')}.${signature}`;
  return { token, expiresAt };
}

async function handle(): Promise<Response> {
  const serverKey = process.env[VOICE_KEY_ENV];

  if (!isPlausibleKey(serverKey)) {
    // No key (or an obviously invalid one) -> designed degraded state, not an error.
    return voiceUnavailable('key-unset');
  }

  try {
    const { token, expiresAt } = mintEphemeralToken(serverKey);
    return new Response(
      JSON.stringify({
        available: true,
        token, // opaque ephemeral session token — NOT the server key
        expiresAt,
        provider: 'gemini',
        model: 'gemini-live',
      }),
      {
        status: 200,
        headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
      },
    );
  } catch {
    // Any failure during minting degrades cleanly; the key is never surfaced.
    return voiceUnavailable('mint-failed');
  }
}

/** Tokens are minted on POST (the client initiates a session). */
export async function POST(): Promise<Response> {
  return handle();
}

/** A GET probe answers the same way, so health checks never leak the key either. */
export async function GET(): Promise<Response> {
  return handle();
}
