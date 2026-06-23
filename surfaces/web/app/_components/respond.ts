/* ============================================================================
   The local turn responder.

   This is the graceful-degradation stand-in for the live Vidya path through the
   gateway (generate-and-verify, confidence gate, permission ladder). It maps a
   user intention to a calm reply and, only when the task warrants one, an inline
   generative result — and, for a big task, an "open in its page" route. It never
   manufactures UI on every turn. When the gateway env var is configured the
   surface will call the wall instead; until then this keeps the home alive.
   ============================================================================ */

import type { InlineResultData } from './InlineResult';

export interface TurnReply {
  text: string;
  inline?: InlineResultData;
}

function id(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function respond(input: string): TurnReply {
  const q = input.toLowerCase();

  // Big task -> route. A quick check produces persistent state, so it opens its
  // own page; the inline result carries the route.
  if (q.includes('check') || q.includes('quiz') || q.includes('worksheet')) {
    return {
      text: 'I have drafted a short check for Class 10-B. It is ready to review in its own workspace, where you can edit items and set it live.',
      inline: {
        title: 'Quick check — equivalent fractions',
        body: 'Five items, mixed difficulty, mapped to the prerequisite outcomes the class slipped on.',
        items: [
          'Two recall items to settle the idea',
          'Two application items in a fresh context',
          'One short-answer item that asks them to explain their step',
        ],
        confidence: 'middle',
        openHref: '/proactive',
        openLabel: 'Open the workspace',
      },
    };
  }

  // Insights / analytics ask -> route to the insights page.
  if (q.includes('weak') || q.includes('insight') || q.includes('attention') || q.includes('progress')) {
    return {
      text: 'Nine students need support across two topics this week, and equivalent fractions is the one to address first. The full picture is on the insights page.',
      inline: {
        title: 'Who needs attention',
        body: 'A plain-language read of where the class is independent and where it still leans on support.',
        items: [
          'Equivalent fractions — most still need a worked start',
          'Photosynthesis — reliable with guidance, not yet unprompted',
        ],
        openHref: '/insights',
        openLabel: 'Open student insights',
      },
    };
  }

  // Small task -> inline, ephemeral. A 15-minute plan answers directly.
  if (q.includes('fraction') || q.includes('15 min') || q.includes('fix')) {
    return {
      text: 'Here is a 15-minute reset you can run at the start of the next class. It stays in this thread unless you want to save it.',
      inline: {
        title: 'Fractions reset — 15 minutes',
        body: 'A short, low-stakes sequence to settle equivalent fractions before the ratios unit.',
        items: [
          '3 min — one worked example on the board, thinking aloud',
          '7 min — paired practice on three graded items',
          '5 min — a device-free check to see who can now start alone',
        ],
        confidence: 'high',
      },
    };
  }

  // Default: answered directly, no manufactured UI.
  return {
    text: 'I can help you prepare a class, build a quick check, read where the class is, or draft tomorrow’s prep. Tell me where you want to start.',
  };
}

export { id as messageId };
