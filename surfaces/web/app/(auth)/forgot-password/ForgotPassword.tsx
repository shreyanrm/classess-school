'use client';

/* ============================================================================
   app/(auth)/forgot-password/ForgotPassword.tsx — the calm reset surface.

   A familiar "enter your email and we will send a reset link" card. Wires real
   Supabase password reset when configured; degrades to a calm confirmation in
   the demo. v4: centred card, the Classess mark, sharp corners, no shadows,
   plain language, no emoji. Accessible labels + aria-live status.
   ============================================================================ */

import { useState } from 'react';
import Link from 'next/link';
import { Button, Input } from '@classess/design-system';
import { useRole } from '@/lib/RoleContext';
import { requestPasswordReset } from '@/lib/auth';

export function ForgotPassword() {
  const { role } = useRole();
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.trim()) {
      setError('Enter your email so we can send a reset link.');
      return;
    }
    setBusy(true);
    const redirectTo =
      typeof window !== 'undefined' ? `${window.location.origin}/reset-password` : undefined;
    const result = await requestPasswordReset({ email: email.trim(), redirectTo });
    setBusy(false);
    if (!result.ok) {
      setError(result.error ?? 'Could not send a reset link. Please try again.');
      return;
    }
    setSent(true);
  }

  return (
    <main className="auth-shell" data-surface={role}>
      <div className="auth-card">
        <div className="auth-head">
          <span className="auth-mark" aria-hidden="true">
            C
          </span>
          <h1 className="display-sm auth-title">Reset your password</h1>
          <p className="body-sm muted auth-sub">
            Enter your email and we will send a link to set a new password.
          </p>
        </div>

        {sent ? (
          <p className="body-sm" role="status" aria-live="polite">
            If an account exists for that email, a reset link is on its way. You can close this and
            check your inbox.
          </p>
        ) : (
          <form className="auth-form" onSubmit={submit} noValidate>
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              inputMode="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
            {error ? (
              <p className="auth-error" role="alert" aria-live="polite">
                {error}
              </p>
            ) : null}
            <Button type="submit" variant="accent" disabled={busy}>
              Send reset link
            </Button>
          </form>
        )}

        <p className="auth-switch">
          <Link href="/sign-in" className="auth-link">
            Back to sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
