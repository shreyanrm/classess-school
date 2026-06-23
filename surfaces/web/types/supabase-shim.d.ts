/* ============================================================================
   types/supabase-shim.d.ts — a minimal ambient declaration for
   @supabase/supabase-js.

   The dependency is declared in package.json but the orchestrator installs deps
   AFTER this build step, so this shim lets `npx tsc --noEmit` pass before the
   real package lands. Once @supabase/supabase-js is installed, ITS bundled
   types take precedence and this shim is harmless (it only declares the small
   surface lib/auth.ts + lib/supabaseClient.ts use).

   Kept intentionally narrow and structural — not a vendored copy of the SDK.
   ============================================================================ */

declare module '@supabase/supabase-js' {
  export interface SupabaseUser {
    id: string;
    email?: string | null;
    phone?: string | null;
  }

  export interface SupabaseSession {
    user: SupabaseUser | null;
  }

  export interface SupabaseAuthError {
    message: string;
  }

  export interface SupabaseSubscription {
    unsubscribe: () => void;
  }

  export interface SupabaseAuthClient {
    getSession(): Promise<{ data: { session: SupabaseSession | null } }>;
    signUp(input: {
      email: string;
      password: string;
    }): Promise<{ data: { user: SupabaseUser | null }; error: SupabaseAuthError | null }>;
    signInWithPassword(input: {
      email: string;
      password: string;
    }): Promise<{ data: { user: SupabaseUser | null }; error: SupabaseAuthError | null }>;
    signInWithOAuth(input: {
      provider: 'google' | 'apple' | string;
      options?: { redirectTo?: string };
    }): Promise<{ data: unknown; error: SupabaseAuthError | null }>;
    signInWithOtp(input: { phone: string }): Promise<{ data: unknown; error: SupabaseAuthError | null }>;
    verifyOtp(input: {
      phone: string;
      token: string;
      type: 'sms' | string;
    }): Promise<{ data: { user: SupabaseUser | null }; error: SupabaseAuthError | null }>;
    updateUser(input: {
      password?: string;
      email?: string;
    }): Promise<{ data: { user: SupabaseUser | null }; error: SupabaseAuthError | null }>;
    signOut(): Promise<{ error: SupabaseAuthError | null }>;
    onAuthStateChange(callback: (event: string, session: SupabaseSession | null) => void): {
      data: { subscription: SupabaseSubscription };
    };
  }

  export interface SupabaseClient {
    auth: SupabaseAuthClient;
  }

  export interface SupabaseClientOptions {
    auth?: {
      persistSession?: boolean;
      autoRefreshToken?: boolean;
      detectSessionInUrl?: boolean;
    };
  }

  export function createClient(
    url: string,
    key: string,
    options?: SupabaseClientOptions,
  ): SupabaseClient;
}
