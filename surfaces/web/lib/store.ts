/* ============================================================================
   lib/store.ts — the SSR-safe local persistence layer for the web surface.

   The surface is EMPTY until onboarding. Nothing is seeded: there is no
   account, no institution, no personalization profile until the user creates
   them through the first-run experience. This module is the single, typed,
   versioned home for that local state.

   It is deliberately a thin, swappable interface over localStorage so the live
   path (the gateway + Supabase, env vars named in lib/runtime.ts) can replace
   the storage backend without touching callers. Reads and writes go through the
   StoreAdapter; the default adapter is localStorage, guarded for SSR (Next 15
   renders this on the server first, where no window exists).

   LAWS honoured here:
     - The account id is an OPAQUE, locally-minted canonical_uuid. It is never a
       real personal id. It is clearly labelled a demo identity.
     - NO PII lives in the behavioural / personalization profile. The phone-OTP
       shape mints an opaque id and discards the digits — only a masked hint is
       kept, the way a vault would expose a non-identifying handle.
     - The personalization profile is INFERRED, never interrogated, and is gated
       by a consent tier (DPDP age tier). The profile is only persisted within
       the tier the user consented to.
     - No secret value is read here. No NEXT_PUBLIC leak. No hardcoded keys.
   ============================================================================ */

import type { Role } from './mock';

/** Bump when the persisted shape changes incompatibly; old blobs are dropped. */
export const STORE_VERSION = 1 as const;

/** The single localStorage key. One blob, versioned, behind the adapter. */
export const STORE_KEY = 'clss.web.store.v1';

// ---------------------------------------------------------------------------
// Consent + age tier (DPDP). Build only the doors the law provides.
// ---------------------------------------------------------------------------

/**
 * The lawful age tier of the account holder. Drives what may be profiled:
 *   - adult          : self-consenting adult (teacher / admin / parent / 18+).
 *   - teen           : 13–17; profiling permitted only within a reduced tier.
 *   - child          : under 13; verifiable parental consent required, the
 *                      narrowest tier — minimal, non-behavioural personalization.
 * A learner is never profiled beyond the tier the law permits.
 */
export type AgeTier = 'adult' | 'teen' | 'child';

/** What the user has consented to. Transparent, revocable, tier-bounded. */
export interface ConsentState {
  /** The lawful age tier captured at onboarding. */
  ageTier: AgeTier;
  /** Personalization (inferred interests/pace) — the core profiling consent. */
  personalization: boolean;
  /** Whether a guardian consent stands behind a minor's profiling. */
  guardianConsent: boolean;
  /** Plain-language tier label shown back to the user. */
  tierLabel: string;
  /** ISO timestamp the consent was last set; supports revocation/audit. */
  decidedAt: string;
}

/** The widest personalization the tier legally permits. */
export function tierAllowsBehavioural(tier: AgeTier): boolean {
  return tier === 'adult' || tier === 'teen';
}

// ---------------------------------------------------------------------------
// Account — a locally-minted opaque demo identity. NEVER real PII.
// ---------------------------------------------------------------------------

export interface Account {
  /** Opaque, locally-minted canonical_uuid. Not a real person id. */
  id: string;
  /** The chosen / inferred role for this account. */
  role: Role;
  /** The sign-in shape used (demo only — no real backend). */
  method: 'phone-otp' | 'google' | 'apple' | 'microsoft';
  /**
   * A NON-identifying masked hint of the phone shape (e.g. "•••• ••12"). We
   * keep only this, the way a vault exposes a handle — the full number is never
   * stored. Absent for the OAuth shapes.
   */
  contactHint?: string;
  /** Clearly labelled: this is a demo identity, not a verified account. */
  demo: true;
  /** ISO timestamp the account was minted. */
  createdAt: string;
}

// ---------------------------------------------------------------------------
// Onboarding state — drives first-run detection and resumability.
// ---------------------------------------------------------------------------

export type OnboardingStep =
  | 'welcome'
  | 'sign-in'
  | 'role'
  | 'discover'
  | 'consent'
  | 'finish'
  | 'done';

export interface OnboardingState {
  /** True once the whole flow has completed at least once. */
  completed: boolean;
  /** Where the user is in the flow (supports resume after a reload). */
  step: OnboardingStep;
  /** The natural choices the user made — the raw signal personalization infers from. */
  choices: OnboardingChoices;
}

/**
 * The natural, implicit choices captured during the conversational first-run.
 * These are NOT a questionnaire: each is a single tap on a calm chip or card.
 * Personalization is inferred from these plus the role — never from a form
 * asking the learner to declare interests, likes, or dislikes.
 */
export interface OnboardingChoices {
  /** "What brings you in today" — a single intent chip. */
  intent?: string;
  /** A subject the user found interesting enough to tap. */
  subject?: string;
  /** A goal chip the user chose. */
  goal?: string;
  /** How fast they want to move — inferred from a pace chip. */
  pace?: PreferredPace;
}

export type PreferredPace = 'steady' | 'brisk' | 'deep';

// ---------------------------------------------------------------------------
// The inferred personalization profile — built, never asked.
// ---------------------------------------------------------------------------

/**
 * The personalization profile. Mirrors the inference principles of the Python
 * personalization engine (infer, never interrogate; gate by consent/age tier).
 * It carries NO PII — only behavioural preference signal, tied to the opaque
 * account id, and only ever within the consented tier.
 */
export interface PersonalizationProfile {
  /** Inferred interest tags (e.g. "patterns", "real-world", "stories"). */
  interests: string[];
  /** Subjects the user leaned toward, most-preferred first. */
  preferredSubjects: string[];
  /** The single goal the experience is shaped around. */
  goal?: string;
  /** Inferred pace. */
  pace: PreferredPace;
  /**
   * A confidence band on the inference itself — low at first run, it grows as
   * real behaviour accrues. Never shown as a number to a learner.
   */
  confidence: 'low' | 'middle' | 'high';
  /** The tier the profile was built within; profiling never exceeds it. */
  tier: AgeTier;
  /** ISO timestamp of the last inference pass. */
  updatedAt: string;
}

// ---------------------------------------------------------------------------
// Institution + structure + roster — the persistent school setup.
// ---------------------------------------------------------------------------

/** A leaf section within the structure tree (group -> grade -> section). */
export interface SectionNode {
  id: string;
  name: string;
  /** Section teacher's generic role label (never a real name). */
  teacherLabel?: string;
}

/** A grade level holding sections. */
export interface GradeNode {
  id: string;
  name: string;
  sections: SectionNode[];
}

/** A top-level group (campus / wing). */
export interface GroupNode {
  id: string;
  name: string;
  grades: GradeNode[];
}

/** A starter roster member — a generic label, never a real personal name. */
export interface RosterMember {
  id: string;
  /** Generic label, e.g. "Student A", "Teacher 1". */
  label: string;
  kind: 'student' | 'teacher';
  /** The section id this member sits in. */
  sectionId: string;
}

/** The institution created during admin setup. */
export interface Institution {
  id: string;
  name: string;
  /** Board label — a field, never a baked-in lock-in. */
  board: string;
  /** Pacing approach captured in the policy step. */
  pacing: string;
  createdAt: string;
  /**
   * The LIVE operational institution_id returned by /api/school once the
   * blueprint persists to Supabase. Opaque. Absent on the degraded (no-db)
   * path; when present, surfaces reload the school live and it survives a
   * refresh. Never a real personal id.
   */
  liveId?: string;
}

/** The whole school setup blueprint, persisted across reload. */
export interface SchoolSetup {
  institution: Institution;
  structure: GroupNode[];
  roster: RosterMember[];
  /** True once the human confirmed the blueprint (never auto-committed). */
  confirmed: boolean;
}

// ---------------------------------------------------------------------------
// The whole persisted shape.
// ---------------------------------------------------------------------------

export interface StoreState {
  version: typeof STORE_VERSION;
  account: Account | null;
  onboarding: OnboardingState;
  consent: ConsentState | null;
  profile: PersonalizationProfile | null;
  school: SchoolSetup | null;
  /**
   * The persisted UI locale (multilingual-by-design law). Captured implicitly in
   * onboarding/personalise and changeable in settings. A parent reads in their
   * chosen language; subject terminology is never altered by translation.
   * Undefined means "follow the default (English)".
   */
  locale?: string;
  /**
   * How Vidya helps you — calm, plain switches set in Settings. Persisted so the
   * choice survives reload. Undefined fields follow their sensible defaults
   * (voice + proactive on; sharing reads off).
   */
  preferences?: Preferences;
  /**
   * Admin governance configuration the control-centre persists: which agents are
   * enabled, and the active policy versions. A map of opaque id -> boolean (agent
   * enabled) and id -> version label (policy in force). Undefined entries follow
   * their declared defaults so an un-touched control-centre reads its baseline.
   * Survives reload — admin config is real configuration, not session state.
   */
  adminConfig?: AdminConfig;
}

/** Admin governance configuration, persisted across reload. */
export interface AdminConfig {
  /** Agent id -> enabled. Absent means "follow the agent's declared default". */
  agents?: Record<string, boolean>;
  /** Policy id -> the version label set in force. Absent means the latest. */
  policyVersions?: Record<string, string>;
}

/** User-facing behaviour switches, all explicit and revocable. */
export interface Preferences {
  voice: boolean;
  proactive: boolean;
  shareReads: boolean;
}

export function defaultPreferences(): Preferences {
  return { voice: true, proactive: true, shareReads: false };
}

/** The empty initial state — the app is empty until onboarding. */
export function emptyState(): StoreState {
  return {
    version: STORE_VERSION,
    account: null,
    onboarding: {
      completed: false,
      step: 'welcome',
      choices: {},
    },
    consent: null,
    profile: null,
    school: null,
    locale: undefined,
    preferences: undefined,
  };
}

/** Persist a behaviour preference. Survives reload; read in Settings + the orb. */
export function setPreference(key: keyof Preferences, value: boolean): void {
  updateStore((s) => ({
    ...s,
    preferences: { ...defaultPreferences(), ...s.preferences, [key]: value },
  }));
}

/** Persist the chosen UI locale. Survives reload; read by the LocaleProvider. */
export function setLocale(locale: string): void {
  updateStore((s) => ({ ...s, locale }));
}

/** Persist an agent's enabled state (admin control-centre). Survives reload. */
export function setAgentEnabled(agentId: string, enabled: boolean): void {
  updateStore((s) => ({
    ...s,
    adminConfig: {
      ...s.adminConfig,
      agents: { ...s.adminConfig?.agents, [agentId]: enabled },
    },
  }));
}

/** Persist the policy version set in force (admin governance). Survives reload. */
export function setPolicyVersion(policyId: string, version: string): void {
  updateStore((s) => ({
    ...s,
    adminConfig: {
      ...s.adminConfig,
      policyVersions: { ...s.adminConfig?.policyVersions, [policyId]: version },
    },
  }));
}

// ---------------------------------------------------------------------------
// First-run detection — the routing predicate.
// ---------------------------------------------------------------------------

/**
 * The app is in first-run (route to onboarding) when there is no account AND no
 * institution. Either one existing means the user has been here before. The
 * admin can create a school without a personal onboarding, and a learner can
 * onboard without a school — neither path is a dead end.
 */
export function isFirstRun(state: StoreState): boolean {
  return state.account === null && state.school === null;
}

// ---------------------------------------------------------------------------
// Opaque id minting — locally generated canonical_uuid. Never real PII.
// ---------------------------------------------------------------------------

/** Mint a v4-shaped opaque id. Uses crypto.randomUUID when present. */
export function mintId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
  } catch {
    // fall through to the manual shape below
  }
  // Manual v4-shaped fallback (test/SSR environments without crypto.randomUUID).
  const hex = '0123456789abcdef';
  let out = '';
  for (let i = 0; i < 36; i += 1) {
    if (i === 8 || i === 13 || i === 18 || i === 23) out += '-';
    else if (i === 14) out += '4';
    else if (i === 19) out += hex[(Math.floor(Math.random() * 4) + 8) | 0];
    else out += hex[Math.floor(Math.random() * 16)];
  }
  return out;
}

/**
 * Derive a STABLE, deterministic v4-shaped opaque id from a seed string. The
 * same seed always yields the same id, so a conversation keeps one channel ref
 * across every send (and across reloads) — this is what lets the durable
 * history read a thread back. It is NOT random and NOT PII: it is a pure hash of
 * the opaque seed, shaped like a uuid so it satisfies the routes' uuid guard and
 * the channels FK. Uses a small FNV-style mix so it is identical in the browser,
 * SSR, and tests without needing crypto.subtle.
 */
export function channelRef(seed: string): string {
  // Build 16 deterministic bytes from the seed with a rolling FNV-1a mix. A typed
  // Uint8Array keeps indexed access as a number and self-wraps modulo 256.
  const bytes = new Uint8Array(16);
  let h = 0x811c9dc5;
  for (let i = 0; i < seed.length; i += 1) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
    const a = i % 16;
    const b = (i + 7) % 16;
    bytes[a] = (bytes[a]! + (h & 0xff)) & 0xff;
    // Stir each step into the whole array so short seeds still spread out.
    bytes[b] = (bytes[b]! ^ ((h >>> 8) & 0xff)) & 0xff;
  }
  // Fold the final accumulator across every byte so empty/short seeds differ.
  for (let i = 0; i < 16; i += 1) {
    h = Math.imul(h ^ (i + 1), 0x01000193) >>> 0;
    bytes[i] = (bytes[i]! ^ (h & 0xff)) & 0xff;
  }
  // Stamp the v4 version + RFC-4122 variant bits so it is a well-formed uuid.
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'));
  return (
    `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-` +
    `${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10, 16).join('')}`
  );
}

/**
 * Turn a raw phone shape into a NON-identifying masked hint. We keep only the
 * last two visible glyphs, the way a vault exposes a handle. The full input is
 * never stored. An empty/odd input yields a neutral masked placeholder.
 */
export function maskContact(raw: string): string {
  const digits = raw.replace(/\D/g, '');
  if (digits.length < 2) return '•••• ••••';
  return `•••• ••${digits.slice(-2)}`;
}

// ---------------------------------------------------------------------------
// The storage adapter — the swappable seam.
// ---------------------------------------------------------------------------

export interface StoreAdapter {
  read(): StoreState;
  write(state: StoreState): void;
  clear(): void;
}

/** A no-op adapter for SSR / environments without storage. Always empty. */
function memoryAdapter(): StoreAdapter {
  let state = emptyState();
  return {
    read: () => state,
    write: (next) => {
      state = next;
    },
    clear: () => {
      state = emptyState();
    },
  };
}

/** The minimal Storage shape we depend on — Web Storage compatible. */
export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

/** Resolve the ambient localStorage, or null when unavailable (SSR/private). */
function ambientStorage(): StorageLike | null {
  try {
    if (typeof globalThis !== 'undefined') {
      const g = globalThis as { localStorage?: StorageLike };
      if (g.localStorage) return g.localStorage;
    }
  } catch {
    // Access can throw under strict privacy modes.
  }
  return null;
}

/**
 * The default localStorage-backed adapter, SSR-safe. Accepts an explicit
 * Storage-like object (handy for tests and the future gateway path); falls back
 * to the ambient localStorage, and to an in-memory adapter when none exists.
 */
export function localStorageAdapter(storage?: StorageLike): StoreAdapter {
  const store = storage ?? ambientStorage();
  if (!store) return memoryAdapter();

  // Snapshot cache: read() must return a STABLE reference until the underlying
  // blob changes, or useSyncExternalStore (lib/useStore) treats every render as
  // a store change and spins into an infinite update loop. We key the cache on
  // the raw string — it only changes on write — so repeated reads return the
  // identical object.
  let cache: { raw: string | null; state: StoreState } | null = null;

  function parse(raw: string | null): StoreState {
    if (!raw) return emptyState();
    try {
      const parsed = JSON.parse(raw) as Partial<StoreState>;
      // Drop an incompatible older blob rather than crash on it.
      if (!parsed || parsed.version !== STORE_VERSION) return emptyState();
      return { ...emptyState(), ...parsed } as StoreState;
    } catch {
      return emptyState();
    }
  }

  return {
    read(): StoreState {
      let raw: string | null = null;
      try {
        raw = store.getItem(STORE_KEY);
      } catch {
        raw = null;
      }
      if (cache && cache.raw === raw) return cache.state;
      const state = parse(raw);
      cache = { raw, state };
      return state;
    },
    write(state: StoreState) {
      try {
        const raw = JSON.stringify(state);
        store.setItem(STORE_KEY, raw);
        // Keep the cache coherent so the next read returns this exact state.
        cache = { raw, state };
      } catch {
        // Quota / private mode — non-fatal; in-memory state still stands.
      }
    },
    clear() {
      try {
        store.removeItem(STORE_KEY);
      } catch {
        // Non-fatal.
      }
      cache = null;
    },
  };
}

/** A simple in-memory Storage-like, for tests and environments without one. */
export function createMemoryStorage(): StorageLike {
  const map = new Map<string, string>();
  return {
    getItem: (k) => (map.has(k) ? map.get(k)! : null),
    setItem: (k, v) => {
      map.set(k, v);
    },
    removeItem: (k) => {
      map.delete(k);
    },
  };
}

// The module-level adapter. Swappable for tests and the future gateway path.
let adapter: StoreAdapter = localStorageAdapter();

// ---------------------------------------------------------------------------
// Subscription — lets the React hook re-render on any write, across components.
// ---------------------------------------------------------------------------

type Listener = () => void;
const listeners = new Set<Listener>();

/** Subscribe to store changes. Returns an unsubscribe function. */
export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function notify(): void {
  for (const l of listeners) l();
}

/** Replace the storage adapter (tests / the future gateway path). */
export function setStoreAdapter(next: StoreAdapter): void {
  adapter = next;
}

/** A fresh in-memory adapter, handy for isolated tests. */
export function createMemoryAdapter(): StoreAdapter {
  return memoryAdapter();
}

// ---------------------------------------------------------------------------
// Read / write helpers — the imperative surface used by callers and the hook.
// ---------------------------------------------------------------------------

/** Read the whole persisted state. Always returns a value (never throws). */
export function readStore(): StoreState {
  return adapter.read();
}

/** Replace the whole state. */
export function writeStore(state: StoreState): void {
  adapter.write(state);
  notify();
}

/** Apply a pure updater to the current state and persist the result. */
export function updateStore(updater: (state: StoreState) => StoreState): StoreState {
  const next = updater(readStore());
  writeStore(next);
  return next;
}

/** Clear all local state — the sign-out / re-onboard reset. */
export function clearStore(): void {
  adapter.clear();
  notify();
}

// ---------------------------------------------------------------------------
// Domain write helpers — small, intent-named mutations the flows call.
// ---------------------------------------------------------------------------

/** Mint and persist a demo account from the sign-in shape. */
export function signIn(input: {
  role: Role;
  method: Account['method'];
  contactRaw?: string;
}): Account {
  const account: Account = {
    id: mintId(),
    role: input.role,
    method: input.method,
    contactHint: input.contactRaw ? maskContact(input.contactRaw) : undefined,
    demo: true,
    createdAt: new Date().toISOString(),
  };
  updateStore((s) => ({ ...s, account }));
  return account;
}

/** Sign out — clears the local account and everything tied to it. */
export function signOut(): void {
  clearStore();
}

/** Set / update the account role (when role is chosen after sign-in). */
export function setAccountRole(role: Role): void {
  updateStore((s) => (s.account ? { ...s, account: { ...s.account, role } } : s));
}

/** Advance / set the onboarding step. */
export function setOnboardingStep(step: OnboardingStep): void {
  updateStore((s) => ({ ...s, onboarding: { ...s.onboarding, step } }));
}

/** Merge a natural choice into the onboarding signal. */
export function recordChoice(patch: Partial<OnboardingChoices>): void {
  updateStore((s) => ({
    ...s,
    onboarding: { ...s.onboarding, choices: { ...s.onboarding.choices, ...patch } },
  }));
}

/** Record the consent decision (tier-bounded, revocable). */
export function setConsent(consent: ConsentState): void {
  updateStore((s) => ({ ...s, consent }));
}

/**
 * Persist the inferred personalization profile — ONLY within the consented
 * tier. If personalization consent is absent or off, the profile is cleared,
 * never written. This is the storage-level enforcement of the consent gate.
 */
export function setProfile(profile: PersonalizationProfile, consent: ConsentState): void {
  updateStore((s) => {
    if (!consent.personalization) return { ...s, profile: null, consent };
    return { ...s, profile, consent };
  });
}

/** Mark onboarding complete and land the (now personalised) user. */
export function completeOnboarding(): void {
  updateStore((s) => ({
    ...s,
    onboarding: { ...s.onboarding, completed: true, step: 'done' },
  }));
}

/** Reset onboarding so it can be re-run from settings (keeps the account). */
export function restartOnboarding(): void {
  updateStore((s) => ({
    ...s,
    onboarding: { completed: false, step: 'welcome', choices: {} },
  }));
}

/** Persist the school setup blueprint (admin setup wizard). */
export function saveSchool(school: SchoolSetup): void {
  updateStore((s) => ({ ...s, school }));
}

/** Remove the school setup (start the blueprint over). */
export function clearSchool(): void {
  updateStore((s) => ({ ...s, school: null }));
}

/**
 * Stamp the LIVE operational institution_id onto the saved blueprint after it
 * persists to Supabase via /api/school. No-op when there is no school yet.
 * This is what lets surfaces reload the school live and survive a refresh.
 */
export function setSchoolLiveId(liveId: string): void {
  updateStore((s) =>
    s.school
      ? { ...s, school: { ...s.school, institution: { ...s.school.institution, liveId } } }
      : s,
  );
}

// ---------------------------------------------------------------------------
// The inference rule — infer, never interrogate; gate by consent/age tier.
// ---------------------------------------------------------------------------

/** Map an intent chip to interest tags. Plain, board-agnostic. */
const INTENT_INTERESTS: Record<string, string[]> = {
  'Catch up on something': ['foundations', 'steady-support'],
  'Get ahead': ['challenge', 'depth'],
  'Just exploring': ['breadth', 'curiosity'],
  'Prepare for a test': ['focus', 'recall'],
  'Help my class': ['planning', 'class-read'],
  'Set up my school': ['structure', 'governance'],
  'See how my child is doing': ['care', 'plain-language'],
};

/** Map a goal chip to interest tags. */
const GOAL_INTERESTS: Record<string, string[]> = {
  'Build strong foundations': ['foundations'],
  'Reach independence': ['independence'],
  'Enjoy the subject': ['curiosity', 'real-world'],
  'Master the basics fast': ['recall', 'brisk'],
};

/**
 * Build the initial personalization profile from the natural onboarding choices
 * and the role — WITHOUT any explicit profile question. Gated by the consent
 * tier: a behavioural profile is only built when the tier permits it; a child
 * tier yields a minimal, non-behavioural profile (subjects only, no interests).
 *
 * This mirrors the Python personalization engine's principles: infer from
 * choices + behaviour, never interrogate, and never exceed the lawful tier.
 */
export function inferProfile(
  choices: OnboardingChoices,
  consent: ConsentState,
): PersonalizationProfile {
  const behavioural = tierAllowsBehavioural(consent.ageTier) && consent.personalization;

  const interests = new Set<string>();
  if (behavioural) {
    if (choices.intent) (INTENT_INTERESTS[choices.intent] ?? []).forEach((t) => interests.add(t));
    if (choices.goal) (GOAL_INTERESTS[choices.goal] ?? []).forEach((t) => interests.add(t));
  }

  const preferredSubjects = choices.subject ? [choices.subject] : [];
  const pace: PreferredPace = choices.pace ?? (choices.intent === 'Get ahead' ? 'brisk' : 'steady');

  // Confidence in the inference starts low at first run; it grows with behaviour.
  // A child tier stays low (minimal signal by design).
  const signals = [choices.intent, choices.subject, choices.goal].filter(Boolean).length;
  const confidence: PersonalizationProfile['confidence'] = !behavioural
    ? 'low'
    : signals >= 3
      ? 'middle'
      : 'low';

  return {
    interests: Array.from(interests),
    preferredSubjects,
    goal: choices.goal,
    pace,
    confidence,
    tier: consent.ageTier,
    updatedAt: new Date().toISOString(),
  };
}

/**
 * A calm, plain-language line summarising what was inferred — Vidya speaks this
 * at the finish, having asked no explicit profile question. Never a number.
 */
export function profileSummaryLine(profile: PersonalizationProfile | null): string {
  if (!profile) {
    return 'I have set up a calm space for you. We can shape it together as we go.';
  }
  const subject = profile.preferredSubjects[0];
  if (subject && profile.goal) {
    return `I have set you up around ${subject}, with a focus on ${profile.goal.toLowerCase()}.`;
  }
  if (subject) {
    return `I have set you up around ${subject}. We can widen it whenever you like.`;
  }
  if (profile.goal) {
    return `I have shaped things around your goal to ${profile.goal.toLowerCase()}.`;
  }
  return 'I have set up a calm space for you, ready to grow as we learn what helps.';
}
