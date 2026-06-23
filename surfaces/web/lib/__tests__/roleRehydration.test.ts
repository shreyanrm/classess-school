/* ============================================================================
   lib/__tests__/roleRehydration.test.ts — the role survives a restart.

   The RoleProvider seeds its active role from readStore().account?.role when
   sessionStorage has no role (the post-restart case), and persists every chosen
   role into the SAME localStorage store as the account (via setAccountRole). This
   test locks the durable half of that contract at the store layer: a role written
   through setAccountRole lands in the persisted blob and is read back by a FRESH
   adapter over the same backing storage — i.e. it survives a restart, so a
   returning non-teacher rehydrates to THEIR role, not the hard-coded default.
   ============================================================================ */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  setStoreAdapter,
  localStorageAdapter,
  createMemoryStorage,
  readStore,
  signIn,
  setAccountRole,
  type StorageLike,
} from '../store';

describe('role rehydration — survives a restart via the persisted store', () => {
  let storage: StorageLike;

  beforeEach(() => {
    // One backing storage shared across "sessions"; a fresh adapter each restart.
    storage = createMemoryStorage();
    setStoreAdapter(localStorageAdapter(storage));
  });

  it('persists the chosen role into the account blob and reads it back after a restart', () => {
    // A returning admin signs in, then switches the active role to admin.
    signIn({ role: 'student', method: 'phone-otp' });
    setAccountRole('admin');
    expect(readStore().account?.role).toBe('admin');

    // Simulate a restart: a brand-new adapter over the SAME backing storage. The
    // role is recovered from the persisted account, not the 'teacher' default.
    setStoreAdapter(localStorageAdapter(storage));
    expect(readStore().account?.role).toBe('admin');
  });

  it('does not resurrect a role when there is no account (signed out)', () => {
    // No account: setAccountRole is a no-op, so nothing seeds a stale role.
    setAccountRole('parent');
    expect(readStore().account).toBeNull();
  });
});
