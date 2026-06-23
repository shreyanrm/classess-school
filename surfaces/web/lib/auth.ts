/* ============================================================================
   lib/auth.ts — the one auth abstraction the app talks to.

   The app never calls Supabase directly for auth; it calls this module, which:

     - uses REAL Supabase Auth (email/password, OAuth, phone OTP) when the public
       env vars are configured (NEXT_PUBLIC_SUPABASE_URL + _ANON_KEY); the session
       is persisted by Supabase in localStorage and rehydrates on reload, OR
     - DEGRADES to a local-store session when those vars are absent (the demo
       default) — so sign-in / sign-up / sign-out always work with no backend.

   It exposes a single AuthSession shape regardless of backend, plus a subscribe()
   so React can re-render on a session change. The local path is deliberately
   pure and node-testable (it routes every read/write through lib/store.ts).

   No secret value is read here. The anon key + URL are public by design and live
   only behind lib/supabaseClient.ts.
   ============================================================================ */

import type { Role } from './mock';
import {
  readStore,
  updateStore,
  clearStore,
  subscribe as subscribeStore,
  mintId,
  maskContact,
  type Account,
} from './store';
import { getSupabaseClient, isSupabaseConfigured } from './supabaseClient';

/** The auth shapes the familiar sign-in / sign-up surface offers. */
export type AuthMethod = 'password' | 'google' | 'apple' | 'microsoft' | 'phone-otp';

/** The single session shape the whole app reads, backend-agnostic. */
export interface AuthSession {
  /** Opaque user id (Supabase user id, or a locally-minted demo id). */
  userId: string;
  /** A non-identifying display handle (masked email/phone) — never raw PII. */
  handle: string;
  /** Whether this session came from real Supabase Auth or the local degrade. */
  source: 'supabase' | 'local';
  /** The auth shape used. */
  method: AuthMethod;
}

/** The outcome of an auth attempt — calm, plain, never throws on the caller. */
export interface AuthResult {
  ok: boolean;
  session?: AuthSession;
  /** Plain-language error for the form (never a stack, never a key). */
  error?: string;
}

/** True when real Supabase Auth is wired; false means the local degrade path. */
export function authConfigured(): boolean {
  return isSupabaseConfigured();
}

// ---------------------------------------------------------------------------
// Non-identifying handle helpers — we keep a masked hint, never raw PII.
// ---------------------------------------------------------------------------

/** Mask an email to a non-identifying handle, e.g. "a•••@gmail.com". */
export function maskEmail(email: string): string {
  const at = email.indexOf('@');
  if (at <= 0) return '•••';
  const name = email.slice(0, at);
  const domain = email.slice(at + 1);
  const head = name.slice(0, 1);
  return `${head}•••@${domain}`;
}

// ---------------------------------------------------------------------------
// The local degrade path — a session minted into lib/store's Account slot.
// Pure and node-testable: it only touches the store, never the network.
// ---------------------------------------------------------------------------

/** Map our auth method onto the store Account's narrower method set. */
function accountMethod(method: AuthMethod): Account['method'] {
  if (method === 'google') return 'google';
  if (method === 'apple') return 'apple';
  if (method === 'microsoft') return 'microsoft';
  // password + phone-otp both persist as the phone-otp demo shape (opaque id +
  // optional masked hint); no password or number is ever stored.
  return 'phone-otp';
}

/** Build the AuthSession view of a stored local Account. */
function sessionFromAccount(account: Account): AuthSession {
  return {
    userId: account.id,
    handle: account.contactHint ?? 'Demo account',
    source: 'local',
    method:
      account.method === 'google'
        ? 'google'
        : account.method === 'apple'
          ? 'apple'
          : account.method === 'microsoft'
            ? 'microsoft'
            : 'password',
  };
}

/** Mint + persist a local demo session (the degrade path). Never stores PII. */
export function localSignIn(input: {
  role: Role;
  method: AuthMethod;
  /** Raw email/phone — only a masked hint is kept; the raw value is discarded. */
  contact?: string;
}): AuthSession {
  const handle =
    input.method === 'password' && input.contact
      ? maskEmail(input.contact)
      : input.contact
        ? maskContact(input.contact)
        : 'Demo account';

  const account: Account = {
    id: mintId(),
    role: input.role,
    method: accountMethod(input.method),
    contactHint: handle,
    demo: true,
    createdAt: new Date().toISOString(),
  };
  updateStore((s) => ({ ...s, account }));
  return sessionFromAccount(account);
}

/** Read the current local session from the store, or null when signed out. */
export function localSession(): AuthSession | null {
  const account = readStore().account;
  return account ? sessionFromAccount(account) : null;
}

/** Clear the local session (and everything tied to the demo identity). */
export function localSignOut(): void {
  clearStore();
}

// ---------------------------------------------------------------------------
// The public API — chooses the Supabase path when configured, else the local
// degrade. Every method resolves (never throws) so the forms stay calm.
// ---------------------------------------------------------------------------

/** Read the current session. Async because Supabase resolves it asynchronously;
 *  the local path resolves synchronously-fast. Returns null when signed out. */
export async function getSession(): Promise<AuthSession | null> {
  const supabase = await getSupabaseClient();
  if (supabase) {
    try {
      const { data } = await supabase.auth.getSession();
      const s = data.session;
      if (!s?.user) return null;
      return {
        userId: s.user.id,
        handle: s.user.email ? maskEmail(s.user.email) : s.user.phone ? maskContact(s.user.phone) : 'Account',
        source: 'supabase',
        method: 'password',
      };
    } catch {
      return null;
    }
  }
  return localSession();
}

/** Create an account with email + password (or degrade to a local session). */
export async function signUpWithPassword(input: {
  email: string;
  password: string;
  role: Role;
}): Promise<AuthResult> {
  const supabase = await getSupabaseClient();
  if (supabase) {
    try {
      const { data, error } = await supabase.auth.signUp({
        email: input.email,
        password: input.password,
      });
      if (error) return { ok: false, error: error.message };
      const user = data.user;
      if (!user) {
        // Email confirmation may be required — surface a calm, plain message.
        return { ok: false, error: 'Check your inbox to confirm your email, then sign in.' };
      }
      return {
        ok: true,
        session: {
          userId: user.id,
          handle: maskEmail(input.email),
          source: 'supabase',
          method: 'password',
        },
      };
    } catch {
      return { ok: false, error: 'Could not reach the sign-up service. Please try again.' };
    }
  }
  return { ok: true, session: localSignIn({ role: input.role, method: 'password', contact: input.email }) };
}

/** Sign in with email + password (or degrade to a local session). */
export async function signInWithPassword(input: {
  email: string;
  password: string;
  role: Role;
}): Promise<AuthResult> {
  const supabase = await getSupabaseClient();
  if (supabase) {
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: input.email,
        password: input.password,
      });
      if (error) return { ok: false, error: error.message };
      const user = data.user;
      if (!user) return { ok: false, error: 'Those details did not match. Please try again.' };
      return {
        ok: true,
        session: {
          userId: user.id,
          handle: maskEmail(input.email),
          source: 'supabase',
          method: 'password',
        },
      };
    } catch {
      return { ok: false, error: 'Could not reach the sign-in service. Please try again.' };
    }
  }
  return { ok: true, session: localSignIn({ role: input.role, method: 'password', contact: input.email }) };
}

/** The social providers our auth surface offers. Microsoft is our label;
 *  Supabase uses "azure" for the same provider — mapped at the boundary below. */
export type OAuthProvider = 'google' | 'apple' | 'microsoft';

/** The provider value Supabase's signInWithOAuth expects for each of ours. */
const SUPABASE_PROVIDER: Record<OAuthProvider, 'google' | 'apple' | 'azure'> = {
  google: 'google',
  apple: 'apple',
  microsoft: 'azure',
};

/** Map one of our provider labels onto Supabase's provider value. Exported so
 *  the mapping is unit-testable (microsoft -> azure) without a live client. */
export function supabaseProvider(provider: OAuthProvider): 'google' | 'apple' | 'azure' {
  return SUPABASE_PROVIDER[provider];
}

/** Continue with an OAuth provider (or degrade to a local session). */
export async function signInWithOAuth(input: {
  provider: OAuthProvider;
  role: Role;
  redirectTo?: string;
}): Promise<AuthResult> {
  const supabase = await getSupabaseClient();
  if (supabase) {
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        // Supabase uses "azure" for Microsoft; map our label at the boundary.
        provider: supabaseProvider(input.provider),
        options: input.redirectTo ? { redirectTo: input.redirectTo } : undefined,
      });
      if (error) return { ok: false, error: error.message };
      // The browser is redirecting to the provider; the session lands on return.
      return { ok: true };
    } catch {
      return { ok: false, error: 'This sign-in is not available yet. Please try another way.' };
    }
  }
  return { ok: true, session: localSignIn({ role: input.role, method: input.provider }) };
}

/** Request a phone OTP (or degrade — the local demo accepts any code). */
export async function requestPhoneOtp(input: { phone: string }): Promise<AuthResult> {
  const supabase = await getSupabaseClient();
  if (supabase) {
    try {
      const { error } = await supabase.auth.signInWithOtp({ phone: input.phone });
      if (error) return { ok: false, error: error.message };
      return { ok: true };
    } catch {
      return { ok: false, error: 'Could not send a code. Please try again.' };
    }
  }
  // Demo: no code is actually sent; the verify step accepts any value.
  return { ok: true };
}

/** Verify a phone OTP (or degrade to a local session, accepting any code). */
export async function verifyPhoneOtp(input: {
  phone: string;
  code: string;
  role: Role;
}): Promise<AuthResult> {
  const supabase = await getSupabaseClient();
  if (supabase) {
    try {
      const { data, error } = await supabase.auth.verifyOtp({
        phone: input.phone,
        token: input.code,
        type: 'sms',
      });
      if (error) return { ok: false, error: error.message };
      const user = data.user;
      if (!user) return { ok: false, error: 'That code did not match. Please try again.' };
      return {
        ok: true,
        session: {
          userId: user.id,
          handle: maskContact(input.phone),
          source: 'supabase',
          method: 'phone-otp',
        },
      };
    } catch {
      return { ok: false, error: 'Could not verify that code. Please try again.' };
    }
  }
  return { ok: true, session: localSignIn({ role: input.role, method: 'phone-otp', contact: input.phone }) };
}

/**
 * Request a password-reset email. On Supabase this sends the reset link; on the
 * local degrade it resolves ok with a calm, plain message (nothing is sent).
 */
export async function requestPasswordReset(input: {
  email: string;
  redirectTo?: string;
}): Promise<AuthResult> {
  const supabase = await getSupabaseClient();
  if (supabase) {
    // resetPasswordForEmail is part of the SDK; the narrow shim does not declare
    // it, so guard access defensively to keep both paths type-safe and crash-free.
    const auth = supabase.auth as unknown as {
      resetPasswordForEmail?: (
        email: string,
        options?: { redirectTo?: string },
      ) => Promise<{ error: { message: string } | null }>;
    };
    if (typeof auth.resetPasswordForEmail === 'function') {
      try {
        const { error } = await auth.resetPasswordForEmail(
          input.email,
          input.redirectTo ? { redirectTo: input.redirectTo } : undefined,
        );
        if (error) return { ok: false, error: error.message };
        return { ok: true };
      } catch {
        return { ok: false, error: 'Could not send a reset link. Please try again.' };
      }
    }
  }
  return { ok: true };
}

/**
 * Set a new password for the user in the active recovery session. On Supabase
 * this calls auth.updateUser({ password }); on the local degrade (no provider)
 * it resolves ok with a calm message — nothing is stored, there is no password
 * to change in the demo. Never throws, so the reset form stays calm.
 */
export async function updatePassword(input: { password: string }): Promise<AuthResult> {
  const supabase = await getSupabaseClient();
  if (supabase) {
    try {
      const { error } = await supabase.auth.updateUser({ password: input.password });
      if (error) return { ok: false, error: error.message };
      return { ok: true };
    } catch {
      return { ok: false, error: 'Could not update your password. Please try again.' };
    }
  }
  // Degrade: no provider, no stored password — confirm calmly so the demo flows.
  return { ok: true };
}

/** Sign out of whichever backend is active, clearing the session. */
export async function signOut(): Promise<void> {
  const supabase = await getSupabaseClient();
  if (supabase) {
    try {
      await supabase.auth.signOut();
    } catch {
      // Non-fatal — fall through and clear local state too.
    }
  }
  localSignOut();
}

/**
 * Subscribe to session changes. On the Supabase path it bridges
 * onAuthStateChange; on the local path it bridges the store subscription. Returns
 * an unsubscribe function. Never throws.
 */
export function subscribeToAuth(listener: () => void): () => void {
  // Always bridge the local store subscription (it is the degrade source and is
  // synchronously available). When Supabase is configured, ALSO bridge its async
  // onAuthStateChange — resolved lazily so this function can stay synchronous and
  // return the unsubscribe immediately.
  const unsubStore = subscribeStore(listener);

  let supaUnsub: (() => void) | null = null;
  let cancelled = false;

  if (isSupabaseConfigured()) {
    void getSupabaseClient()
      .then((supabase) => {
        if (cancelled || !supabase) return;
        try {
          const { data } = supabase.auth.onAuthStateChange(() => listener());
          supaUnsub = () => data.subscription.unsubscribe();
        } catch {
          supaUnsub = null;
        }
      })
      .catch(() => undefined);
  }

  return () => {
    cancelled = true;
    unsubStore();
    if (supaUnsub) supaUnsub();
  };
}
