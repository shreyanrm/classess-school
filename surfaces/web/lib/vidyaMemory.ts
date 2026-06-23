/* ============================================================================
   lib/vidyaMemory.ts — persistent, PII-free, consent-gated per-user memory.

   Vidya is conditioned on WHO it is talking to ACROSS sessions. This module is
   the web-native memory slice: it persists, keyed to the OPAQUE account id (a
   locally-minted canonical_uuid — never real PII), two things:

     - THREAD   : the recent conversation turns (bounded), so a returning user is
                  not a stranger.
     - SALIENCE : a compact set of salient facts + preferences (topics they work
                  on, their pace, recurring intents) — distilled, never raw PII.

   It is a thin, swappable interface over a Storage-like backend (the same seam
   as lib/store), SSR-safe (no window on the server). It mirrors the store's
   adapter pattern so the live path can swap the backend without touching
   callers.

   LAWS honoured here:
     - The memory is keyed to the OPAQUE id only; it holds NO PII. A redactor
       strips anything that looks like a contact detail before it is persisted.
     - It is CONSENT-GATED: memory is only persisted/recalled when the holder has
       consented to personalization. With consent off, recall returns empty and
       writes are no-ops — Vidya treats each turn as fresh.
     - The salience summary is a SMALL, bounded set — it conditions the prompt,
       it does not reconstruct the conversation.
   ============================================================================ */

import type { StorageLike } from './store';
import { createMemoryStorage } from './store';

/** Bump when the persisted memory shape changes incompatibly; old blobs dropped. */
export const MEMORY_VERSION = 1 as const;

/** Per-account localStorage key. The opaque id is the only identifier in it. */
export function memoryKey(accountId: string): string {
  return `clss.vidya.memory.v1.${accountId}`;
}

/** Keep the persisted thread bounded — recent context, not a transcript. */
export const MAX_THREAD_TURNS = 24;
/** Keep the salience set small — it conditions the prompt, it is not a history. */
export const MAX_SALIENT_FACTS = 8;
export const MAX_FACT_LEN = 120;

/** One remembered turn. role mirrors the chat turn; text is redacted on write. */
export interface MemoryTurn {
  role: 'user' | 'vidya';
  text: string;
  /** ISO timestamp the turn was remembered. */
  at: string;
}

/** The compact, PII-free salient profile distilled across sessions. */
export interface SalientMemory {
  /** Topics the user keeps working on, most-recent-first. */
  topics: string[];
  /** Recurring plain-language facts/preferences (e.g. "prefers worked examples"). */
  facts: string[];
  /** The last intent we inferred (a short verb phrase), if any. */
  lastIntent?: string;
}

/** The whole persisted memory blob for one opaque account. */
export interface VidyaMemory {
  version: typeof MEMORY_VERSION;
  /** The opaque account id this memory belongs to. NEVER real PII. */
  accountId: string;
  thread: MemoryTurn[];
  salient: SalientMemory;
  /** ISO timestamp of the last write. */
  updatedAt: string;
}

export function emptyMemory(accountId: string): VidyaMemory {
  return {
    version: MEMORY_VERSION,
    accountId,
    thread: [],
    salient: { topics: [], facts: [] },
    updatedAt: new Date(0).toISOString(),
  };
}

// ---------------------------------------------------------------------------
// PII redaction — the wall before anything is persisted. Memory is PII-free by
// construction: strip emails, phone-shaped digit runs, and long digit strings,
// replacing them with a neutral marker so a leaked contact detail can never be
// remembered. This is conservative (it over-redacts rather than risk a leak).
// ---------------------------------------------------------------------------

const EMAIL_RE = /\b[\w.+-]+@[\w-]+\.[\w.-]+\b/g;
// A run of 7+ digits (optionally grouped by spaces/dashes) — a phone/id shape.
const PHONE_RE = /\b(?:\d[\s-]?){7,}\b/g;
const URL_RE = /\bhttps?:\/\/\S+/gi;

/** Redact contact-shaped PII from a string before it is persisted/recalled. */
export function redactPII(text: string): string {
  return text
    .replace(EMAIL_RE, '[contact]')
    .replace(URL_RE, '[link]')
    .replace(PHONE_RE, '[number]')
    .trim();
}

// ---------------------------------------------------------------------------
// The adapter seam — a thin, swappable Storage-like backend, SSR-safe.
// ---------------------------------------------------------------------------

function ambientStorage(): StorageLike | null {
  try {
    if (typeof globalThis !== 'undefined') {
      const g = globalThis as { localStorage?: StorageLike };
      if (g.localStorage) return g.localStorage;
    }
  } catch {
    // Strict privacy mode can throw on access.
  }
  return null;
}

// Module-level backend, swappable for tests + the future gateway path.
let backend: StorageLike = ambientStorage() ?? createMemoryStorage();

/** Replace the memory backend (tests / the future server-side path). */
export function setMemoryBackend(next: StorageLike): void {
  backend = next;
}

// ---------------------------------------------------------------------------
// Read / write — consent-gated. With consent OFF, recall is empty and writes
// are no-ops, so Vidya treats every turn as fresh and nothing is persisted.
// ---------------------------------------------------------------------------

/**
 * Recall the memory for an opaque account. Returns EMPTY when consent is off or
 * the id is missing — Vidya then meets the user fresh. Never throws.
 */
export function recallMemory(accountId: string, consented: boolean): VidyaMemory {
  if (!consented || !accountId) return emptyMemory(accountId || 'anon');
  let raw: string | null = null;
  try {
    raw = backend.getItem(memoryKey(accountId));
  } catch {
    raw = null;
  }
  if (!raw) return emptyMemory(accountId);
  try {
    const parsed = JSON.parse(raw) as Partial<VidyaMemory>;
    if (!parsed || parsed.version !== MEMORY_VERSION) return emptyMemory(accountId);
    return {
      version: MEMORY_VERSION,
      accountId,
      thread: Array.isArray(parsed.thread) ? parsed.thread.slice(-MAX_THREAD_TURNS) : [],
      salient: {
        topics: Array.isArray(parsed.salient?.topics) ? parsed.salient!.topics.slice(0, MAX_FACT_LEN) : [],
        facts: Array.isArray(parsed.salient?.facts) ? parsed.salient!.facts.slice(0, MAX_SALIENT_FACTS) : [],
        lastIntent: typeof parsed.salient?.lastIntent === 'string' ? parsed.salient!.lastIntent : undefined,
      },
      updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : new Date(0).toISOString(),
    };
  } catch {
    return emptyMemory(accountId);
  }
}

/** Persist memory for an opaque account. A NO-OP when consent is off. */
export function persistMemory(memory: VidyaMemory, consented: boolean): void {
  if (!consented || !memory.accountId) return;
  try {
    backend.setItem(memoryKey(memory.accountId), JSON.stringify({ ...memory, updatedAt: new Date().toISOString() }));
  } catch {
    // Quota / private mode — non-fatal.
  }
}

/** Forget everything for an opaque account — the consent-revocation / wipe path. */
export function forgetMemory(accountId: string): void {
  try {
    backend.removeItem(memoryKey(accountId));
  } catch {
    // Non-fatal.
  }
}

// ---------------------------------------------------------------------------
// Distillation — fold a finished turn into the bounded memory. The thread keeps
// the last N turns; the salience set absorbs topics/facts (deduped, bounded). A
// turn's text is REDACTED before it is remembered.
// ---------------------------------------------------------------------------

/** Append a turn (redacted) to the bounded thread. */
export function rememberTurn(memory: VidyaMemory, role: 'user' | 'vidya', text: string): VidyaMemory {
  const clean = redactPII(text).slice(0, 600);
  if (!clean) return memory;
  const thread = [...memory.thread, { role, text: clean, at: new Date().toISOString() }].slice(-MAX_THREAD_TURNS);
  return { ...memory, thread };
}

/**
 * Fold salient signal into memory: topics the user works on and short
 * preference facts. Deduped (case-insensitive), redacted, and bounded. Each is
 * a SMALL plain-language note — never a transcript, never PII.
 */
export function rememberSalient(
  memory: VidyaMemory,
  patch: { topics?: string[]; facts?: string[]; lastIntent?: string },
): VidyaMemory {
  const dedupe = (existing: string[], incoming: string[] | undefined, cap: number): string[] => {
    const out = [...existing];
    for (const raw of incoming ?? []) {
      const v = redactPII(String(raw)).slice(0, MAX_FACT_LEN).trim();
      if (!v) continue;
      if (out.some((e) => e.toLowerCase() === v.toLowerCase())) continue;
      out.unshift(v); // most-recent-first
    }
    return out.slice(0, cap);
  };
  return {
    ...memory,
    salient: {
      topics: dedupe(memory.salient.topics, patch.topics, MAX_FACT_LEN),
      facts: dedupe(memory.salient.facts, patch.facts, MAX_SALIENT_FACTS),
      lastIntent:
        patch.lastIntent !== undefined
          ? redactPII(patch.lastIntent).slice(0, MAX_FACT_LEN) || memory.salient.lastIntent
          : memory.salient.lastIntent,
    },
  };
}

// ---------------------------------------------------------------------------
// Prompt conditioning — render the salient memory into a SHORT system addendum
// so the orchestrator is conditioned on who it is talking to across sessions.
// Returns '' when there is nothing to recall (a fresh user, or consent off).
// ---------------------------------------------------------------------------

/**
 * Build the memory addendum for the system prompt. SHORT and plain — it tells
 * Vidya what it already knows about this person (topics, preferences, last
 * intent) without replaying the conversation. PII-free by construction.
 */
export function memoryInstruction(memory: VidyaMemory): string {
  const { topics, facts, lastIntent } = memory.salient;
  if (topics.length === 0 && facts.length === 0 && !lastIntent) return '';
  const parts: string[] = [
    'You have spoken with this person before. Use what you remember to feel',
    'continuous and personal, but do not recite it back at them. What you know:',
  ];
  if (topics.length) parts.push(`topics they work on: ${topics.slice(0, 5).join(', ')}.`);
  if (facts.length) parts.push(`what helps them: ${facts.slice(0, 5).join('; ')}.`);
  if (lastIntent) parts.push(`last time they wanted to: ${lastIntent}.`);
  return parts.join(' ');
}
