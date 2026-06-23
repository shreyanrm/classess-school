import { AuthForm } from '../AuthForm';

export const metadata = { title: 'Sign in — Classess School' };

/** The familiar sign-in surface. After sign-in, lands straight in the role home. */
export default function SignInPage() {
  return <AuthForm mode="sign-in" />;
}
