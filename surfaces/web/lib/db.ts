/* ============================================================================
   lib/db.ts — the SERVER-ONLY Postgres pool for the live event seam.

   This module is the single, guarded door to the platform database (the
   immutable, append-only platform.events store and the governed read function
   platform.read_events). It is imported ONLY by server route handlers
   (app/api/events/route.ts, runtime = 'nodejs'). It MUST NEVER be imported by a
   client component — it reads a server-only secret (process.env.CLSS_DATABASE_URL)
   and holds a live database connection.

   LAWS honoured here:
     - The connection string is read BY NAME from process.env. It is never a
       NEXT_PUBLIC var, never logged, never returned to a caller, never embedded.
     - A MISSING url degrades to null. Importing this module never throws and
       never crashes the build/runtime: the surface keeps working on the local
       store when there is no database (the designed degraded path).
     - 'pg' is imported lazily (require at first use) so a build without the
       dependency installed, or a client bundle that somehow reaches this file,
       never hard-fails at module load.
   ============================================================================ */

/** The env var name the live event seam reads. Server-only. Never NEXT_PUBLIC. */
export const DB_URL_ENV = 'CLSS_DATABASE_URL' as const;

/**
 * The minimal slice of node-postgres we depend on. Declared locally so this
 * module type-checks before `pg` (and @types/pg) are installed — the orchestrator
 * installs dependencies after the build. At runtime the real Pool is used.
 */
export interface QueryResultLike<R = Record<string, unknown>> {
  rows: R[];
  rowCount: number | null;
}

export interface PoolLike {
  query<R = Record<string, unknown>>(
    text: string,
    params?: ReadonlyArray<unknown>,
  ): Promise<QueryResultLike<R>>;
  end(): Promise<void>;
}

// Singleton — one pool per server process. Cached on globalThis so Next's dev
// hot-reload (which re-evaluates modules) does not leak a new pool each reload.
const GLOBAL_KEY = '__clss_pg_pool__';

interface PoolHolder {
  pool: PoolLike | null;
  resolved: boolean;
}

function holder(): PoolHolder {
  const g = globalThis as unknown as Record<string, PoolHolder | undefined>;
  if (!g[GLOBAL_KEY]) g[GLOBAL_KEY] = { pool: null, resolved: false };
  return g[GLOBAL_KEY]!;
}

/**
 * Resolve the singleton Postgres pool, or null when the database is not
 * configured (no CLSS_DATABASE_URL) or `pg` is unavailable. NEVER throws on a
 * missing url or a missing dependency — the caller treats null as "no live
 * persistence" and stays on the local store. The url value is never logged.
 */
export function getPool(): PoolLike | null {
  const h = holder();
  if (h.resolved) return h.pool;
  h.resolved = true;

  const url = process.env[DB_URL_ENV];
  if (!url || url.trim().length === 0) {
    h.pool = null;
    return null;
  }

  try {
    // Lazy require: keeps a build/bundle without `pg` from failing at import.
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require('pg') as { Pool: new (config: { connectionString: string; max?: number; ssl?: unknown }) => PoolLike };
    h.pool = new mod.Pool({
      connectionString: url,
      max: 4,
      // Supabase's pooled connection terminates TLS; accept its managed cert.
      ssl: url.includes('sslmode=disable') ? undefined : { rejectUnauthorized: false },
    });
  } catch {
    // Dependency missing or pool construction failed — degrade, never crash.
    h.pool = null;
  }
  return h.pool;
}

/** True when a live database is configured AND reachable as a pool. */
export function isDbConfigured(): boolean {
  return getPool() !== null;
}

/** Test seam: inject a fake pool (or null) so route logic can be unit-tested
 *  without a real database and without `pg` installed. */
export function __setPoolForTest(pool: PoolLike | null): void {
  const h = holder();
  h.pool = pool;
  h.resolved = true;
}

/** Test seam: reset the resolver so the next getPool() re-reads the env. */
export function __resetPoolForTest(): void {
  const g = globalThis as unknown as Record<string, PoolHolder | undefined>;
  g[GLOBAL_KEY] = { pool: null, resolved: false };
}
