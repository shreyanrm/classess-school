'use client';

import { CrystallizeNode } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import type { MasteryResult, GapResult } from '@/lib/engine';
import { gapLabel } from '@/lib/engine';

/** Plain-language gloss per dimension — never a number, never the formula. */
const DIMENSION_GLOSS: Record<string, string> = {
  performance: 'how correct the work is',
  reliability: 'how dependable across attempts',
  independence: 'how much was done alone, not with help',
  difficulty: 'how hard the items succeeded on were',
  recency: 'how fresh the evidence is',
  consistency: 'how steady the work is over time',
};

/** A coarse, word-only level for a dimension — keeps the number off the surface. */
function level(v: number): string {
  if (v >= 0.7) return 'strong';
  if (v >= 0.45) return 'building';
  return 'early';
}

/**
 * Build the evidence lines behind a mastery conclusion: the six dimensions in
 * plain language, the independent-vs-supported split, and any confirmed gap.
 * The lines are words, never a raw composite or formula (the cross-cutting law).
 */
export function masteryEvidence(mastery: MasteryResult, gaps: GapResult[] = []): string[] {
  const lines: string[] = [];
  lines.push(
    `Based on ${mastery.observationCount} ${mastery.observationCount === 1 ? 'piece' : 'pieces'} of evidence, ` +
      `${mastery.independentObservationCount} of them done on your own.`,
  );
  const dims = mastery.reading.dimensions as unknown as Record<string, number>;
  for (const key of Object.keys(DIMENSION_GLOSS)) {
    const v = dims[key];
    if (typeof v === 'number') {
      lines.push(`${cap(DIMENSION_GLOSS[key]!)} — ${level(v)}.`);
    }
  }
  if (mastery.revisionDue) lines.push('A spaced review is due — the memory is starting to fade.');
  const confirmed = gaps.find((g) => g.evidence.confirmed);
  if (confirmed) {
    lines.push(`Confirmed focus: ${gapLabel(confirmed.evidence.gapType).toLowerCase()} (${confirmed.evidence.rationale}).`);
  }
  return lines;
}

function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * One mastery conclusion in plain language, with the EvidenceDrawer wired so the
 * provenance opens on demand. The ignite (CrystallizeNode) marks a genuine,
 * unaided demonstration. Never renders a raw score.
 */
export function MasteryConclusion({
  topicName,
  mastery,
  gaps = [],
  source,
}: {
  topicName: string;
  mastery: MasteryResult;
  gaps?: GapResult[];
  source?: 'gateway' | 'fallback';
}) {
  const independent = mastery.reading.independent;
  return (
    <div className="stack">
      <div className="row-between">
        <div className="ignite-row">
          {independent ? <CrystallizeNode variant="b" inline resolved label="On your own" /> : null}
          <span className="body">{topicName}</span>
        </div>
        <span className="body-sm muted">{cap(mastery.plainLanguage)}</span>
      </div>
      <EvidenceDrawer
        evidence={masteryEvidence(mastery, gaps)}
        whySeeing={
          source === 'fallback'
            ? 'This is the last reading kept on your device — it refreshes from the live engine when the connection is back.'
            : 'This reading comes from your own attempts and checks, read live from the learning engine.'
        }
      />
    </div>
  );
}
