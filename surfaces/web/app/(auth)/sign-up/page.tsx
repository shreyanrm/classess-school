import { AuthForm } from '../AuthForm';

export const metadata = { title: 'Create account — Classess School' };

/**
 * The familiar create-account surface. After sign-up, lands in a short, optional
 * personalisation step (/welcome/personalise) and then the role home.
 */
export default function SignUpPage() {
  return <AuthForm mode="sign-up" />;
}
