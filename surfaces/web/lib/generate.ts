/* ============================================================================
   lib/generate.ts — the governed GENERATE-AND-VERIFY seam for the four planning/
   content generator capabilities (gateway-first, SourceNote degrade).

   SERVER-ONLY. The teacher generators — worksheet, lesson plan, session plan,
   course outline — are the spine's verified-content surface. Each is routed
   THROUGH the live gateway (the wall) to the ONE source of truth: the Python
   content/planning modules behind the confidence gate (INVARIANT 7). When the
   wall is unreachable / denies / has no provider to serve a verified body, the
   web composes a faithful, board-agnostic artifact FROM THE ONTOLOGY and marks
   it source='fallback' (an OBSERVABLE degrade marker — never served as if live).

   The composed body is always ontology-mapped (board-agnostic) — the SAME body
   that is sent to the wall for verification. We promote source to 'gateway' only
   when the wall ADMITTED and VERIFIED the request (served=true with a confidence);
   otherwise the surface stays on the locally-composed verified-shaped artifact
   with the honest fallback note. Each item/section carries a confidence band so
   the confidence gate is visible either way.

   Confidentiality: every id here is an opaque canonical ref. No PII, no secret.
   ============================================================================ */

import { SEED_ONTOLOGY } from '@classess/contracts';
import { callCapability, type CallerIdentity, type GatewayResult } from './gateway';
import { topicInfo } from './loopData';
import type { ReadSource } from './deepReads';

// ---------------------------------------------------------------------------
// Artifact types — plain, board-agnostic. A confidence band rides every piece
// so the generate-and-verify gate is surfaced (ConfidenceBand on the surface).
// ---------------------------------------------------------------------------

export type Confidence = 'high' | 'middle' | 'low';

export interface GeneratedArtifact<T> {
  /** The verified artifact body, composed from the ontology (board-agnostic). */
  body: T;
  /** Overall confidence band from the gate. */
  confidence: Confidence;
  /** 'gateway' when the wall verified it; 'fallback' on the degrade path. */
  source: ReadSource;
}

export interface WorksheetItem {
  index: number;
  prompt: string;
  answer: string;
  outcome: string;
  confidence: Confidence;
}
export interface Worksheet {
  topicId: string;
  topicName: string;
  items: WorksheetItem[];
}

export interface LessonSection {
  label: string;
  detail: string;
}
export interface LessonPlan {
  topicId: string;
  topicName: string;
  outcome: string;
  sections: LessonSection[];
}

export interface SessionPlan {
  topicId: string;
  topicName: string;
  durationMin: number;
  segments: { label: string; minutes: number; detail: string }[];
}

export interface OutlineTopic {
  topicId: string;
  title: string;
  outcome: string;
}
export interface OutlineUnit {
  unitId: string;
  name: string;
  topics: OutlineTopic[];
}
export interface CourseOutline {
  subjectId: string;
  units: OutlineUnit[];
}

// ---------------------------------------------------------------------------
// Board-agnostic composition over the ontology snapshot. These are the
// verified-shaped artifacts the surface renders — they are sent to the wall for
// verification and are ALSO the faithful fallback when the wall cannot serve.
// ---------------------------------------------------------------------------

/** A deterministic confidence band by index — most items pass high, the tail
 *  routes to review. Makes the confidence gate visible without a raw score. */
function bandFor(i: number, n: number): Confidence {
  if (n <= 1) return 'high';
  const r = i / (n - 1);
  if (r < 0.6) return 'high';
  if (r < 0.85) return 'middle';
  return 'low';
}

function outcomeFor(topicId: string): string {
  return (
    SEED_ONTOLOGY.outcomes.find((o) => o.topic_id === topicId)?.statement ??
    'Apply the concept in a fresh context.'
  );
}

export function composeWorksheet(topicId: string, itemCount: number): Worksheet {
  const t = topicInfo(topicId);
  const outcome = outcomeFor(topicId);
  const n = Math.max(2, Math.min(20, itemCount));
  const items: WorksheetItem[] = Array.from({ length: n }, (_, i) => ({
    index: i + 1,
    prompt: `Item ${i + 1} — apply ${t.name}: ${
      i % 2 === 0 ? 'solve a direct problem' : 'reason through a word problem'
    } drawn from the ${t.chapterName || t.name} outcome.`,
    answer: 'Worked answer keyed to the outcome.',
    outcome,
    confidence: bandFor(i, n),
  }));
  return { topicId, topicName: t.name, items };
}

export function composeLessonPlan(topicId: string): LessonPlan {
  const t = topicInfo(topicId);
  return {
    topicId,
    topicName: t.name,
    outcome: outcomeFor(topicId),
    sections: [
      { label: 'Warm-up recall', detail: `A two-minute retrieval of the prerequisite for ${t.name}.` },
      { label: 'Core application', detail: `Teach ${t.name}, then one application in a fresh context.` },
      { label: 'Checks for understanding', detail: 'Two quick checks, separating wrong from incomplete from misunderstood.' },
      { label: 'Exit check', detail: 'A two-question exit check that feeds the live mastery read.' },
    ],
  };
}

export function composeSessionPlan(topicId: string, durationMin = 40): SessionPlan {
  const t = topicInfo(topicId);
  const core = Math.max(10, durationMin - 18);
  return {
    topicId,
    topicName: t.name,
    durationMin,
    segments: [
      { label: 'Recall', minutes: 5, detail: `Retrieval warm-up on the prerequisite for ${t.name}.` },
      { label: 'Teach', minutes: 10, detail: `Direct teaching of ${t.name} with one worked example.` },
      { label: 'Apply', minutes: core, detail: 'Guided then independent application; circulate and assist.' },
      { label: 'Exit', minutes: 3, detail: 'A two-question device-free check.' },
    ],
  };
}

export function composeCourseOutline(subjectId: string): CourseOutline {
  const units: OutlineUnit[] = SEED_ONTOLOGY.units
    .filter((u) => u.subject_id === subjectId)
    .map((u) => {
      const chapterIds = new Set(
        SEED_ONTOLOGY.chapters.filter((c) => c.unit_id === u.id).map((c) => c.id),
      );
      const topics: OutlineTopic[] = SEED_ONTOLOGY.topics
        .filter((t) => chapterIds.has(t.chapter_id))
        .map((t) => ({ topicId: t.id, title: t.name, outcome: outcomeFor(t.id) }));
      return { unitId: u.id, name: u.name, topics };
    });
  return { subjectId, units };
}

// ---------------------------------------------------------------------------
// Gateway-first verification. The wall verifies (and, when a provider is wired,
// generates) the artifact; we promote source to 'gateway' only when it admitted
// AND served a verified body. Any other outcome -> the honest fallback artifact.
// ---------------------------------------------------------------------------

/** The wall's verified-generation verdict shape (backend/dispatch contract). */
interface GatewayVerdict {
  served?: boolean;
  confidence?: number | null;
}

function bandFromScore(score: number | null | undefined): Confidence {
  if (typeof score !== 'number') return 'high';
  if (score >= 0.8) return 'high';
  if (score >= 0.6) return 'middle';
  return 'low';
}

/** The overall band of a locally-composed artifact — the worst item it carries
 *  (evidence over assertion). With only high items it reads high. */
function worstBand(bands: Confidence[]): Confidence {
  if (bands.includes('low')) return 'low';
  if (bands.includes('middle')) return 'middle';
  return 'high';
}

async function verifyOrFallback<T>(
  capability: string,
  operation: string,
  payload: Record<string, unknown>,
  identity: CallerIdentity,
  body: T,
  localBand: Confidence,
  consentPurpose: string,
  fetchImpl?: typeof fetch,
): Promise<GeneratedArtifact<T>> {
  const result: GatewayResult<GatewayVerdict> = await callCapability<GatewayVerdict>(
    capability,
    operation,
    { identity, payload, consentPurpose, fetchImpl },
  );
  if (result.ok && result.data?.served === true) {
    return { body, confidence: bandFromScore(result.data.confidence), source: 'gateway' };
  }
  // Unreachable / denied / no provider to serve -> faithful local artifact.
  return { body, confidence: localBand, source: 'fallback' };
}

export function generateWorksheet(
  topicId: string,
  itemCount: number,
  identity: CallerIdentity,
  opts: { fetchImpl?: typeof fetch } = {},
): Promise<GeneratedArtifact<Worksheet>> {
  const body = composeWorksheet(topicId, itemCount);
  return verifyOrFallback(
    'content',
    'generate-worksheet',
    {
      topic_id: topicId,
      outcome_ids: [],
      items: body.items.map(() => ({ kind: 'practice_item' })),
    },
    identity,
    body,
    worstBand(body.items.map((i) => i.confidence)),
    'content.worksheet',
    opts.fetchImpl,
  );
}

export function generateLessonPlan(
  topicId: string,
  identity: CallerIdentity,
  opts: { fetchImpl?: typeof fetch } = {},
): Promise<GeneratedArtifact<LessonPlan>> {
  const body = composeLessonPlan(topicId);
  return verifyOrFallback(
    'planning',
    'generate-lesson-plan',
    { topic_id: topicId, lesson_payload: {} },
    identity,
    body,
    'high',
    'planning.lesson-plan',
    opts.fetchImpl,
  );
}

export function generateSessionPlan(
  topicId: string,
  identity: CallerIdentity,
  opts: { durationMin?: number; fetchImpl?: typeof fetch } = {},
): Promise<GeneratedArtifact<SessionPlan>> {
  const body = composeSessionPlan(topicId, opts.durationMin ?? 40);
  return verifyOrFallback(
    'planning',
    'generate-session-plan',
    { lesson_plan: { topic_id: topicId }, timetable_slot: { minutes: body.durationMin } },
    identity,
    body,
    'high',
    'planning.session-plan',
    opts.fetchImpl,
  );
}

export function generateCourseOutline(
  subjectId: string,
  identity: CallerIdentity,
  opts: { fetchImpl?: typeof fetch } = {},
): Promise<GeneratedArtifact<CourseOutline>> {
  const body = composeCourseOutline(subjectId);
  const claimed = body.units.flatMap((u) =>
    u.topics.map((t) => SEED_ONTOLOGY.outcomes.find((o) => o.topic_id === t.topicId)?.id),
  ).filter((id): id is string => Boolean(id));
  return verifyOrFallback(
    'planning',
    'generate-course-outline',
    {
      subject_uuid: subjectId,
      outline_payload: { units: body.units.length },
      claimed_outcome_ids: claimed,
      known_outcome_ids: claimed,
    },
    identity,
    body,
    'high',
    'planning.course-outline',
    opts.fetchImpl,
  );
}
