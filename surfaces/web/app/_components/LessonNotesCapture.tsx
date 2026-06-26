'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Button, ConfidenceBand, Icon, Tag } from '@classess/design-system';
import { EvidenceDrawer } from './EvidenceDrawer';
import { ApprovalControl } from './ApprovalControl';

/* ============================================================================
   LessonNotesCapture — the v2 "Lesson Notes Editor" carried into v3 as a Vidya
   generative-UI showcase.

   A teacher captures raw notes by typing OR by voice (Web Speech API, dictation
   appended to the textarea — gracefully absent where the browser has no STT),
   then "Format with AI" structures the free text into the canonical lesson-note
   sections: Topics covered · Key points · Concepts introduced · Questions to
   pose · Homework. The structured draft is shown as editable, evidence-first
   placeholders; saving the notes routes through the approval ladder (a note
   attached to a lesson is a prepared act, not auto-published).

   v3 grammar: one accent surface, depth = hairline + tonal, NO shadow, mono
   overline, reduced-motion safe. The "format" pass is a deterministic, on-device
   structuring (the generative step) — honest about being prepared, never magic.
   ============================================================================ */

type Phase = 'capture' | 'formatted' | 'saved';

interface NoteSection {
  key: string;
  label: string;
  placeholder: string;
  /** The structured lines pulled into this section. */
  lines: string[];
}

const SECTION_DEFS: { key: string; label: string; placeholder: string; cue: RegExp }[] = [
  { key: 'topics', label: 'Topics covered', placeholder: 'What the lesson moved through', cue: /\b(topic|cover|chapter|unit|recap|introduc)/i },
  { key: 'keyPoints', label: 'Key points', placeholder: 'The points that mattered most', cue: /\b(point|note|remember|important|key|emphasi)/i },
  { key: 'concepts', label: 'Concepts introduced', placeholder: 'New ideas met for the first time', cue: /\b(concept|idea|definition|theorem|formula|principle|law)/i },
  { key: 'questions', label: 'Questions to pose', placeholder: 'Prompts to check understanding', cue: /(\?|\b(ask|question|why|how|what if|discuss|probe))/i },
  { key: 'homework', label: 'Homework', placeholder: 'What to practise before next class', cue: /\b(homework|practice|practise|assign|worksheet|exercise|due|complete)/i },
];

/** A minimal SpeechRecognition surface — typed locally to avoid a global dep. */
interface SpeechRec {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}

/** Structure raw notes into the canonical sections — the "Format with AI" pass.
 *  Deterministic + on-device: each sentence is routed to the section it cues,
 *  unmatched lines fall to "Key points" so nothing is dropped. */
function formatNotes(raw: string): NoteSection[] {
  const sections: NoteSection[] = SECTION_DEFS.map((d) => ({
    key: d.key,
    label: d.label,
    placeholder: d.placeholder,
    lines: [],
  }));
  const byKey = new Map(sections.map((s) => [s.key, s]));
  const sentences = raw
    .split(/(?<=[.!?])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
  for (const sentence of sentences) {
    const def = SECTION_DEFS.find((d) => d.cue.test(sentence));
    const target = byKey.get(def?.key ?? 'keyPoints')!;
    // Strip a trailing period for clean bullet lines.
    target.lines.push(sentence.replace(/\.$/, ''));
  }
  return sections;
}

export interface LessonNotesCaptureProps {
  /** The lesson/topic these notes attach to — shown in the header + payload. */
  topicLabel: string;
  topicId?: string;
}

export function LessonNotesCapture({ topicLabel, topicId }: LessonNotesCaptureProps) {
  const [raw, setRaw] = useState('');
  const [phase, setPhase] = useState<Phase>('capture');
  const [sections, setSections] = useState<NoteSection[]>([]);
  const [listening, setListening] = useState(false);
  const recRef = useRef<SpeechRec | null>(null);

  const voiceSupported = useMemo(() => {
    if (typeof window === 'undefined') return false;
    return Boolean(
      (window as unknown as { SpeechRecognition?: unknown }).SpeechRecognition ||
        (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition,
    );
  }, []);

  useEffect(() => {
    return () => {
      try {
        recRef.current?.stop();
      } catch {
        /* no-op */
      }
    };
  }, []);

  function toggleVoice() {
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const Ctor =
      (window as unknown as { SpeechRecognition?: new () => SpeechRec }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: new () => SpeechRec }).webkitSpeechRecognition;
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = 'en-IN';
    rec.interimResults = false;
    rec.continuous = false;
    rec.onresult = (e) => {
      const last = e.results[e.results.length - 1];
      const text = last?.[0]?.transcript ?? '';
      if (text) setRaw((prev) => (prev ? `${prev} ${text}` : text));
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    setPhase('capture');
    try {
      rec.start();
    } catch {
      setListening(false);
    }
  }

  function handleFormat() {
    setSections(formatNotes(raw));
    setPhase('formatted');
  }

  function editSection(key: string, value: string) {
    setSections((prev) =>
      prev.map((s) => (s.key === key ? { ...s, lines: value.split('\n') } : s)),
    );
  }

  const wordCount = raw.trim() ? raw.trim().split(/\s+/).length : 0;
  const canFormat = wordCount >= 3;

  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-4)' }}>
      <div className="sec-head">
        <div>
          <p className="overline" style={{ margin: 0 }}>Lesson notes · {topicLabel}</p>
          <h4 className="h4" style={{ margin: '4px 0 0' }}>Capture, then format with Vidya</h4>
        </div>
        <Tag tone={phase === 'saved' ? 'success' : phase === 'formatted' ? 'info' : 'neutral'}>
          {phase === 'saved' ? 'Saved' : phase === 'formatted' ? 'Structured draft' : 'Capturing'}
        </Tag>
      </div>

      {/* ── Raw capture: textarea + voice dictation ── */}
      <div className="stack" style={{ gap: 'var(--space-2)' }}>
        <label className="caption muted" htmlFor="lesson-notes-raw">
          Type the notes, or dictate them — Vidya structures them for you.
        </label>
        <textarea
          id="lesson-notes-raw"
          className="notes-textarea"
          value={raw}
          onChange={(e) => {
            setRaw(e.target.value);
            if (phase !== 'capture') setPhase('capture');
          }}
          placeholder="e.g. Covered equivalent fractions and the number line. Key point: a fraction is a single number, not two. Introduced the concept of equivalence. Ask why 1/2 and 2/4 land on the same point. Homework: the fractions worksheet, due Friday."
          rows={6}
        />
        <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
          {voiceSupported ? (
            <Button
              variant={listening ? 'accent' : 'secondary'}
              size="sm"
              onClick={toggleVoice}
              className="row"
              style={{ gap: 'var(--space-2)' }}
              aria-pressed={listening}
            >
              <Icon name="spark" size="sm" />
              {listening ? 'Listening — tap to stop' : 'Dictate'}
            </Button>
          ) : (
            <span className="caption quiet row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
              <Icon name="info" size="sm" /> Voice dictation is unavailable in this browser — typing works the same.
            </span>
          )}
          <Button variant="primary" size="sm" disabled={!canFormat} onClick={handleFormat} className="row" style={{ gap: 'var(--space-2)' }}>
            <Icon name="spark" size="sm" /> Format with AI
          </Button>
          <span className="caption muted">{wordCount} words</span>
        </div>
      </div>

      {/* ── Structured placeholders (editable) ── */}
      {phase !== 'capture' ? (
        <div className="stack" style={{ gap: 'var(--space-3)' }}>
          <div className="row-between">
            <p className="overline" style={{ margin: 0 }}>Structured notes</p>
            <ConfidenceBand level="middle" />
          </div>
          <div className="notes-sections">
            {sections.map((s) => (
              <div className="notes-section" key={s.key}>
                <label className="caption" htmlFor={`note-${s.key}`} style={{ fontWeight: 500 }}>{s.label}</label>
                <textarea
                  id={`note-${s.key}`}
                  className="notes-section-field"
                  value={s.lines.join('\n')}
                  onChange={(e) => editSection(s.key, e.target.value)}
                  placeholder={s.placeholder}
                  rows={Math.max(2, s.lines.length)}
                />
              </div>
            ))}
          </div>
          <EvidenceDrawer
            claim="How the notes were structured"
            confidence="middle"
            evidence={[
              'Your free text was split into lines and routed to the section each line cues — topics, key points, concepts, questions, and homework.',
              'Nothing was invented or dropped: an unmatched line falls to Key points, and every section stays editable.',
              'This is a prepared draft — middle confidence — so it waits for your edit and approval before it attaches to the lesson.',
            ]}
            whySeeing="Formatting is a structuring pass over what you said — it organises your words, it does not write new ones, and you stay in control of every line."
          />
        </div>
      ) : null}

      {/* ── Save through the permission ladder ── */}
      {phase === 'formatted' ? (
        <ApprovalControl
          kind="Lesson notes · the permission ladder"
          summary={`Attach the structured notes to ${topicLabel}`}
          consequence="The notes are saved to this lesson's record and become part of the class diary. They are not shared with students or parents unless you choose to."
          eventType="plan.submitted"
          approveLabel="Save the notes"
          payload={{ surface: 'teacher.plan.notes', topicId, sections: sections.length }}
          evidence={[
            'The notes are a structured draft of what you captured — every line is yours and editable.',
            'Saving attaches them to the lesson record only; nothing is sent onward without a separate choice.',
          ]}
          whySeeing="Notes attach to a lesson record, so saving is a deliberate act — it is prepared and waits for you."
          onApprove={() => setPhase('saved')}
          onAdjust={() => setPhase('capture')}
        />
      ) : null}

      {phase === 'saved' ? (
        <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
          <Tag tone="success">Saved to the lesson</Tag>
          <span className="caption muted">The notes now sit on {topicLabel} in the class diary.</span>
          <Button variant="ghost" size="sm" onClick={() => { setPhase('capture'); setRaw(''); setSections([]); }}>
            New notes
          </Button>
        </div>
      ) : null}
    </div>
  );
}
