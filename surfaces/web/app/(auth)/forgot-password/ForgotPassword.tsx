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
import { useT } from '@/lib/i18n';
import { Logo } from '@/app/_components/Logo';
import { requestPasswordReset } from '@/lib/auth';

export function ForgotPassword() {
  const { role } = useRole();
  const { t } = useT();
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
          <Logo width={110} className="auth-logo" />
          <h1 className="display-sm auth-title">{t('auth.forgot.title')}</h1>
          <p className="body-sm muted auth-sub">
            {t('auth.forgot.sub')}
          </p>
        </div>

        {sent ? (
          <p className="body-sm" role="status" aria-live="polite">
            {t('auth.forgot.sent')}
          </p>
        ) : (
          <form className="auth-form" onSubmit={submit} noValidate>
            <Input
              label={t('auth.email.label')}
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
              {t('auth.forgot.send')}
            </Button>
          </form>
        )}

        <p className="auth-switch">
          <Link href="/sign-in" className="auth-link">
            {t('auth.forgot.backToSignIn')}
          </Link>
        </p>
      </div>
    </main>
  );
}
