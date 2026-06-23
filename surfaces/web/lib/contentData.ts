/* ============================================================================
   lib/contentData.ts — typed mock for the Content / Resource Library (d5).

   Mirrors modules/content (repository.py + verification_surface.py): every
   resource is keyed to ontology topic ids from @classess/contracts SEED_ONTOLOGY,
   carries an approval lifecycle, and a generate-and-verify verification band.
   INVARIANT 7: only VERIFIED-and-APPROVED content is servable to learners — an
   unverified or generated draft is held back until a human approves it.

   Labels are generic and board-agnostic. No real pricing, no PII. The live data
   path is the gateway + content service (secret NAMES only, never values); this
   module is the graceful-degradation fallback the surface renders offline.

   The store has no content slice yet (STORE_VERSION 1), so `loadContent` reads
   the store opportunistically and falls back to this mock — the contract the
   live path will slot into without touching callers.
   ============================================================================ */

import { SEED_ONTOLOGY_IDS } from '@classess/contracts';
import type { Confidence, SubjectAccent } from '@classess/design-system';
import { topicInfo } from './loopData';

const IDS = SEED_ONTOLOGY_IDS;

/** The kind of resource. Plain, board-agnostic labels. */
export type ResourceType = 'explanation' | 'worked-example' | 'practice-set' | 'video' | 'document';

export const RESOURCE_TYPE_LABEL: Record<ResourceType, string> = {
  explanation: 'Explanation',
  'worked-example': 'Worked example',
  'practice-set': 'Practice set',
  video: 'Video',
  document: 'Document',
};

/**
 * The generate-and-verify state of one resource, surfaced from the content
 * module's confidence band + approval lifecycle:
 *   - verified     : passed the gate and a human approved it — servable.
 *   - needs-review : prepared (generated or ingested) and waiting for a human.
 *   - generated    : freshly generated, not yet verified — never servable.
 * Only `verified` is servable (INVARIANT 7).
 */
export type VerificationState = 'verified' | 'needs-review' | 'generated';

export const VERIFICATION_LABEL: Record<VerificationState, string> = {
  verified: 'Verified',
  'needs-review': 'Needs review',
  generated: 'Generated, not verified',
};

/** Map a verification state to the shared plain-language confidence band. */
export const VERIFICATION_CONFIDENCE: Record<VerificationState, Confidence> = {
  verified: 'high',
  'needs-review': 'middle',
  generated: 'low',
};

/** How a resource entered the library — provenance, never an opaque claim. */
export type ResourceSource = 'authored' | 'generated' | 'ingested';

export const SOURCE_LABEL: Record<ResourceSource, string> = {
  authored: 'Authored',
  generated: 'Generated with Vidya',
  ingested: 'Uploaded and ingested',
};

export interface ContentResource {
  id: string;
  title: string;
  /** A plain-language one-line summary — never a raw score or formula. */
  summary: string;
  type: ResourceType;
  /** The ontology topic this resource is mapped to. */
  topicId: string;
  verification: VerificationState;
  source: ResourceSource;
  /** Provenance line — where it came from, for the evidence drawer. */
  provenance: string;
  /** Plain rights note so nothing is served without clear licence. */
  licence: string;
  updated: string;
}

/** Whether a resource may be served to learners (only verified content). */
export function isServable(r: Pick<ContentResource, 'verification'>): boolean {
  return r.verification === 'verified';
}

/** Derived display fields for a resource — topic + subject from the ontology. */
export interface ResourceView extends ContentResource {
  topicName: string;
  subjectId: string;
  subjectName: string;
  accent: SubjectAccent;
  servable: boolean;
  confidence: Confidence;
}

export function toResourceView(r: ContentResource): ResourceView {
  const t = topicInfo(r.topicId);
  return {
    ...r,
    topicName: t.name,
    subjectId: t.subjectId,
    subjectName: t.subjectName,
    accent: t.accent,
    servable: isServable(r),
    confidence: VERIFICATION_CONFIDENCE[r.verification],
  };
}

// ---------------------------------------------------------------------------
// The mock library — mapped to real seed topic ids, a realistic spread of
// verification states and sources.
// ---------------------------------------------------------------------------

export const CONTENT_LIBRARY: ContentResource[] = [
  {
    id: 'res-1',
    title: 'Trigonometric ratios from a right triangle',
    summary: 'A plain walkthrough of the six ratios, built from one labelled triangle.',
    type: 'explanation',
    topicId: IDS.tTrigRatios,
    verification: 'verified',
    source: 'authored',
    provenance: 'Authored by the Mathematics lead and reviewed for Class 10-B.',
    licence: 'School-owned, free to reuse within the school.',
    updated: 'Updated 2 days ago',
  },
  {
    id: 'res-2',
    title: 'Worked examples — finding cos from sin',
    summary: 'Three worked items moving from a guided start to an independent finish.',
    type: 'worked-example',
    topicId: IDS.tTrigRatios,
    verification: 'verified',
    source: 'generated',
    provenance: 'Generated with Vidya, passed the verification gate, approved by a teacher.',
    licence: 'Generated content, school-owned.',
    updated: 'Updated yesterday',
  },
  {
    id: 'res-3',
    title: 'Practice set — trigonometric identities',
    summary: 'A short set that builds on the ratios before identities are introduced.',
    type: 'practice-set',
    topicId: IDS.tTrigIdentities,
    verification: 'needs-review',
    source: 'generated',
    provenance: 'Generated with Vidya. The second-model cross-check abstained, so it waits for a human read.',
    licence: 'Generated content, pending approval.',
    updated: 'Prepared today',
  },
  {
    id: 'res-4',
    title: 'Laws of reflection — class notes (scanned)',
    summary: 'Uploaded handwritten notes, read by document understanding into clean text.',
    type: 'document',
    topicId: IDS.tReflectionLaws,
    verification: 'needs-review',
    source: 'ingested',
    provenance: 'Uploaded and read by document understanding. Ingested content is never auto-served.',
    licence: 'Uploaded by a teacher; rights confirmed at upload.',
    updated: 'Uploaded 3 days ago',
  },
  {
    id: 'res-5',
    title: 'Ohm’s law — short explainer video',
    summary: 'A two-minute explainer with a transcript for accessibility.',
    type: 'video',
    topicId: IDS.tOhmsLaw,
    verification: 'verified',
    source: 'ingested',
    provenance: 'Uploaded, transcribed, and approved by the Physics lead.',
    licence: 'Licensed for classroom use; attribution kept on the record.',
    updated: 'Updated last week',
  },
  {
    id: 'res-6',
    title: 'Spherical mirrors — generated practice (draft)',
    summary: 'A fresh draft set on image formation, not yet checked.',
    type: 'practice-set',
    topicId: IDS.tSphericalMirrors,
    verification: 'generated',
    source: 'generated',
    provenance: 'Just generated with Vidya. Not yet verified — held back from learners until approved.',
    licence: 'Generated content, draft only.',
    updated: 'Generated moments ago',
  },
  {
    id: 'res-7',
    title: 'Refraction and refractive index — explanation',
    summary: 'A plain account of Snell’s law with an everyday example.',
    type: 'explanation',
    topicId: IDS.tRefractionLaws,
    verification: 'verified',
    source: 'authored',
    provenance: 'Authored by the Physics lead and approved for the unit.',
    licence: 'School-owned, free to reuse within the school.',
    updated: 'Updated 5 days ago',
  },
  {
    id: 'res-8',
    title: 'Degree and zeros of a polynomial — worked set',
    summary: 'Worked items pairing a graph read with the algebra.',
    type: 'worked-example',
    topicId: IDS.tPolyDegreeZeros,
    verification: 'verified',
    source: 'authored',
    provenance: 'Authored and approved by the Mathematics lead.',
    licence: 'School-owned, free to reuse within the school.',
    updated: 'Updated last week',
  },
];

// ---------------------------------------------------------------------------
// Filtering — the surface filters by subject, topic, type, and search text.
// Pure functions so the page logic stays testable.
// ---------------------------------------------------------------------------

export interface ContentFilter {
  /** A subject id, or 'all'. */
  subjectId?: string;
  /** A topic id, or undefined for any. */
  topicId?: string;
  /** A resource type, or undefined for any. */
  type?: ResourceType;
  /** Free-text query over title + topic name. */
  query?: string;
  /** When true, only servable (verified) resources are returned. */
  onlyServable?: boolean;
}

/** Apply a filter to a list of resource views. Pure + deterministic. */
export function filterResources(views: ResourceView[], filter: ContentFilter): ResourceView[] {
  const q = filter.query?.trim().toLowerCase() ?? '';
  return views.filter((v) => {
    if (filter.subjectId && filter.subjectId !== 'all' && v.subjectId !== filter.subjectId)
      return false;
    if (filter.topicId && v.topicId !== filter.topicId) return false;
    if (filter.type && v.type !== filter.type) return false;
    if (filter.onlyServable && !v.servable) return false;
    if (q) {
      const hay = `${v.title} ${v.topicName} ${v.summary}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

/** A small plain-language count summary for the filtered library. */
export function libraryStats(views: ResourceView[]): {
  total: number;
  verified: number;
  needsReview: number;
  generated: number;
} {
  return {
    total: views.length,
    verified: views.filter((v) => v.verification === 'verified').length,
    needsReview: views.filter((v) => v.verification === 'needs-review').length,
    generated: views.filter((v) => v.verification === 'generated').length,
  };
}

// ---------------------------------------------------------------------------
// The load seam — read the store when a content slice exists, else the mock.
// The live gateway path slots in here without touching the page.
// ---------------------------------------------------------------------------

/** A store-shaped blob that MAY carry a content slice in a future version. */
interface MaybeContentStore {
  content?: { resources?: ContentResource[] };
}

/**
 * Resolve the library: a populated store slice when present, the mock otherwise.
 * Never throws — returns the mock on any malformed shape (graceful degradation).
 */
export function loadContent(store?: unknown): ResourceView[] {
  try {
    const slice = (store as MaybeContentStore | undefined)?.content?.resources;
    const source = Array.isArray(slice) && slice.length > 0 ? slice : CONTENT_LIBRARY;
    return source.map(toResourceView);
  } catch {
    return CONTENT_LIBRARY.map(toResourceView);
  }
}
