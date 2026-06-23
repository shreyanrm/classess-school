'use client';

/* ============================================================================
   app/(auth)/AuthForm.tsx — the familiar auth surface, as a STEPPED flow.

   One focused view at a time (like the sign-up flows people already know): each
   screen asks a single thing and slides to the next — role -> email -> password
   for create-account, email -> password for sign in. Enter advances; a back
   control and a small progress row keep it oriented. A phone-OTP path and the
   social buttons are offered on the first view as alternatives.

   The auth LOGIC is unchanged — it still calls lib/auth (real Supabase Auth when
   configured, local-store session otherwise). Only the experience is stepped.
   v4 throughout; accessible labels, focus, aria-live errors; honours reduced
   motion (the slide collapses to a plain swap).
   ============================================================================ */

import { useMemo, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button, Icon, Input } from '@classess/design-system';
import { useRole } from '@/lib/RoleContext';
import { useT } from '@/lib/i18n';
import { Logo } from '@/app/_components/Logo';
import { readStore } from '@/lib/store';
import { ROLE_LABELS, type Role } from '@/lib/mock';
import {
  signInWithPassword,
  signUpWithPassword,
  signInWithOAuth,
  requestPhoneOtp,
  verifyPhoneOtp,
  authConfigured,
  type OAuthProvider,
} from '@/lib/auth';

export type AuthMode = 'sign-in' | 'sign-up';
type Step = 'role' | 'identifier' | 'secret';
const ROLE_ORDER: Role[] = ['student', 'teacher', 'admin', 'parent'];

function GoogleGlyph() {
  return (
    <svg width={18} height={18} viewBox="0 0 18 18" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.02-3.7H.96v2.34A9 9 0 0 0 9 18Z" />
      <path fill="#FBBC05" d="M3.98 10.72a5.4 5.4 0 0 1 0-3.44V4.94H.96a9 9 0 0 0 0 8.12l3.02-2.34Z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.46 3.44 1.35l2.58-2.58A9 9 0 0 0 .96 4.94l3.02 2.34C4.68 5.16 6.66 3.58 9 3.58Z" />
    </svg>
  );
}
function AppleGlyph() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M16.36 12.78c.02 2.46 2.16 3.28 2.18 3.29-.02.06-.34 1.18-1.13 2.33-.68.99-1.39 1.98-2.51 2-1.1.02-1.45-.65-2.71-.65-1.26 0-1.65.63-2.69.67-1.08.04-1.9-1.07-2.59-2.06-1.4-2.02-2.48-5.71-1.04-8.2.71-1.24 1.99-2.02 3.38-2.04 1.06-.02 2.07.71 2.71.71.65 0 1.87-.88 3.15-.75.54.02 2.05.22 3.02 1.64-.08.05-1.8 1.06-1.78 3.16ZM14.3 4.6c.57-.69.95-1.65.85-2.6-.82.03-1.81.55-2.4 1.24-.53.6-.99 1.58-.87 2.51.91.07 1.85-.46 2.42-1.15Z" />
    </svg>
  );
}
function MicrosoftGlyph() {
  // The Microsoft four-square glyph, in its brand colours. Inline SVG only.
  return (
    <svg width={18} height={18} viewBox="0 0 18 18" aria-hidden="true">
      <rect x={1} y={1} width={7.6} height={7.6} fill="#F25022" />
      <rect x={9.4} y={1} width={7.6} height={7.6} fill="#7FBA00" />
      <rect x={1} y={9.4} width={7.6} height={7.6} fill="#00A4EF" />
      <rect x={9.4} y={9.4} width={7.6} height={7.6} fill="#FFB900" />
    </svg>
  );
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function AuthForm({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const { role: ctxRole, setRole } = useRole();
  const { t } = useT();
  const isSignUp = mode === 'sign-up';
  const configured = authConfigured();

  const steps: Step[] = useMemo(
    () => (isSignUp ? ['role', 'identifier', 'secret'] : ['identifier', 'secret']),
    [isSignUp],
  );
  const [idx, setIdx] = useState(0);
  const step = steps[idx]!;

  const [method, setMethod] = useState<'password' | 'phone'>('password');
  const [role, setLocalRole] = useState<Role>(ctxRole);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A calm farewell after right-to-erasure routes here with ?farewell=1. Read
  // from the URL on the client (no useSearchParams, so no Suspense boundary is
  // required) — purely informational, dismissed by starting to sign in again.
  const [farewell] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return new URLSearchParams(window.location.search).get('farewell') === '1';
  });

  function go(next: number) {
    setError(null);
    setIdx((i) => Math.max(0, Math.min(steps.length - 1, next)));
  }
  function chooseRole(r: Role) {
    setLocalRole(r);
    setRole(r);
    go(idx + 1);
  }
  function landAfter(success: boolean) {
    if (!success) return;
    // Seed the active role from the resolved account so a returning user lands on
    // THEIR surface. Prefer the persisted account role (the source of truth after
    // a restart); fall back to the role chosen in this form.
    const landedRole = readStore().account?.role ?? role;
    setRole(landedRole);
    router.replace(isSignUp ? '/welcome/personalise' : '/');
  }

  async function advance(e?: FormEvent) {
    e?.preventDefault();
    setError(null);

    if (step === 'identifier') {
      if (method === 'password') {
        if (!EMAIL_RE.test(email.trim())) return setError('Enter a valid email address.');
        return go(idx + 1);
      }
      // phone: send the code, then move to the code view
      if (phone.replace(/\D/g, '').length < 4) return setError('Enter a phone number to receive a code.');
      setBusy(true);
      const r = await requestPhoneOtp({ phone });
      setBusy(false);
      if (!r.ok) return setError(r.error ?? 'Could not send a code. Please try again.');
      setOtpSent(true);
      return go(idx + 1);
    }

    if (step === 'secret') {
      setBusy(true);
      if (method === 'phone') {
        if (!otp.trim()) { setBusy(false); return setError('Enter the code you received.'); }
        const r = await verifyPhoneOtp({ phone, code: otp.trim(), role });
        setBusy(false);
        if (!r.ok) return setError(r.error ?? 'That code did not match. Please try again.');
        return landAfter(Boolean(r.session) || !configured);
      }
      if (isSignUp && password.length < 6) { setBusy(false); return setError('Choose a password of at least six characters.'); }
      if (!password) { setBusy(false); return setError('Enter your password.'); }
      const r = isSignUp
        ? await signUpWithPassword({ email: email.trim(), password, role })
        : await signInWithPassword({ email: email.trim(), password, role });
      setBusy(false);
      if (!r.ok) return setError(r.error ?? 'Something went wrong. Please try again.');
      if (r.session || !configured) return landAfter(true);
      return setError('Check your inbox to confirm your email, then sign in.');
    }
  }

  async function oauth(provider: OAuthProvider) {
    setError(null);
    setBusy(true);
    // Mode-aware: only a new account goes through personalise; a returning user
    // lands straight on their role home, never re-onboarding.
    const redirectTo =
      typeof window !== 'undefined'
        ? isSignUp
          ? `${window.location.origin}/welcome/personalise`
          : `${window.location.origin}/`
        : undefined;
    const r = await signInWithOAuth({ provider, role, redirectTo });
    setBusy(false);
    // Until a provider is enabled in Supabase, a click surfaces a calm message
    // rather than crashing the surface.
    if (!r.ok) return setError(r.error ?? 'This sign-in is not available yet. Please try another way.');
    if (r.session) landAfter(true);
  }

  return (
    <main className="auth-shell" data-surface={role}>
      <div className="auth-card auth-stepped">
        <div className="auth-head">
          <Logo width={110} className="auth-logo" />
          <div className="auth-progress" aria-hidden="true">
            {steps.map((s, i) => (
              <span key={s} className={`auth-dot${i === idx ? ' on' : ''}${i < idx ? ' done' : ''}`} />
            ))}
          </div>
        </div>

        {farewell && !isSignUp ? (
          <p className="caption quiet auth-note" data-testid="auth-farewell" role="status">
            Your account has been deleted. Your identity and personal details are erased; your
            anonymised learning history is retained. You are welcome back any time.
          </p>
        ) : null}

        <form className="auth-steps" onSubmit={advance} noValidate>
          {/* one focused view per step; key re-mounts to replay the slide */}
          <div className="auth-step" key={`${step}-${method}`} data-testid="auth-step" data-step={step}>
            {step === 'role' ? (
              <>
                <h1 className="display-sm auth-title">{t('auth.role.title')}</h1>
                <p className="body-sm muted auth-sub">{t('auth.role.sub')}</p>
                <div className="auth-role-stack" role="radiogroup" aria-label={t('auth.role.legend')}>
                  {ROLE_ORDER.map((r) => (
                    <button key={r} type="button" role="radio" aria-checked={role === r}
                      className={`auth-role-row${role === r ? ' selected' : ''}`} onClick={() => chooseRole(r)}>
                      <span>{ROLE_LABELS[r]}</span>
                      <Icon name="chevron-right" size="sm" />
                    </button>
                  ))}
                </div>
              </>
            ) : null}

            {step === 'identifier' ? (
              <>
                <h1 className="display-sm auth-title">
                  {isSignUp ? t('auth.identifier.titleSignUp') : t('auth.identifier.titleSignIn')}
                </h1>
                <p className="body-sm muted auth-sub">
                  {method === 'phone' ? t('auth.identifier.subPhone') : isSignUp ? t('auth.identifier.subSignUp') : t('auth.identifier.subSignIn')}
                </p>
                {method === 'password' ? (
                  <Input label={t('auth.email.label')} type="email" autoComplete="email" inputMode="email" autoFocus
                    value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
                ) : (
                  <Input label={t('auth.phone.label')} type="tel" autoComplete="tel" inputMode="tel" autoFocus
                    value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Your phone number" />
                )}
              </>
            ) : null}

            {step === 'secret' ? (
              <>
                <h1 className="display-sm auth-title">
                  {method === 'phone' ? t('auth.secret.titlePhone') : isSignUp ? t('auth.secret.titleSignUp') : t('auth.secret.titleSignIn')}
                </h1>
                <p className="body-sm muted auth-sub">
                  {method === 'phone' ? `${t('auth.identifier.subPhone')}` : isSignUp ? t('auth.secret.subSignUp') : ''}
                </p>
                {method === 'phone' ? (
                  <Input label="Code" type="text" autoComplete="one-time-code" inputMode="numeric" autoFocus
                    value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="6-digit code" />
                ) : (
                  <div className="auth-password">
                    <Input label={t('auth.password.label')} type={showPassword ? 'text' : 'password'} autoFocus
                      autoComplete={isSignUp ? 'new-password' : 'current-password'}
                      value={password} onChange={(e) => setPassword(e.target.value)}
                      placeholder={isSignUp ? 'At least six characters' : 'Your password'} />
                    <button type="button" className="auth-password-toggle" aria-pressed={showPassword}
                      aria-label={showPassword ? t('auth.password.hide') : t('auth.password.show')} onClick={() => setShowPassword((v) => !v)}>
                      {showPassword ? t('auth.password.hide') : t('auth.password.show')}
                    </button>
                  </div>
                )}
                {!isSignUp && method === 'password' ? (
                  <div className="auth-row-end"><Link href="/forgot-password" className="auth-link">{t('auth.forgot')}</Link></div>
                ) : null}
              </>
            ) : null}

            {error ? <p className="auth-error" role="alert" aria-live="polite">{error}</p> : null}

            {/* the advance control — hidden on the role step (choosing advances) */}
            {step !== 'role' ? (
              <Button type="submit" variant="accent" disabled={busy} className="auth-advance" data-testid="auth-continue">
                {step === 'secret' ? (isSignUp ? t('auth.cta.createAccount') : method === 'phone' ? t('auth.cta.verify') : t('common.signIn')) : t('common.continue')}
                <Icon name="arrow-right" size="sm" />
              </Button>
            ) : null}
          </div>
        </form>

        <div className="auth-foot">
          {idx > 0 ? (
            <button type="button" className="auth-link auth-back" data-testid="auth-back" onClick={() => go(idx - 1)}>
              <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}
                strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
              {t('common.back')}
            </button>
          ) : <span />}

          {/* alternatives only on the first identifier view */}
          {step === 'identifier' ? (
            <div className="auth-alts">
              <button type="button" className="auth-social-btn" data-testid="auth-social-google"
                onClick={() => oauth('google')} disabled={busy}>
                <GoogleGlyph /> Google
              </button>
              <button type="button" className="auth-social-btn" data-testid="auth-social-apple"
                onClick={() => oauth('apple')} disabled={busy}>
                <AppleGlyph /> Apple
              </button>
              <button type="button" className="auth-social-btn" data-testid="auth-social-microsoft"
                onClick={() => oauth('microsoft')} disabled={busy}>
                <MicrosoftGlyph /> Microsoft
              </button>
              <button type="button" className="auth-social-btn"
                onClick={() => { setMethod((m) => (m === 'phone' ? 'password' : 'phone')); setOtpSent(false); setError(null); }} disabled={busy}>
                <Icon name="send" size="sm" /> {method === 'phone' ? 'Email' : 'Phone'}
              </button>
            </div>
          ) : <span />}
        </div>

        <p className="auth-switch">
          {isSignUp ? t('auth.switch.haveAccount') : t('auth.switch.newHere')}{' '}
          <Link href={isSignUp ? '/sign-in' : '/sign-up'} className="auth-link">
            {isSignUp ? t('common.signIn') : t('common.createAccount')}
          </Link>
        </p>

        {!configured ? (
          <p className="caption quiet auth-note">
            {t('auth.demoNote')}
          </p>
        ) : null}
      </div>
    </main>
  );
}
