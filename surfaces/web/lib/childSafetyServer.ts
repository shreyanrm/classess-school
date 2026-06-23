/* ============================================================================
   lib/childSafetyServer.ts — the SERVER-ONLY child-safety gate for free text.

   The audit found screening was illustrative: every free-text surface hard-coded
   flagged:false and nothing was ever held, routed, or escalated. This module is
   the real gate. It is SERVER-ONLY: it reads the Gemini key by env NAME (the same
   pattern as lib/vidyaServer — process.env, never returned, never logged, never a
   NEXT_PUBLIC var) and is imported only by server route handlers.

   THE INVARIANT THAT OVERRIDES EVERYTHING: a crisis is NEVER silenced. A message
   that signals self-harm or an acute crisis must flag AND escalate to a human —
   never dropped, never sent to an unmonitored channel. The supportive verdict
   tells the surface to show a calm, human-routed response.

   It returns a calm verdict:
     { allowed, flagged, escalate, category, support }
       - allowed  : may this post to the MONITORED channel as-is.
       - flagged  : held for a responsible adult to review (harassment, etc.).
       - escalate : route to a human NOW (crisis / self-harm). Never auto-silenced.
       - category : the plain-language reason ('crisis' | 'harassment' | 'safe').
       - support  : a calm supportive line to show when escalate is true.

   TWO PATHS, ONE PROMISE:
     1. With a key, it asks Gemini to classify the text (calm, structured JSON).
     2. With NO key (or any provider failure), a DETERMINISTIC keyword fallback
        runs — and the fallback STILL catches a crisis. Safety never depends on a
        provider being reachable; the conservative path still escalates.
   ============================================================================ */

/** The env NAME of the Gemini key — read here, never returned or logged. Same
 *  key the Vidya server core uses; this module reads it by name only. */
export const SAFETY_KEY_ENV = 'CLSS_AIFABRIC_DEV_GEMINI_API_KEY';

const BASE = 'https://generativelanguage.googleapis.com/v1beta/models';
const MODELS = ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.0-flash'];

/** The plain-language category of a screened message. */
export type SafetyCategory = 'safe' | 'harassment' | 'crisis';

/** A calm verdict on one free-text message. Pure data — carries no key, no PII. */
export interface SafetyVerdict {
  /** May this post to the MONITORED channel as written. False when held. */
  allowed: boolean;
  /** Held for a responsible adult to review (harassment / abuse). */
  flagged: boolean;
  /** Route to a human NOW. A crisis is never silenced — this is always honoured. */
  escalate: boolean;
  /** The plain-language reason. */
  category: SafetyCategory;
  /** A calm, supportive line to show the person when a crisis is detected. */
  support?: string;
}

/** The one supportive line shown on a crisis — calm, human-routed, never silencing. */
export const CRISIS_SUPPORT =
  'It sounds like you are going through something really hard. You are not alone, and a person who can help has been notified so they can reach out to you.';

// ---------------------------------------------------------------------------
// Deterministic keyword fallback — the floor that NEVER misses a crisis. This
// runs when there is no key, when the provider fails, or as a safety net union
// alongside the model verdict (the stricter of the two always wins). It is
// intentionally conservative: a phrase that signals self-harm escalates even if
// a model would have shrugged it off. Better a human reviews a false positive
// than a real crisis is silenced.
// ---------------------------------------------------------------------------

/** Crisis / self-harm signals. Matching ANY of these forces escalate=true. */
const CRISIS_PATTERNS: RegExp[] = [
  /\bkill myself\b/i,
  /\bkilling myself\b/i,
  /\bkill me\b/i,
  /\bend (my|it all|my life)\b/i,
  /\bending my life\b/i,
  /\bsuicid/i, // suicide, suicidal
  /\bself[\s-]?harm/i,
  /\bhurt(ing)? myself\b/i,
  /\bcut(ting)? myself\b/i,
  /\bdon'?t want to (live|be alive|be here|wake up)\b/i,
  /\bwant to die\b/i,
  /\bwish (i was|i were) dead\b/i,
  /\bno (reason|point) (to|in) (live|living|going on)\b/i,
  /\bbetter off (without me|dead)\b/i,
  /\bnobody would (miss|care)\b/i,
  /\btake my (own )?life\b/i,
];

/** Harassment / abuse signals. Matching forces flagged=true (held for review). */
const HARASSMENT_PATTERNS: RegExp[] = [
  /\bi('| wi)?ll (hurt|beat|find|get) you\b/i,
  /\bi('| wi)?ll kill you\b/i,
  /\b(kill|hurt|beat) yourself\b/i,
  /\bgo (and )?(die|kill yourself)\b/i,
  /\byou('| a)?re (worthless|pathetic|a loser|stupid|an idiot|ugly|trash)\b/i,
  /\bnobody likes you\b/i,
  /\beveryone hates you\b/i,
  /\bshut up\b.*\b(loser|idiot|stupid)\b/i,
  /\b(stupid|ugly|fat|dumb)\s+(idiot|loser|freak)\b/i,
  /\bi('| wi)?ll (ruin|destroy) you\b/i,
];

/** The deterministic floor. Always available, never throws, never silences a
 *  crisis. Returns the conservative verdict for a piece of free text. */
export function keywordVerdict(text: string): SafetyVerdict {
  const t = String(text ?? '');
  if (CRISIS_PATTERNS.some((re) => re.test(t))) {
    return {
      allowed: false,
      flagged: true,
      escalate: true,
      category: 'crisis',
      support: CRISIS_SUPPORT,
    };
  }
  if (HARASSMENT_PATTERNS.some((re) => re.test(t))) {
    return { allowed: false, flagged: true, escalate: false, category: 'harassment' };
  }
  return { allowed: true, flagged: false, escalate: false, category: 'safe' };
}

/** A clean, safe verdict — the common case. */
function safeVerdict(): SafetyVerdict {
  return { allowed: true, flagged: false, escalate: false, category: 'safe' };
}

/** Merge two verdicts into the STRICTER one. A crisis from EITHER path wins; a
 *  flag from either path holds. Safety is the union — never the intersection. */
export function mergeVerdicts(a: SafetyVerdict, b: SafetyVerdict): SafetyVerdict {
  if (a.category === 'crisis' || b.category === 'crisis') {
    return {
      allowed: false,
      flagged: true,
      escalate: true,
      category: 'crisis',
      support: a.support ?? b.support ?? CRISIS_SUPPORT,
    };
  }
  if (a.category === 'harassment' || b.category === 'harassment') {
    return { allowed: false, flagged: true, escalate: false, category: 'harassment' };
  }
  return safeVerdict();
}

// ---------------------------------------------------------------------------
// The model path — calm structured classification via Gemini. Reads the key by
// name, never returns or logs it. Any failure abstains to the keyword floor.
// ---------------------------------------------------------------------------

const SAFETY_PROMPT = [
  'You are a calm child-safety classifier for a school messaging surface used by',
  'students, teachers, parents and admins. Read ONE message and classify it.',
  'Respond with STRICT JSON only: {"category":"safe"|"harassment"|"crisis"}.',
  '- "crisis": the writer signals self-harm, suicidal thoughts, or an acute',
  '  emergency about their own safety. This must always be caught — when unsure',
  '  between safe and crisis, choose crisis.',
  '- "harassment": the message harasses, threatens, demeans, or bullies another',
  '  person.',
  '- "safe": ordinary school communication.',
  'Do not add commentary. Output only the JSON object.',
].join(' ');

interface GeminiClassification {
  category: SafetyCategory;
}

/** Ask the model to classify. Never throws; returns null on any failure so the
 *  caller falls back to the deterministic floor (which still escalates a crisis). */
async function modelClassify(
  text: string,
  key: string,
  fetchImpl: typeof fetch = fetch,
): Promise<GeminiClassification | null> {
  const body = {
    systemInstruction: { parts: [{ text: SAFETY_PROMPT }] },
    contents: [{ role: 'user', parts: [{ text: String(text).slice(0, 4000) }] }],
    generationConfig: { temperature: 0, maxOutputTokens: 40, responseMimeType: 'application/json' },
  };
  for (const model of MODELS) {
    try {
      const res = await fetchImpl(`${BASE}/${model}:generateContent`, {
        method: 'POST',
        headers: { 'x-goog-api-key': key, 'content-type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) continue;
      const json: any = await res.json().catch(() => null);
      const raw = json?.candidates?.[0]?.content?.parts?.map((p: any) => p?.text).filter(Boolean).join('');
      if (typeof raw !== 'string') continue;
      let parsed: any;
      try {
        parsed = JSON.parse(raw);
      } catch {
        // Tolerate a fenced or padded JSON blob.
        const m = raw.match(/\{[\s\S]*\}/);
        if (!m) continue;
        try {
          parsed = JSON.parse(m[0]);
        } catch {
          continue;
        }
      }
      const cat = parsed?.category;
      if (cat === 'safe' || cat === 'harassment' || cat === 'crisis') {
        return { category: cat };
      }
    } catch {
      // Never leak a key or stack; try the next model, then fall back.
    }
  }
  return null;
}

function classificationToVerdict(c: GeminiClassification): SafetyVerdict {
  if (c.category === 'crisis') {
    return { allowed: false, flagged: true, escalate: true, category: 'crisis', support: CRISIS_SUPPORT };
  }
  if (c.category === 'harassment') {
    return { allowed: false, flagged: true, escalate: false, category: 'harassment' };
  }
  return safeVerdict();
}

/**
 * Screen one free-text message. SERVER-ONLY.
 *
 * The deterministic floor ALWAYS runs. When a key is configured, the model runs
 * too and the two verdicts are merged into the stricter one — so a crisis from
 * EITHER path escalates, and the model can only ever catch MORE, never silence
 * what the floor caught. With no key (or any provider failure) the floor stands
 * alone and still escalates a crisis.
 *
 * @param text       the free text to screen.
 * @param env        the environment to read the key NAME from (defaults to process.env).
 * @param fetchImpl  injectable transport for tests.
 */
export async function screenText(
  text: string,
  env: Record<string, string | undefined> = process.env,
  fetchImpl: typeof fetch = fetch,
): Promise<SafetyVerdict> {
  const floor = keywordVerdict(text);

  const key = env[SAFETY_KEY_ENV];
  if (!key || key.trim().length < 16) {
    // No key: the deterministic floor stands. It still escalates a crisis.
    return floor;
  }

  const classification = await modelClassify(text, key, fetchImpl);
  if (!classification) {
    // Provider failed: never block on it — the floor still protects.
    return floor;
  }
  // Union of both: the stricter verdict wins. The model never silences the floor.
  return mergeVerdicts(floor, classificationToVerdict(classification));
}
