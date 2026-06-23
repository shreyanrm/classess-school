'use client';

/* ============================================================================
   app/(auth)/reset-password/ResetPassword.tsx — set a new password.

   The destination of the password-reset link. Supabase puts the user into a
   recovery session on arrival (the link carries the token), so this view simply
   asks for a new password and calls lib/auth.updatePassword. With no provider
   (the demo degrade) it confirms calmly — there is no stored password to change.

   Stepped-consistent with AuthForm: one focused card, the Classess mark, sharp
   corners, no shadows, plain language, no emoji. Accessible labels + aria-live.
   ============================================================================ */

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button, Icon, Input } from '@classess/design-system';
import { useRole } from '@/lib/RoleContext';
import { useT } from '@/lib/i18n';
import { Logo } from '@/app/_components/Logo';
import { updatePassword } from '@/lib/auth';

export function ResetPassword() {
  const router = useRouter();
  const { role } = useRole();
  const { t } = useT();
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 6) {
      setError('Choose a password of at least six characters.');
      return;
    }
    setBusy(true);
    const result = await updatePassword({ password });
    setBusy(false);
    if (!result.ok) {
      setError(result.error ?? 'Could not update your password. Please try again.');
      return;
    }
    setDone(true);
  }

  return (
    <main className="auth-shell" data-surface={role}>
      <div className="auth-card">
        <div className="auth-head">
          <Logo width={110} className="auth-logo" />
          <h1 className="display-sm auth-title">{t('auth.reset.title')}</h1>
          <p className="body-sm muted auth-sub">
            {t('auth.reset.sub')}
          </p>
        </div>

        {done ? (
          <>
            <p className="body-sm" role="status" aria-live="polite">
              {t('auth.reset.done')}
            </p>
            <div className="auth-personalise-actions">
              <Button variant="accent" onClick={() => router.replace('/sign-in')}>
                {t('auth.reset.goSignIn')}
                <Icon name="arrow-right" size="sm" />
              </Button>
            </div>
          </>
        ) : (
          <form className="auth-form" onSubmit={submit} noValidate>
            <div className="auth-password">
              <Input
                label={t('auth.reset.newLabel')}
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least six characters"
              />
              <button
                type="button"
                className="auth-password-toggle"
                aria-pressed={showPassword}
                aria-label={showPassword ? t('auth.password.hide') : t('auth.password.show')}
                onClick={() => setShowPassword((v) => !v)}
              >
                {showPassword ? t('auth.password.hide') : t('auth.password.show')}
              </button>
            </div>
            {error ? (
              <p className="auth-error" role="alert" aria-live="polite">
                {error}
              </p>
            ) : null}
            <Button type="submit" variant="accent" disabled={busy}>
              {t('auth.reset.set')}
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
