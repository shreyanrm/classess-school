/* ============================================================================
   lib/opRoute.ts — SERVER-ONLY shared helpers for the operational API routes.

   This is imported ONLY by app/api/* route handlers (runtime = 'nodejs'). It
   never reaches a client bundle. It carries no secret of its own — it only
   offers the small, shared validators + response shapers the operational routes
   reuse (school, attendance, coursework, messages), so each route stays small
   and consistent.

   The connection is owned by lib/db.ts; this module never reads the connection
   string and never returns it. Every helper degrades safely.
   ============================================================================ */

const NO_STORE = { 'cache-control': 'no-store' } as const;

/** A calm JSON answer with no-store (operational reads/writes are dynamic). */
export function ok(body: Record<string, unknown>, status = 200): Response {
  return Response.json(body, { status, headers: NO_STORE });
}

/** The shared degraded answer when no live database is configured. */
export function degraded(extra: Record<string, unknown> = {}): Response {
  return ok({ persisted: false, rows: [], reason: 'no-db', ...extra });
}

/** A defensive uuid check so a malformed ref never reaches the query layer. */
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function isUuid(v: unknown): v is string {
  return typeof v === 'string' && UUID_RE.test(v);
}

/** Trim + coerce to string; returns '' for nullish so callers can guard. */
export function str(v: unknown): string {
  return typeof v === 'string' ? v.trim() : v == null ? '' : String(v).trim();
}

/** Bound a free-text label so a route never stores an unbounded blob. */
export function label(v: unknown, max = 200): string {
  return str(v).slice(0, max);
}
