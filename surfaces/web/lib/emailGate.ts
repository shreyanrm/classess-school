/* ============================================================================
   lib/emailGate.ts — pure, node-testable helpers for the email broker.

   Kept OUT of app/api/email/route.ts because a Next.js route file may only
   export HTTP method handlers + route config (runtime/dynamic). These two pure
   functions (input validation + the consent/quiet-hours/child-safety gate) live
   here so the route stays a valid Route module and the helpers stay unit-testable.
   ============================================================================ */

import { buildEmail, EMAIL_KINDS, type EmailInput } from './emailTemplate';

/** The consent + timing flags a caller passes through. */
export interface SendFlags {
  consent?: boolean;
  quietHours?: boolean;
  childSafetyHold?: boolean;
}

/** Narrow an unknown payload to a valid EmailInput, or null when malformed. */
export function parseEmailInput(value: unknown): EmailInput | null {
  if (!value || typeof value !== 'object') return null;
  const v = value as { kind?: unknown; data?: unknown };
  if (typeof v.kind !== 'string' || !EMAIL_KINDS.includes(v.kind as never)) return null;
  if (!v.data || typeof v.data !== 'object') return null;
  // The typed builder is the real validator (it reads only the fields it needs
  // and escapes them); a successful build is the gate.
  const candidate = { kind: v.kind, data: v.data } as EmailInput;
  return buildEmail(candidate) ? candidate : null;
}

/**
 * Decide whether a send is permitted by the consent / quiet-hours / child-safety
 * flags. Pure + node-testable. Returns a plain reason when blocked so the route
 * can answer calmly. Consent gates every send: an EXPLICIT false blocks.
 */
export function sendGate(flags: SendFlags | undefined): { allowed: boolean; reason?: string } {
  if (flags?.consent === false) return { allowed: false, reason: 'consent-withheld' };
  if (flags?.quietHours === true) return { allowed: false, reason: 'quiet-hours' };
  if (flags?.childSafetyHold === true) return { allowed: false, reason: 'child-safety-hold' };
  return { allowed: true };
}
