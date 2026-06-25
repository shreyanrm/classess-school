/* ============================================================================
   lib/emailClient.ts — the CLIENT-SAFE seam to the transactional email route.

   The browser side of transactional email. It builds a well-formed request and
   POSTs it to /api/email, which renders the branded HTML (lib/emailTemplate.ts)
   and hands it to Resend using the SERVER-ONLY key. Like lib/opData.ts this
   carries NO secret and NO Resend import — it is safe to bundle into a client
   component.

   GRACEFUL DEGRADATION: every call is best-effort and NEVER throws. When the
   Resend key is unset, the route answers 200 { sent:false } and the caller shows
   a calm "saved, not sent" state — nothing blank, nothing crashes.

   CONSENT + QUIET HOURS: the caller passes the consent + quiet-hours flags it
   already holds; the route honours them and will not send when consent is
   withheld or quiet hours are active. No PII is required — labels are generic.
   ============================================================================ */

import type { EmailInput } from './emailTemplate';
import { readStore } from './store';

/** The route transactional email posts to. */
export const EMAIL_ROUTE = '/api/email';

/** Opaque caller-identity headers (canonical_uuid + role) the wall reads to
 *  authorize the cross-context send (lib/opGate). Never PII, never a secret. */
function callerHeaders(): Record<string, string> {
  try {
    const account = readStore().account;
    if (!account?.id) return {};
    return { 'x-caller-uuid': account.id, 'x-caller-role': account.role, 'x-caller-app': 'school' };
  } catch {
    return {};
  }
}

/** The consent + timing flags the caller already holds, passed through to the route. */
export interface SendFlags {
  /** False blocks the send (consent gates every send). Defaults to allowed. */
  consent?: boolean;
  /** True blocks the send until quiet hours pass. */
  quietHours?: boolean;
  /** True marks this as concerning a child, so child-safety holds apply. */
  childSafetyHold?: boolean;
}

/** The shape every email send accepts: a recipient, the typed input, the flags. */
export interface SendEmailInput {
  /** The destination address. The route validates it; never logged with the key. */
  to: string;
  /** The typed { kind, data } the template builder renders. */
  email: EmailInput;
  /** Consent + quiet-hours + child-safety flags. */
  flags?: SendFlags;
}

/** What the route answers. `sent` is false on the degraded / blocked path. */
export interface SendEmailResult {
  sent: boolean;
  /** A non-sensitive reason on the not-sent path (never a key, never the body). */
  reason?: string;
  /** The provider message id when actually sent. */
  id?: string;
}

/** Send a transactional email. Best-effort, never throws, degrades to { sent:false }. */
export async function sendEmail(
  input: SendEmailInput,
  fetchImpl: typeof fetch = fetch,
): Promise<SendEmailResult> {
  try {
    const res = await fetchImpl(EMAIL_ROUTE, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...callerHeaders() },
      body: JSON.stringify(input),
    });
    const data = (await res.json().catch(() => ({}))) as Partial<SendEmailResult>;
    return {
      sent: Boolean(data.sent),
      reason: typeof data.reason === 'string' ? data.reason : undefined,
      id: typeof data.id === 'string' ? data.id : undefined,
    };
  } catch {
    return { sent: false, reason: 'network' };
  }
}
