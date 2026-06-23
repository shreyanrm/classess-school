/* ============================================================================
   app/api/messages/route.ts — the LIVE messaging seam over operational.*

   SERVER-ONLY (runtime = 'nodejs'). Persists safety-screened messages into
   operational.messages (the monitored store — no unmonitored channel) through
   the server-only pool (lib/db.ts). The live realtime fan-out runs on the
   public anon Supabase client (lib/realtime.ts); THIS route is the durable
   history behind it, so a reload re-reads the conversation.

     POST  appends a screened message to a channel. The safety verdict
           (flagged / requires_human) travels with the row.
     GET   ?channel_id=...&institution_id=...  reads the channel history back.

   DEGRADE: no CLSS_DATABASE_URL -> 200 { persisted:false } so the surface stays
   on its local thread. sender_ref is opaque, never PII; no secret is returned.
   ============================================================================ */

import { getPool, type PoolLike } from '@/lib/db';
import { ok, degraded, isUuid, str } from '@/lib/opRoute';
import { screenText, type SafetyVerdict } from '@/lib/childSafetyServer';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface Body {
  institutionId?: string;
  channelId?: string;
  senderRef?: string;
  body?: string;
  flagged?: boolean;
  requiresHuman?: boolean;
}

async function appendMessage(pool: PoolLike, body: Body, screened: SafetyVerdict): Promise<string | null> {
  // The REAL verdict travels with the row — never a hard-coded flagged:false. A
  // crisis or harassment is flagged and held for a human; nothing posts to an
  // unmonitored channel (this store IS the monitored one).
  const flagged = screened.flagged;
  const requiresHuman = screened.escalate || screened.flagged;
  const verdict = JSON.stringify({
    flagged,
    requires_human: requiresHuman,
    escalate: screened.escalate,
    category: screened.category,
    screened: true,
  });
  const res = await pool.query<{ message_id: string }>(
    `INSERT INTO operational.messages
       (institution_id, channel_id, sender_ref, body, safety_verdict, flagged, requires_human)
     VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)
     RETURNING message_id`,
    [
      body.institutionId,
      isUuid(body.channelId) ? body.channelId : null,
      body.senderRef,
      str(body.body).slice(0, 4000),
      verdict,
      flagged,
      requiresHuman,
    ],
  );
  return res.rows[0]?.message_id ?? null;
}

export async function POST(req: Request): Promise<Response> {
  let body: Body;
  try {
    body = (await req.json()) as Body;
  } catch {
    return ok({ persisted: false, reason: 'bad-request' }, 400);
  }
  if (!isUuid(body.institutionId) || !isUuid(body.senderRef) || !str(body.body)) {
    return ok({ persisted: false, reason: 'invalid-input' }, 400);
  }

  // CHILD-SAFETY runs on the server BEFORE anything persists. The real verdict
  // (not a hard-coded flagged:false) decides whether the message holds for a
  // responsible adult and whether a crisis routes/escalates to a human. A crisis
  // is never silenced: it is held + escalated, and the verdict travels back so
  // the surface shows a calm supportive response.
  const screened = await screenText(str(body.body));

  const pool = getPool();
  if (!pool) {
    // No durable store: still return the safety verdict so the surface can hold,
    // flag, and escalate locally — a crisis is never silenced by a missing db.
    return degraded({
      flagged: screened.flagged,
      escalate: screened.escalate,
      requiresHuman: screened.escalate || screened.flagged,
      category: screened.category,
      support: screened.support,
    });
  }

  try {
    const id = await appendMessage(pool, body, screened);
    return ok({
      persisted: Boolean(id),
      id: id ?? undefined,
      flagged: screened.flagged,
      escalate: screened.escalate,
      requiresHuman: screened.escalate || screened.flagged,
      category: screened.category,
      support: screened.support,
    });
  } catch {
    return ok({
      persisted: false,
      reason: 'write-failed',
      flagged: screened.flagged,
      escalate: screened.escalate,
      category: screened.category,
      support: screened.support,
    });
  }
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const channelId = str(url.searchParams.get('channel_id'));
  const institutionId = str(url.searchParams.get('institution_id'));
  if (!isUuid(channelId) || !isUuid(institutionId)) {
    return ok({ persisted: false, rows: [], reason: 'invalid-input' }, 400);
  }

  const pool = getPool();
  if (!pool) return degraded();

  try {
    const res = await pool.query(
      `SELECT message_id, sender_ref, body, flagged, requires_human, posted_at
         FROM operational.messages
        WHERE institution_id = $1 AND channel_id = $2
        ORDER BY posted_at`,
      [institutionId, channelId],
    );
    return ok({ persisted: true, rows: res.rows });
  } catch {
    return ok({ persisted: false, rows: [], reason: 'read-failed' });
  }
}
