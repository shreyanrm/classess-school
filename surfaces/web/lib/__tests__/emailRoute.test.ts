/* ============================================================================
   lib/__tests__/emailRoute.test.ts — the SERVER-ONLY email broker route.

   Pins the invariants that matter:
   - DEGRADE: with no Resend key, POST resolves 200 { sent:false, reason:'key-unset' }
     and never reaches the provider (no fetch is made).
   - CONSENT / QUIET HOURS / CHILD-SAFETY: the send gate blocks before any key is
     read, with a plain reason.
   - VALIDATION: a bad recipient or a malformed body is rejected with a clean 4xx
     and { sent:false } — never a throw.
   - The key is NEVER serialised into a response body.
   ============================================================================ */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { POST } from '@/app/api/email/route';
import { sendGate, parseEmailInput } from '@/lib/emailGate';

const KEY_ENV = 'CLSS_COMMS_DEV_RESEND_KEY';
const SAVED = process.env[KEY_ENV];

function jsonReq(body: unknown): Request {
  return new Request('http://localhost/api/email', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

const VALID_EMAIL = {
  kind: 'roster-invite' as const,
  data: { schoolName: 'Campus North', roleLabel: 'teacher', inviteUrl: 'https://x.test/sign-up' },
};

beforeEach(() => {
  delete process.env[KEY_ENV];
});
afterEach(() => {
  if (SAVED !== undefined) process.env[KEY_ENV] = SAVED;
  vi.restoreAllMocks();
});

describe('sendGate — consent, quiet hours, child-safety', () => {
  it('allows when no flags are set', () => {
    expect(sendGate(undefined)).toEqual({ allowed: true });
    expect(sendGate({})).toEqual({ allowed: true });
    expect(sendGate({ consent: true })).toEqual({ allowed: true });
  });
  it('blocks on withheld consent', () => {
    expect(sendGate({ consent: false })).toEqual({ allowed: false, reason: 'consent-withheld' });
  });
  it('blocks during quiet hours', () => {
    expect(sendGate({ quietHours: true })).toEqual({ allowed: false, reason: 'quiet-hours' });
  });
  it('blocks under a child-safety hold', () => {
    expect(sendGate({ childSafetyHold: true })).toEqual({ allowed: false, reason: 'child-safety-hold' });
  });
});

describe('parseEmailInput — validates the kind + builds', () => {
  it('accepts a known kind with valid data', () => {
    expect(parseEmailInput(VALID_EMAIL)).not.toBeNull();
  });
  it('rejects an unknown kind', () => {
    expect(parseEmailInput({ kind: 'spam', data: {} })).toBeNull();
  });
  it('rejects a missing data object', () => {
    expect(parseEmailInput({ kind: 'roster-invite' })).toBeNull();
    expect(parseEmailInput(null)).toBeNull();
  });
});

describe('POST /api/email — degrades without a key', () => {
  it('returns 200 { sent:false, reason:"key-unset" } and never calls the provider', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const res = await POST(jsonReq({ to: 'a@b.com', email: VALID_EMAIL, flags: { consent: true } }));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.sent).toBe(false);
    expect(body.reason).toBe('key-unset');
    // The provider is never reached on the degraded path.
    expect(fetchSpy).not.toHaveBeenCalled();
    // The key is never present in the response, whether set or not.
    expect(JSON.stringify(body)).not.toContain('CLSS_COMMS');
  });

  it('blocks (without a key read) when consent is withheld', async () => {
    process.env[KEY_ENV] = 'a-plausible-resend-key';
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const res = await POST(jsonReq({ to: 'a@b.com', email: VALID_EMAIL, flags: { consent: false } }));
    const body = await res.json();
    expect(body.sent).toBe(false);
    expect(body.reason).toBe('consent-withheld');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('blocks during quiet hours even with a key present', async () => {
    process.env[KEY_ENV] = 'a-plausible-resend-key';
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const res = await POST(jsonReq({ to: 'a@b.com', email: VALID_EMAIL, flags: { quietHours: true } }));
    const body = await res.json();
    expect(body.reason).toBe('quiet-hours');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('rejects an invalid recipient with a clean 400', async () => {
    const res = await POST(jsonReq({ to: 'not-an-email', email: VALID_EMAIL }));
    expect(res.status).toBe(400);
    expect((await res.json()).reason).toBe('invalid-recipient');
  });

  it('rejects a malformed email input with a clean 400', async () => {
    const res = await POST(jsonReq({ to: 'a@b.com', email: { kind: 'nope', data: {} } }));
    expect(res.status).toBe(400);
    expect((await res.json()).reason).toBe('invalid-input');
  });

  it('sends through the provider when a key is present, never echoing the key', async () => {
    process.env[KEY_ENV] = 'a-plausible-resend-key';
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        new Response(JSON.stringify({ id: 'msg_123' }), { status: 200 }) as Response,
      );
    const res = await POST(jsonReq({ to: 'a@b.com', email: VALID_EMAIL, flags: { consent: true } }));
    const body = await res.json();
    expect(body.sent).toBe(true);
    expect(body.id).toBe('msg_123');
    expect(fetchSpy).toHaveBeenCalledOnce();
    // The Bearer header carries the key; the response body never does.
    const [, init] = fetchSpy.mock.calls[0]!;
    const headers = (init as RequestInit).headers as Record<string, string>;
    expect(headers.authorization).toContain('a-plausible-resend-key');
    expect(JSON.stringify(body)).not.toContain('a-plausible-resend-key');
  });
});
