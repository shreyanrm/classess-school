'use client';

import { useState } from 'react';
import { Button, Icon, Input, Tag } from '@classess/design-system';
import { HolisticProgressCard } from './HolisticProgressCard';
import { FormalReportCard } from './FormalReportCard';
import { ApprovalControl } from './ApprovalControl';
import type { FormalReportCard as FormalReportCardData, HolisticProgress, ObservationLine, ReadSource } from '@/lib/vizData';

/* ============================================================================
   HolisticCardBuilder — the teacher COMPOSES the holistic progress card, then
   shares it to the parent. The card itself (HolisticProgressCard) is the
   read-only render; this builder adds the two acts a teacher needs:

     1) Compose — add / edit / remove the teacher OBSERVATIONS and PREPARED
        next steps that sit on the card (the rest of the card is the evidence
        read and is not hand-edited).
     2) Share — the permission ladder. Sharing the card to the parent is
        consequential, so it is PREPARED and waits for explicit approval; it
        never auto-sends. The shared view is the PARENT audience (plain
        language; the six-dimension reasoning stays teacher-only).

   v3 grammar: bands not raw %, evidence-first, one accent surface, depth =
   hairline + tonal, NO shadow, reduced-motion safe.
   ============================================================================ */

const KIND_OPTIONS: { kind: ObservationLine['kind']; label: string }[] = [
  { kind: 'strength', label: 'Strength' },
  { kind: 'focus', label: 'Focus' },
  { kind: 'intervention', label: 'Prepared step' },
];

export interface HolisticCardBuilderProps {
  data: HolisticProgress;
  /** The formal marks/grade report card for the same learner — offered as an
   *  explicit export alongside the plain-language card (never replacing it). */
  formalReport?: FormalReportCardData;
  source?: ReadSource;
  /** The source behind the formal-report read (for its own SourceNote). */
  formalSource?: ReadSource;
}

export function HolisticCardBuilder({ data, formalReport, source = 'fallback', formalSource = 'fallback' }: HolisticCardBuilderProps) {
  const [observations, setObservations] = useState<ObservationLine[]>(data.observations);
  const [draftText, setDraftText] = useState('');
  const [draftKind, setDraftKind] = useState<ObservationLine['kind']>('strength');
  const [composing, setComposing] = useState(false);
  const [shared, setShared] = useState(false);
  // The plain-language holistic card is the default preview; the formal
  // marks/grade card is an explicit toggle alongside it (never replacing it).
  const [previewView, setPreviewView] = useState<'holistic' | 'formal'>('holistic');

  const card: HolisticProgress = { ...data, observations };

  function addObservation() {
    const text = draftText.trim();
    if (!text) return;
    setObservations((prev) => [...prev, { kind: draftKind, text }]);
    setDraftText('');
  }

  function removeObservation(i: number) {
    setObservations((prev) => prev.filter((_, idx) => idx !== i));
  }

  return (
    <div className="stack" style={{ gap: 'var(--space-5)' }}>
      <div className="sec-head">
        <div>
          <p className="overline" style={{ margin: 0 }}>Holistic progress card · builder</p>
          <h4 className="h4" style={{ margin: '4px 0 0' }}>Compose, then share to the family</h4>
        </div>
        <Button
          variant={composing ? 'accent' : 'secondary'}
          size="sm"
          onClick={() => setComposing((v) => !v)}
          aria-pressed={composing}
          className="row"
          style={{ gap: 'var(--space-2)' }}
        >
          <Icon name="settings" size="sm" />
          {composing ? 'Done editing' : 'Edit observations'}
        </Button>
      </div>

      {/* ── Compose the observations + prepared steps ── */}
      {composing ? (
        <div className="stack viz-card" style={{ gap: 'var(--space-3)' }}>
          <p className="overline" style={{ margin: 0 }}>Observations & prepared next steps</p>
          <ul className="builder-obs">
            {observations.map((obs, i) => (
              <li className="builder-obs-row" key={i}>
                <Tag tone={obs.kind === 'strength' ? 'success' : obs.kind === 'focus' ? 'info' : 'warning'}>
                  {KIND_OPTIONS.find((k) => k.kind === obs.kind)?.label}
                </Tag>
                <span className="body-sm" style={{ flex: 1 }}>{obs.text}</span>
                <Button variant="ghost" size="sm" iconOnly aria-label="Remove" onClick={() => removeObservation(i)}>
                  <Icon name="close" size="sm" />
                </Button>
              </li>
            ))}
          </ul>
          <div className="row" style={{ gap: 'var(--space-2)', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div className="ladder" role="group" aria-label="Observation kind">
              {KIND_OPTIONS.map((k) => (
                <button
                  key={k.kind}
                  type="button"
                  className={`ladder-rung${draftKind === k.kind ? ' active' : ''}`}
                  onClick={() => setDraftKind(k.kind)}
                >
                  {k.label}
                </button>
              ))}
            </div>
            <Input
              value={draftText}
              aria-label="Observation text"
              onChange={(e) => setDraftText(e.target.value)}
              placeholder="Add an observation in plain language…"
              style={{ flex: 1, minWidth: 220 }}
              onKeyDown={(e) => { if (e.key === 'Enter') addObservation(); }}
            />
            <Button variant="primary" size="sm" onClick={addObservation} disabled={!draftText.trim()}>
              Add
            </Button>
          </div>
          <p className="caption quiet" style={{ margin: 0 }}>
            Prepared steps wait for your approval — adding one here does not assign or send anything.
          </p>
        </div>
      ) : null}

      {/* ── Live preview of the card as the FAMILY will read it ── */}
      <div className="stack" style={{ gap: 'var(--space-2)' }}>
        <div className="row-between" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
          <p className="overline" style={{ margin: 0 }}>Preview · as the family will read it</p>
          {formalReport ? (
            <div className="ladder" role="group" aria-label="Report card view">
              <button
                type="button"
                className={`ladder-rung${previewView === 'holistic' ? ' active' : ''}`}
                onClick={() => setPreviewView('holistic')}
                aria-pressed={previewView === 'holistic'}
              >
                Plain language
              </button>
              <button
                type="button"
                className={`ladder-rung${previewView === 'formal' ? ' active' : ''}`}
                onClick={() => setPreviewView('formal')}
                aria-pressed={previewView === 'formal'}
              >
                Formal report card
              </button>
            </div>
          ) : null}
        </div>
        {formalReport && previewView === 'formal' ? (
          <FormalReportCard data={formalReport} source={formalSource} audience="parent" />
        ) : (
          <HolisticProgressCard data={card} source={source} audience="parent" />
        )}
        {formalReport ? (
          <p className="caption quiet" style={{ margin: 0 }}>
            The plain-language card is the default the family sees. The formal marks/grade card is an
            explicit export they can print — it sits alongside, it never replaces the plain card.
          </p>
        ) : null}
      </div>

      {/* ── Share through the permission ladder ── */}
      {shared ? (
        <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
          <Tag tone="success">Shared with the family</Tag>
          <span className="caption muted">
            The card is available in the family&apos;s reports, in their language. You can update and re-share at any time.
          </span>
          <Button variant="ghost" size="sm" onClick={() => setShared(false)}>Update and re-share</Button>
        </div>
      ) : (
        <ApprovalControl
          kind="Share progress card · the permission ladder"
          summary={`Share ${data.subjectLabel}'s holistic progress card with the family`}
          consequence="The card becomes visible in the family's reports, in plain language and their chosen language. The six-dimension reasoning stays teacher-only and is never shared."
          eventType="report.shared"
          approveLabel="Share with the family"
          payload={{ surface: 'teacher.holistic.builder', term: data.term, observations: observations.length }}
          evidence={[
            'The card gathers a corroborated read — competency bands, foundations, trend, attendance — never a single score.',
            'Your observations and prepared steps are composed by you; the rest is the evidence read.',
            'Sharing sends the parent-audience view only; the teacher-only six-dimension lens is withheld.',
          ]}
          whySeeing="A card sent to a family is consequential, so it is prepared and waits for your explicit approval — nothing auto-sends."
          onApprove={() => setShared(true)}
        />
      )}
    </div>
  );
}
