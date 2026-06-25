/* ============================================================================
   app/api/email/route.ts — the SERVER-ONLY transactional email broker.

   SERVER-ONLY (runtime = 'nodejs'). Reads the Resend key from process.env as
   CLSS_COMMS_DEV_RESEND_KEY and NEVER returns it, logs it, or exposes it as a
   NEXT_PUBLIC var. The browser sends only { to, email:{ kind, data }, flags };
   this route renders the branded HTML (lib/emailTemplate.ts) and POSTs it to the
   Resend API. The raw key never crosses to the client.

   INVARIANTS:
   - Secrets are ENV-ONLY and server-only. The key is read here, used as a Bearer
     header, and never serialised into a response or a log line.
   - Consent, quiet hours, and child-safety holds are honoured BEFORE any send.
     A withheld consent or an active quiet-hours window resolves { sent:false }
     with a calm reason — nothing is sent.
   - DEGRADE: no key -> 200 { sent:false, reason:'key-unset' }; a provider
     failure -> { sent:false } with a non-leaking reason. Never crashes.

   PRODUCTION NOTE: in production comms route THROUGH the gateway (the wall) which
   holds the provider credential. This dev broker calls Resend directly so the
   surface is demonstrably wired now; the key still never reaches the client.
   ============================================================================ */

import { buildEmail } from '@/lib/emailTemplate';
import { parseEmailInput, sendGate, type SendFlags } from '@/lib/emailGate';
import { authorizeWrite, denied } from '@/lib/opGate';

/** The env var NAME the route reads. Declared for provisioning; value stays in env. */
const RESEND_KEY_ENV = 'CLSS_COMMS_DEV_RESEND_KEY';
/** The fixed, branded From identity. */
const FROM = 'Classess School <noreply@mail.classess.com>';
/** The Resend send endpoint. */
const RESEND_ENDPOINT = 'https://api.resend.com/emails';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const NO_STORE = { 'cache-control': 'no-store', 'content-type': 'application/json' } as const;

function reply(body: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: NO_STORE });
}

interface SendBody {
  to?: unknown;
  email?: unknown;
  flags?: SendFlags;
}

/** A light, defensive email-shape check (the route validates, never trusts). */
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
function isEmail(v: unknown): v is string {
  return typeof v === 'string' && EMAIL_RE.test(v.trim());
}

/** Read the server key without revealing it. Present + plausibly shaped only. */
function readKey(): string | null {
  const key = process.env[RESEND_KEY_ENV];
  return typeof key === 'string' && key.trim().length >= 8 ? key : null;
}

export async function POST(req: Request): Promise<Response> {
  let body: SendBody;
  try {
    body = (await req.json()) as SendBody;
  } catch {
    return reply({ sent: false, reason: 'bad-request' }, 400);
  }

  if (!isEmail(body.to)) return reply({ sent: false, reason: 'invalid-recipient' }, 400);

  // The wall authorizes the send FIRST. Email is cross-context (to a parent/guardian)
  // so the consent purpose runs the consent gate, and the permission ladder
  // (X-Approval-Token) gates the send. A denied caller is refused before the
  // provider key is ever read; an unreachable wall degrades to the path below.
  const wall = await authorizeWrite(req, 'communication', 'send', {
    consentPurpose: 'communication.email',
  });
  if (!wall.proceed) return denied(wall.detail);

  const input = parseEmailInput(body.email);
  if (!input) return reply({ sent: false, reason: 'invalid-input' }, 400);

  // Consent + quiet hours + child-safety are honoured BEFORE any key is read.
  const gate = sendGate(body.flags);
  if (!gate.allowed) return reply({ sent: false, reason: gate.reason });

  const built = buildEmail(input);
  if (!built) return reply({ sent: false, reason: 'invalid-input' }, 400);

  const key = readKey();
  if (!key) {
    // Designed degraded state — the surface keeps a calm "saved, not sent" path.
    return reply({ sent: false, reason: 'key-unset' });
  }

  try {
    const res = await fetch(RESEND_ENDPOINT, {
      method: 'POST',
      headers: {
        // The key is used ONLY as the Bearer credential — never echoed, never logged.
        authorization: `Bearer ${key}`,
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        from: FROM,
        to: (body.to as string).trim(),
        subject: built.subject,
        html: built.html,
      }),
    });
    if (!res.ok) {
      // Non-leaking failure — never surface provider detail or the key.
      return reply({ sent: false, reason: 'provider-error' }, 502);
    }
    const data = (await res.json().catch(() => ({}))) as { id?: string };
    return reply({ sent: true, id: typeof data.id === 'string' ? data.id : undefined });
  } catch {
    return reply({ sent: false, reason: 'send-failed' }, 502);
  }
}

/** A GET probe answers calmly without ever reading or revealing the key. */
export async function GET(): Promise<Response> {
  return reply({ sent: false, reason: 'use-post' }, 405);
}
