'use client';

/* ============================================================================
   PracticeFormats — the varied interaction VOCABULARY for the student learn /
   practice surfaces. Each format is a small, self-contained interaction that
   reports a calm completion signal upward; none of them ever show a raw score.

   The set:
     · Flashcard      — flip + a card counter, "I knew it / show me" self-rating.
     · FillBlank      — drag word pills into the blanks (keyboard-operable too).
     · Matching       — pair terms to definitions.
     · PredictThenCheck   — commit a prediction, THEN reveal (no peeking).
     · AssembleTheProof   — order the steps of an argument into a valid chain.
     · FillTheMissingStep — one step of a worked solution is blank; supply it.
     · TeachItBack        — explain it in your own words; self-check against cues.

   v3 GRAMMAR:
     · Evidence-first, never a mark. Self-rated formats record what the learner
       can do ("knew it", "explained it"), not a percentage.
     · Permission ladder: predict-then-check will NOT reveal until a prediction
       is committed; teach-it-back never grades free reasoning.
     · Hairline + tonal + frost, NEVER a shadow. One accent (the surface hue).
     · Reduced-motion: the flashcard flip is a CSS transition gated by the
       reduce query; everything works without animation.
     · Fully keyboard-operable (drag-drop has click-to-place fallbacks).
   ============================================================================ */

import { useMemo, useState, type ReactNode } from 'react';
import { Button, Icon, Tag } from '@classess/design-system';

/** A calm signal a format emits when the learner finishes a round. */
export interface FormatSignal {
  /** Did the learner demonstrate it unaided / confidently? Drives the count, never a grade. */
  confident: boolean;
}

interface FormatProps {
  onComplete?: (signal: FormatSignal) => void;
}

/* ── A shared format frame — overline kicker + the named interaction ───────── */
function FormatFrame({
  name,
  hint,
  children,
  footer,
}: {
  name: string;
  hint: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <article className="format-card next-step-hero" style={{ padding: 'var(--space-6)' }}>
      <div className="row-between" style={{ alignItems: 'flex-start' }}>
        <p className="overline" style={{ margin: 0 }}>
          {name}
        </p>
        <Tag tone="neutral">{hint}</Tag>
      </div>
      <div style={{ marginTop: 'var(--space-4)' }}>{children}</div>
      {footer ? <div style={{ marginTop: 'var(--space-5)' }}>{footer}</div> : null}
    </article>
  );
}

/* ── Flashcard — flip + counter + self-rate ────────────────────────────────── */

interface Flashcard {
  front: string;
  back: string;
}

const FLASHCARDS: Flashcard[] = [
  { front: 'sin θ', back: 'opposite / hypotenuse' },
  { front: 'cos θ', back: 'adjacent / hypotenuse' },
  { front: 'tan θ', back: 'opposite / adjacent (= sin θ / cos θ)' },
  { front: 'sin²θ + cos²θ', back: '= 1 (the Pythagorean identity)' },
  { front: 'sin 30°', back: '= 1/2' },
];

export function FlashcardDeck({ onComplete }: FormatProps) {
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [knew, setKnew] = useState(0);
  const [done, setDone] = useState(false);

  const card = FLASHCARDS[index]!;

  function rate(confident: boolean) {
    if (confident) setKnew((k) => k + 1);
    const last = index + 1 >= FLASHCARDS.length;
    if (last) {
      setDone(true);
      onComplete?.({ confident: knew + (confident ? 1 : 0) >= Math.ceil(FLASHCARDS.length * 0.6) });
    } else {
      setIndex((i) => i + 1);
      setFlipped(false);
    }
  }

  function restart() {
    setIndex(0);
    setFlipped(false);
    setKnew(0);
    setDone(false);
  }

  if (done) {
    return (
      <FormatFrame name="Flashcards" hint={`${FLASHCARDS.length} cards`}>
        <div className="format-done">
          <Icon name="spark" size="lg" className="glyph" />
          <h4 className="body" style={{ margin: 0 }}>
            You knew {knew} of {FLASHCARDS.length} on sight
          </h4>
          <p className="caption muted" style={{ margin: 0 }}>
            The ones you flipped to check are exactly the ones worth a second pass — no marks, just recall.
          </p>
          <Button variant="secondary" size="sm" onClick={restart}>
            Run the deck again
          </Button>
        </div>
      </FormatFrame>
    );
  }

  return (
    <FormatFrame name="Flashcards" hint={`Card ${index + 1} / ${FLASHCARDS.length}`}>
      <button
        type="button"
        className={`flashcard${flipped ? ' flipped' : ''}`}
        onClick={() => setFlipped((f) => !f)}
        aria-label={flipped ? `Back: ${card.back}. Tap to flip.` : `Front: ${card.front}. Tap to reveal.`}
      >
        <span className="flashcard-inner">
          <span className="flashcard-face flashcard-front">
            <span className="overline">recall</span>
            <span className="display-sm" style={{ fontSize: 28 }}>
              {card.front}
            </span>
          </span>
          <span className="flashcard-face flashcard-back">
            <span className="overline">answer</span>
            <span className="body-lg">{card.back}</span>
          </span>
        </span>
      </button>
      <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
        {!flipped ? (
          <Button variant="secondary" size="sm" onClick={() => setFlipped(true)}>
            Flip the card
          </Button>
        ) : (
          <>
            <Button variant="accent" size="sm" onClick={() => rate(true)}>
              <Icon name="check" size="sm" />
              I knew it
            </Button>
            <Button variant="secondary" size="sm" onClick={() => rate(false)}>
              Show me again later
            </Button>
          </>
        )}
      </div>
    </FormatFrame>
  );
}

/* ── Fill the blank — drag (or click) word pills into slots ─────────────────── */

interface FillBlankSpec {
  /** The sentence, split on '___' markers. parts.length === blanks + 1. */
  parts: string[];
  /** The correct word for each blank, in order. */
  answers: string[];
  /** Extra distractor pills shuffled in. */
  distractors: string[];
}

const FILL_BLANK: FillBlankSpec = {
  parts: ['In a right triangle, sine is ', ' over hypotenuse, and cosine is ', ' over hypotenuse.'],
  answers: ['opposite', 'adjacent'],
  distractors: ['tangent'],
};

export function FillBlank({ onComplete }: FormatProps) {
  const pool = useMemo(
    () => [...FILL_BLANK.answers, ...FILL_BLANK.distractors].sort(() => 0.5 - hashSort()),
    [],
  );
  const [placed, setPlaced] = useState<(string | null)[]>(
    Array(FILL_BLANK.answers.length).fill(null),
  );
  const [active, setActive] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);

  const used = new Set(placed.filter(Boolean) as string[]);
  const allFilled = placed.every(Boolean);
  const correct = placed.every((p, i) => p === FILL_BLANK.answers[i]);

  function placeInto(slot: number, word: string) {
    setPlaced((prev) => {
      const next = [...prev];
      // Remove the word from any other slot first.
      for (let i = 0; i < next.length; i++) if (next[i] === word) next[i] = null;
      next[slot] = word;
      return next;
    });
    setActive(null);
    setChecked(false);
  }

  function clearSlot(slot: number) {
    setPlaced((prev) => {
      const next = [...prev];
      next[slot] = null;
      return next;
    });
    setChecked(false);
  }

  function check() {
    setChecked(true);
    if (correct) onComplete?.({ confident: true });
  }

  function reset() {
    setPlaced(Array(FILL_BLANK.answers.length).fill(null));
    setActive(null);
    setChecked(false);
  }

  return (
    <FormatFrame name="Fill the blank" hint="drag or tap a word">
      <p className="body-lg" style={{ lineHeight: 1.9 }}>
        {FILL_BLANK.parts.map((part, i) => (
          <span key={i}>
            {part}
            {i < FILL_BLANK.answers.length ? (
              <button
                type="button"
                className={`blank-slot${placed[i] ? ' filled' : ''}${
                  checked ? (placed[i] === FILL_BLANK.answers[i] ? ' ok' : ' miss') : ''
                }`}
                onClick={() => (placed[i] ? clearSlot(i) : active ? placeInto(i, active) : undefined)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const word = e.dataTransfer.getData('text/plain');
                  if (word) placeInto(i, word);
                }}
                aria-label={placed[i] ? `Blank ${i + 1}: ${placed[i]}. Tap to clear.` : `Blank ${i + 1}, empty`}
              >
                {placed[i] ?? '    '}
              </button>
            ) : null}
          </span>
        ))}
      </p>

      <div className="pill-tray" role="group" aria-label="Word pills">
        {pool.map((word) => {
          const isUsed = used.has(word);
          return (
            <button
              key={word}
              type="button"
              className={`word-pill${active === word ? ' active' : ''}${isUsed ? ' used' : ''}`}
              draggable={!isUsed}
              onDragStart={(e) => e.dataTransfer.setData('text/plain', word)}
              onClick={() => setActive((a) => (a === word ? null : word))}
              disabled={isUsed}
            >
              {word}
            </button>
          );
        })}
      </div>
      {active ? (
        <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
          Now tap a blank to drop &ldquo;{active}&rdquo; in — or drag it.
        </p>
      ) : null}

      <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
        <Button variant="accent" size="sm" disabled={!allFilled} onClick={check}>
          Check it
        </Button>
        <Button variant="ghost" size="sm" onClick={reset}>
          Reset
        </Button>
        {checked ? (
          <span className={`state-pill ${correct ? 'correct' : 'misunderstood'}`}>
            <span className="dot" />
            {correct ? 'That reads right' : 'Not quite — try swapping the two'}
          </span>
        ) : null}
      </div>
    </FormatFrame>
  );
}

/* ── Matching — pair terms to their definitions ────────────────────────────── */

interface MatchPair {
  term: string;
  def: string;
}

const MATCH_PAIRS: MatchPair[] = [
  { term: 'Reflection', def: 'Angle of incidence equals angle of reflection' },
  { term: 'Refraction', def: 'Light bends as its speed changes between media' },
  { term: "Ohm's law", def: 'V = IR at constant temperature' },
];

export function Matching({ onComplete }: FormatProps) {
  const defs = useMemo(() => MATCH_PAIRS.map((p) => p.def).sort(() => 0.5 - hashSort()), []);
  const [selTerm, setSelTerm] = useState<string | null>(null);
  const [links, setLinks] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);

  const allLinked = Object.keys(links).length === MATCH_PAIRS.length;
  const correctCount = MATCH_PAIRS.filter((p) => links[p.term] === p.def).length;
  const allCorrect = correctCount === MATCH_PAIRS.length;

  function linkDef(def: string) {
    if (!selTerm) return;
    setLinks((prev) => {
      const next = { ...prev };
      // A def can only pair once.
      for (const t of Object.keys(next)) if (next[t] === def) delete next[t];
      next[selTerm] = def;
      return next;
    });
    setSelTerm(null);
    setChecked(false);
  }

  function check() {
    setChecked(true);
    if (allCorrect) onComplete?.({ confident: true });
  }

  function reset() {
    setLinks({});
    setSelTerm(null);
    setChecked(false);
  }

  return (
    <FormatFrame name="Matching" hint="tap a term, then its match">
      <div className="match-grid">
        <div className="match-col" role="listbox" aria-label="Terms">
          {MATCH_PAIRS.map((p) => {
            const linked = links[p.term];
            const ok = checked && linked === p.def;
            const miss = checked && linked && linked !== p.def;
            return (
              <button
                key={p.term}
                type="button"
                className={`match-item${selTerm === p.term ? ' active' : ''}${ok ? ' ok' : ''}${miss ? ' miss' : ''}`}
                onClick={() => setSelTerm((t) => (t === p.term ? null : p.term))}
              >
                <span className="match-term">{p.term}</span>
                {linked ? <span className="match-linked caption muted">→ {linked}</span> : null}
              </button>
            );
          })}
        </div>
        <div className="match-col" role="listbox" aria-label="Definitions">
          {defs.map((def) => {
            const taken = Object.values(links).includes(def);
            return (
              <button
                key={def}
                type="button"
                className={`match-item def${taken ? ' used' : ''}`}
                onClick={() => linkDef(def)}
                disabled={!selTerm}
              >
                {def}
              </button>
            );
          })}
        </div>
      </div>
      <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
        <Button variant="accent" size="sm" disabled={!allLinked} onClick={check}>
          Check the pairs
        </Button>
        <Button variant="ghost" size="sm" onClick={reset}>
          Reset
        </Button>
        {checked ? (
          <span className={`state-pill ${allCorrect ? 'correct' : 'incomplete'}`}>
            <span className="dot" />
            {allCorrect ? 'All paired correctly' : `${correctCount} of ${MATCH_PAIRS.length} so far`}
          </span>
        ) : null}
      </div>
    </FormatFrame>
  );
}

/* ── Predict then check — commit a prediction BEFORE the reveal ─────────────── */

export function PredictThenCheck({ onComplete }: FormatProps) {
  const [choice, setChoice] = useState<number | null>(null);
  const [committed, setCommitted] = useState(false);
  const options = ['It increases', 'It stays the same', 'It decreases'];
  const correctIndex = 2;

  function commit() {
    if (choice === null) return;
    setCommitted(true);
    onComplete?.({ confident: choice === correctIndex });
  }

  return (
    <FormatFrame name="Predict, then check" hint="commit before you peek">
      <p className="body-lg" style={{ fontWeight: 500 }}>
        A fixed voltage drives a circuit. If you increase the resistance, what happens to the current?
      </p>
      <div className="predict-options" role="radiogroup" aria-label="Your prediction" style={{ marginTop: 'var(--space-3)' }}>
        {options.map((opt, i) => (
          <button
            key={i}
            type="button"
            role="radio"
            aria-checked={choice === i}
            className={`predict-option${choice === i ? ' selected' : ''}${
              committed ? (i === correctIndex ? ' ok' : choice === i ? ' miss' : '') : ''
            }`}
            onClick={() => !committed && setChoice(i)}
            disabled={committed}
          >
            {opt}
          </button>
        ))}
      </div>

      {!committed ? (
        <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
          <Button variant="accent" size="sm" disabled={choice === null} onClick={commit}>
            Lock in my prediction
          </Button>
          <span className="caption muted">Nothing is revealed until you commit — that is what makes it stick.</span>
        </div>
      ) : (
        <div className="reveal" style={{ marginTop: 'var(--space-4)' }}>
          <p className="overline" style={{ margin: 0 }}>
            Now the reveal
          </p>
          <p className="body" style={{ marginTop: 'var(--space-3)' }}>
            Current <strong>decreases</strong>. With V fixed, I = V / R, so a larger R means a smaller I.
            {choice === correctIndex
              ? ' Your prediction held — and committing it first is why it will stay.'
              : ' Comparing your prediction to this is exactly where the learning happens.'}
          </p>
        </div>
      )}
    </FormatFrame>
  );
}

/* ── Assemble the proof — order the steps into a valid chain ────────────────── */

const PROOF_STEPS = [
  'Let the opposite side be 3 and the hypotenuse be 5.',
  'By Pythagoras, the adjacent side is √(5² − 3²) = 4.',
  'So sin θ = 3/5 and cos θ = 4/5.',
  'Therefore tan θ = sin θ / cos θ = 3/4.',
];

export function AssembleTheProof({ onComplete }: FormatProps) {
  const [order, setOrder] = useState<number[]>(() => shuffleIndices(PROOF_STEPS.length));
  const [checked, setChecked] = useState(false);

  const correct = order.every((v, i) => v === i);

  function move(from: number, dir: -1 | 1) {
    const to = from + dir;
    if (to < 0 || to >= order.length) return;
    setOrder((prev) => {
      const next = [...prev];
      [next[from], next[to]] = [next[to]!, next[from]!];
      return next;
    });
    setChecked(false);
  }

  function check() {
    setChecked(true);
    if (correct) onComplete?.({ confident: true });
  }

  return (
    <FormatFrame name="Assemble the proof" hint="put the steps in order">
      <p className="caption quiet">Order the steps so the argument flows. Use the arrows to move a step.</p>
      <ol className="proof-list">
        {order.map((stepIdx, pos) => (
          <li key={stepIdx} className={`proof-step${checked ? (stepIdx === pos ? ' ok' : ' miss') : ''}`}>
            <span className="proof-num" aria-hidden="true">
              {pos + 1}
            </span>
            <span className="proof-text">{PROOF_STEPS[stepIdx]}</span>
            <span className="proof-moves">
              <button type="button" aria-label="Move up" disabled={pos === 0} onClick={() => move(pos, -1)}>
                <Icon name="chevron-down" size="sm" style={{ transform: 'rotate(180deg)' }} />
              </button>
              <button
                type="button"
                aria-label="Move down"
                disabled={pos === order.length - 1}
                onClick={() => move(pos, 1)}
              >
                <Icon name="chevron-down" size="sm" />
              </button>
            </span>
          </li>
        ))}
      </ol>
      <div className="rec-actions" style={{ marginTop: 'var(--space-3)' }}>
        <Button variant="accent" size="sm" onClick={check}>
          Check the order
        </Button>
        {checked ? (
          <span className={`state-pill ${correct ? 'correct' : 'incomplete'}`}>
            <span className="dot" />
            {correct ? 'A valid chain — that is the proof' : 'Close — one or two steps are out of place'}
          </span>
        ) : null}
      </div>
    </FormatFrame>
  );
}

/* ── Fill the missing step — supply the gap in a worked solution ────────────── */

export function FillTheMissingStep({ onComplete }: FormatProps) {
  const options = [
    'Multiply both sides by R',
    'Divide both sides by I',
    'Add I to both sides',
  ];
  const correctIndex = 1;
  const [choice, setChoice] = useState<number | null>(null);
  const [checked, setChecked] = useState(false);

  function check() {
    if (choice === null) return;
    setChecked(true);
    if (choice === correctIndex) onComplete?.({ confident: true });
  }

  return (
    <FormatFrame name="Fill the missing step" hint="one step is blank">
      <ol className="proof-list static">
        <li className="proof-step">
          <span className="proof-num">1</span>
          <span className="proof-text">Start from Ohm&rsquo;s law: V = I × R.</span>
        </li>
        <li className="proof-step gap">
          <span className="proof-num">2</span>
          <span className="proof-text">
            <strong>Missing step:</strong> {checked && choice === correctIndex ? options[correctIndex] : '???'}
          </span>
        </li>
        <li className="proof-step">
          <span className="proof-num">3</span>
          <span className="proof-text">Conclude: R = V / I.</span>
        </li>
      </ol>
      <div className="predict-options" role="radiogroup" aria-label="Choose the missing step" style={{ marginTop: 'var(--space-3)' }}>
        {options.map((opt, i) => (
          <button
            key={i}
            type="button"
            role="radio"
            aria-checked={choice === i}
            className={`predict-option${choice === i ? ' selected' : ''}${
              checked ? (i === correctIndex ? ' ok' : choice === i ? ' miss' : '') : ''
            }`}
            onClick={() => !checked && setChoice(i)}
          >
            {opt}
          </button>
        ))}
      </div>
      <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
        <Button variant="accent" size="sm" disabled={choice === null} onClick={check}>
          Place the step
        </Button>
        {checked ? (
          <span className={`state-pill ${choice === correctIndex ? 'correct' : 'misunderstood'}`}>
            <span className="dot" />
            {choice === correctIndex ? 'That completes the chain' : 'Re-read step 3 — what undoes the × R?'}
          </span>
        ) : null}
      </div>
    </FormatFrame>
  );
}

/* ── Teach it back — explain in your own words, self-check against cues ─────── */

const TEACH_CUES = [
  'You named the right triangle sides (opposite, adjacent, hypotenuse).',
  'You linked sine to opposite/hypotenuse and cosine to adjacent/hypotenuse.',
  'You explained why tan θ = sin θ / cos θ.',
];

export function TeachItBack({ onComplete }: FormatProps) {
  const [text, setText] = useState('');
  const [checked, setChecked] = useState<boolean[]>(Array(TEACH_CUES.length).fill(false));
  const [revealed, setRevealed] = useState(false);

  const ticked = checked.filter(Boolean).length;

  function toggle(i: number) {
    setChecked((prev) => {
      const next = [...prev];
      next[i] = !next[i];
      return next;
    });
  }

  function finish() {
    setRevealed(true);
    onComplete?.({ confident: ticked >= 2 && text.trim().length > 20 });
  }

  return (
    <FormatFrame name="Teach it back" hint="explain it in your words">
      <p className="body-lg" style={{ fontWeight: 500 }}>
        Explain how to find sin θ and cos θ in a right triangle — as if teaching a friend.
      </p>
      <textarea
        className="teach-area"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="In your own words…"
        rows={5}
        aria-label="Your explanation"
      />
      <p className="overline" style={{ margin: 'var(--space-4) 0 var(--space-2)' }}>
        Self-check — did your explanation cover these?
      </p>
      <div className="teach-cues">
        {TEACH_CUES.map((cue, i) => (
          <label key={i} className={`teach-cue${checked[i] ? ' on' : ''}`}>
            <input type="checkbox" checked={checked[i]} onChange={() => toggle(i)} />
            <span className="teach-tick" aria-hidden="true">
              <Icon name="check" size="sm" />
            </span>
            <span>{cue}</span>
          </label>
        ))}
      </div>
      <div className="rec-actions" style={{ marginTop: 'var(--space-4)' }}>
        <Button variant="accent" size="sm" disabled={text.trim().length === 0} onClick={finish}>
          I have explained it
        </Button>
        {revealed ? (
          <span className="state-pill correct">
            <span className="dot" />
            {ticked >= 2 ? 'Teaching it back is the strongest signal you know it' : 'Good start — fill the cue you missed'}
          </span>
        ) : null}
      </div>
      <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
        Nothing here grades your wording — explaining it yourself is the point, and the cues are just a mirror.
      </p>
    </FormatFrame>
  );
}

/* ── helpers ────────────────────────────────────────────────────────────────
   A deterministic, no-PII "shuffle" — just enough to vary order each mount
   without depending on Math.random in render. */
let hashSeed = 7;
function hashSort(): number {
  hashSeed = (hashSeed * 9301 + 49297) % 233280;
  return hashSeed / 233280;
}
function shuffleIndices(n: number): number[] {
  const arr = Array.from({ length: n }, (_, i) => i);
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(hashSort() * (i + 1));
    [arr[i], arr[j]] = [arr[j]!, arr[i]!];
  }
  // Never start already-solved.
  if (arr.every((v, i) => v === i) && n > 1) [arr[0], arr[1]] = [arr[1]!, arr[0]!];
  return arr;
}

/* ── The registry — name → component, for the hub picker ───────────────────── */

export type FormatKey =
  | 'flashcard'
  | 'fill-blank'
  | 'matching'
  | 'predict'
  | 'assemble'
  | 'missing-step'
  | 'teach-back';

export interface FormatMeta {
  key: FormatKey;
  name: string;
  blurb: string;
  Component: (props: FormatProps) => ReactNode;
}

export const PRACTICE_FORMATS: FormatMeta[] = [
  { key: 'flashcard', name: 'Flashcards', blurb: 'Flip a card, rate your recall.', Component: FlashcardDeck },
  { key: 'fill-blank', name: 'Fill the blank', blurb: 'Drag the right word into the gap.', Component: FillBlank },
  { key: 'matching', name: 'Matching', blurb: 'Pair each term with its meaning.', Component: Matching },
  { key: 'predict', name: 'Predict, then check', blurb: 'Commit a prediction before the reveal.', Component: PredictThenCheck },
  { key: 'assemble', name: 'Assemble the proof', blurb: 'Order the steps into a valid chain.', Component: AssembleTheProof },
  { key: 'missing-step', name: 'Fill the missing step', blurb: 'Supply the one missing line of a solution.', Component: FillTheMissingStep },
  { key: 'teach-back', name: 'Teach it back', blurb: 'Explain it in your own words.', Component: TeachItBack },
];
