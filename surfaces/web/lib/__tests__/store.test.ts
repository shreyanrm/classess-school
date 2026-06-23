import { describe, it, expect, beforeEach } from 'vitest';
import {
  STORE_KEY,
  STORE_VERSION,
  emptyState,
  isFirstRun,
  readStore,
  writeStore,
  updateStore,
  clearStore,
  setStoreAdapter,
  localStorageAdapter,
  createMemoryStorage,
  type StorageLike,
  mintId,
  maskContact,
  signIn,
  signOut,
  setAccountRole,
  setOnboardingStep,
  recordChoice,
  setConsent,
  setProfile,
  completeOnboarding,
  restartOnboarding,
  saveSchool,
  clearSchool,
  inferProfile,
  profileSummaryLine,
  tierAllowsBehavioural,
  type ConsentState,
  type SchoolSetup,
} from '../store';

function adultConsent(personalization = true): ConsentState {
  return {
    ageTier: 'adult',
    personalization,
    guardianConsent: false,
    tierLabel: 'Adult',
    decidedAt: new Date().toISOString(),
  };
}

// A fresh Storage-like per test, so the adapter is exercised end-to-end without
// depending on the jsdom global (which is not guaranteed across vitest versions).
let mem: StorageLike & { clear: () => void };

function freshStorage(): StorageLike & { clear: () => void } {
  let s = createMemoryStorage();
  return {
    getItem: (k) => s.getItem(k),
    setItem: (k, v) => s.setItem(k, v),
    removeItem: (k) => s.removeItem(k),
    clear: () => {
      s = createMemoryStorage();
    },
  };
}

const SCHOOL: SchoolSetup = {
  institution: {
    id: 'inst-1',
    name: 'Campus North',
    board: 'Example State Board',
    pacing: 'Standard',
    createdAt: new Date().toISOString(),
  },
  structure: [
    { id: 'g1', name: 'Senior wing', grades: [{ id: 'gr1', name: 'Grade 10', sections: [{ id: 's1', name: 'Section A' }] }] },
  ],
  roster: [{ id: 'm1', label: 'Student A', kind: 'student', sectionId: 's1' }],
  confirmed: true,
};

describe('store — localStorage adapter', () => {
  beforeEach(() => {
    mem = freshStorage();
    // Fresh adapter bound to a clean Storage-like each test.
    setStoreAdapter(localStorageAdapter(mem));
  });

  it('starts empty — nothing is seeded', () => {
    const s = readStore();
    expect(s).toEqual(emptyState());
    expect(s.account).toBeNull();
    expect(s.school).toBeNull();
    expect(s.profile).toBeNull();
    expect(s.onboarding.completed).toBe(false);
  });

  it('first-run is true only when there is no account and no school', () => {
    expect(isFirstRun(readStore())).toBe(true);
    signIn({ role: 'student', method: 'phone-otp', contactRaw: '9876543210' });
    expect(isFirstRun(readStore())).toBe(false);
  });

  it('a saved school alone exits first-run (admin path)', () => {
    saveSchool(SCHOOL);
    expect(isFirstRun(readStore())).toBe(false);
  });

  it('persists writes to localStorage under the versioned key', () => {
    writeStore({ ...emptyState(), onboarding: { ...emptyState().onboarding, step: 'role' } });
    const raw = mem.getItem(STORE_KEY);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed.version).toBe(STORE_VERSION);
    expect(parsed.onboarding.step).toBe('role');
  });

  it('updateStore applies a pure updater and persists', () => {
    const next = updateStore((s) => ({ ...s, onboarding: { ...s.onboarding, step: 'consent' } }));
    expect(next.onboarding.step).toBe('consent');
    expect(readStore().onboarding.step).toBe('consent');
  });

  it('clearStore wipes everything', () => {
    signIn({ role: 'teacher', method: 'google' });
    saveSchool(SCHOOL);
    clearStore();
    expect(readStore()).toEqual(emptyState());
    expect(mem.getItem(STORE_KEY)).toBeNull();
  });

  it('drops an incompatible older blob rather than crashing', () => {
    mem.setItem(STORE_KEY, JSON.stringify({ version: 0, account: { id: 'x' } }));
    expect(readStore()).toEqual(emptyState());
  });

  it('survives a corrupt blob (returns empty, never throws)', () => {
    mem.setItem(STORE_KEY, '{not json');
    expect(() => readStore()).not.toThrow();
    expect(readStore()).toEqual(emptyState());
  });
});

describe('store — account is an opaque demo identity, never PII', () => {
  beforeEach(() => {
    mem = freshStorage();
    setStoreAdapter(localStorageAdapter(mem));
  });

  it('mintId yields a v4-shaped opaque id', () => {
    const id = mintId();
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });

  it('signIn keeps only a masked contact hint, never the raw number', () => {
    const acc = signIn({ role: 'student', method: 'phone-otp', contactRaw: '9876543210' });
    expect(acc.demo).toBe(true);
    expect(acc.contactHint).toBe('•••• ••10');
    // The raw number must not appear anywhere in the persisted blob.
    const raw = mem.getItem(STORE_KEY)!;
    expect(raw).not.toContain('9876543210');
    expect(raw).not.toContain('98765');
  });

  it('maskContact never reveals the middle digits', () => {
    expect(maskContact('9876543210')).toBe('•••• ••10');
    expect(maskContact('')).toBe('•••• ••••');
    expect(maskContact('1')).toBe('•••• ••••');
  });

  it('setAccountRole updates the role in place', () => {
    signIn({ role: 'student', method: 'apple' });
    setAccountRole('teacher');
    expect(readStore().account?.role).toBe('teacher');
  });

  it('signOut clears the local account', () => {
    signIn({ role: 'parent', method: 'google' });
    signOut();
    expect(readStore().account).toBeNull();
  });
});

describe('store — onboarding flow state', () => {
  beforeEach(() => {
    mem = freshStorage();
    setStoreAdapter(localStorageAdapter(mem));
  });

  it('records steps and natural choices without a form', () => {
    setOnboardingStep('discover');
    recordChoice({ intent: 'Get ahead' });
    recordChoice({ subject: 'Mathematics' });
    const s = readStore();
    expect(s.onboarding.step).toBe('discover');
    expect(s.onboarding.choices).toEqual({ intent: 'Get ahead', subject: 'Mathematics' });
  });

  it('completeOnboarding marks done; restart resets the flow', () => {
    completeOnboarding();
    expect(readStore().onboarding.completed).toBe(true);
    restartOnboarding();
    const s = readStore();
    expect(s.onboarding.completed).toBe(false);
    expect(s.onboarding.step).toBe('welcome');
    expect(s.onboarding.choices).toEqual({});
  });

  it('restartOnboarding keeps the account (re-run from settings)', () => {
    signIn({ role: 'student', method: 'phone-otp' });
    restartOnboarding();
    expect(readStore().account).not.toBeNull();
  });
});

describe('store — consent gates the personalization profile', () => {
  beforeEach(() => {
    mem = freshStorage();
    setStoreAdapter(localStorageAdapter(mem));
  });

  it('persists a profile only when personalization consent is on', () => {
    const consent = adultConsent(true);
    const profile = inferProfile({ subject: 'Science', goal: 'Enjoy the subject' }, consent);
    setProfile(profile, consent);
    expect(readStore().profile).not.toBeNull();
    expect(readStore().consent?.personalization).toBe(true);
  });

  it('never writes a profile when personalization consent is off', () => {
    const consent = adultConsent(false);
    const profile = inferProfile({ subject: 'Science' }, consent);
    setProfile(profile, consent);
    expect(readStore().profile).toBeNull();
    // The consent decision itself is still recorded (revocable, auditable).
    expect(readStore().consent?.personalization).toBe(false);
  });

  it('setConsent records the decision independently', () => {
    setConsent(adultConsent(true));
    expect(readStore().consent?.tierLabel).toBe('Adult');
  });
});

describe('inferProfile — infer, never interrogate; gated by age tier', () => {
  it('builds behavioural interests for an adult tier', () => {
    const consent = adultConsent(true);
    const profile = inferProfile(
      { intent: 'Get ahead', subject: 'Mathematics', goal: 'Reach independence' },
      consent,
    );
    expect(profile.preferredSubjects).toEqual(['Mathematics']);
    expect(profile.goal).toBe('Reach independence');
    expect(profile.interests.length).toBeGreaterThan(0);
    expect(profile.interests).toContain('independence');
    expect(profile.tier).toBe('adult');
  });

  it('a child tier yields a minimal, non-behavioural profile', () => {
    const consent: ConsentState = {
      ageTier: 'child',
      personalization: true,
      guardianConsent: true,
      tierLabel: 'Child (guardian consent)',
      decidedAt: new Date().toISOString(),
    };
    const profile = inferProfile(
      { intent: 'Just exploring', subject: 'English', goal: 'Enjoy the subject' },
      consent,
    );
    // Subjects (non-behavioural) are kept; behavioural interests are not built.
    expect(profile.preferredSubjects).toEqual(['English']);
    expect(profile.interests).toEqual([]);
    expect(profile.confidence).toBe('low');
    expect(profile.tier).toBe('child');
  });

  it('does not build interests when personalization consent is off', () => {
    const profile = inferProfile({ intent: 'Get ahead', subject: 'Mathematics' }, adultConsent(false));
    expect(profile.interests).toEqual([]);
  });

  it('infers a brisk pace from a get-ahead intent when none chosen', () => {
    const profile = inferProfile({ intent: 'Get ahead' }, adultConsent(true));
    expect(profile.pace).toBe('brisk');
  });

  it('tierAllowsBehavioural is false only for the child tier', () => {
    expect(tierAllowsBehavioural('adult')).toBe(true);
    expect(tierAllowsBehavioural('teen')).toBe(true);
    expect(tierAllowsBehavioural('child')).toBe(false);
  });
});

describe('profileSummaryLine — Vidya speaks what it learned, asked nothing', () => {
  it('references subject and goal without a number', () => {
    const consent = adultConsent(true);
    const profile = inferProfile({ subject: 'Mathematics', goal: 'Build strong foundations' }, consent);
    const line = profileSummaryLine(profile);
    expect(line).toContain('Mathematics');
    expect(/\d/.test(line)).toBe(false);
    expect(line).not.toContain('!');
  });

  it('falls back gracefully with no profile', () => {
    expect(profileSummaryLine(null)).toContain('calm');
  });
});

describe('store — school setup persists across reloads', () => {
  beforeEach(() => {
    mem = freshStorage();
    setStoreAdapter(localStorageAdapter(mem));
  });

  it('saveSchool persists the institution, structure and roster', () => {
    saveSchool(SCHOOL);
    // Simulate a reload: a brand-new adapter reading the same backing store.
    setStoreAdapter(localStorageAdapter(mem));
    const s = readStore();
    expect(s.school?.institution.name).toBe('Campus North');
    expect(s.school?.structure[0]?.grades[0]?.sections[0]?.name).toBe('Section A');
    expect(s.school?.roster).toHaveLength(1);
    expect(s.school?.confirmed).toBe(true);
  });

  it('clearSchool removes the blueprint', () => {
    saveSchool(SCHOOL);
    clearSchool();
    expect(readStore().school).toBeNull();
  });
});
