'use client';

/* ============================================================================
   StudentComposed — the shared composition vocabulary for the student surfaces.

   The student pages used to be sparse colourless white-box lists. These are the
   DENSE, composed building blocks they now ride on — the same pattern the
   sample page uses: a count-up .matrix stat grid, the colour-band subject-card
   grid (the one hit of pigment), the dark ignite-card (the Crystallize moment),
   flag rows, a today timetable, and a Caveat handnote.

   Laws honoured throughout: hairline structure, tonal steps, NO shadow, ONE
   accent per surface (the route hue), subject hues are COOL/brand only. Numbers
   count up (reduced-motion snaps). Plain language — never a raw score.
   ============================================================================ */

import { useEffect, useState, type ReactNode } from 'react';
import Link from 'next/link';
import {
  CrystallizeNode,
  Icon,
  ProgressBar,
  SubjectCard,
  type IconName,
  type SubjectAccent,
} from '@classess/design-system';

/* ── The stat matrix — the count-up metric grid the sample page opens on ───── */

export interface StatItem {
  label: ReactNode;
  /** A number counts up; a node renders as-is. */
  value: number | ReactNode;
  suffix?: string;
  /** A mono delta line under the value. */
  delta?: ReactNode;
  deltaDir?: 'up' | 'down' | 'flat';
}

/**
 * A count-up readout that always settles on the real integer. Eases from 0 on
 * mount; the resting value is the source of truth so it can never get stuck low.
 * Honours reduced-motion (snaps straight to the value, no animation).
 */
function StatValue({ value, suffix }: { value: number; suffix?: string }) {
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    const reduce =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduce || value <= 0) {
      setDisplay(value);
      return;
    }
    let raf = 0;
    let start: number | null = null;
    const dur = 1100;
    setDisplay(0);
    const step = (t: number) => {
      if (start === null) start = t;
      const k = Math.min((t - start) / dur, 1);
      setDisplay(Math.round(k * value));
      if (k < 1) raf = requestAnimationFrame(step);
      else setDisplay(value);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return (
    <div className="cell-value">
      {display}
      {suffix}
    </div>
  );
}

/**
 * A tight stat grid (the .matrix/.cell pattern with shared hairlines). Numbers
 * count up once when scrolled into view; reduced-motion shows the end value.
 */
export function StatMatrix({ stats, columns = 4 }: { stats: StatItem[]; columns?: number }) {
  return (
    <div className="matrix reveal reveal-2" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
      {stats.map((s, i) => (
        <div className="cell" key={i}>
          <div className="cell-label">{s.label}</div>
          {typeof s.value === 'number' ? (
            <StatValue value={s.value} suffix={s.suffix} />
          ) : (
            <div className="cell-value">
              {s.value}
              {s.suffix}
            </div>
          )}
          {s.delta != null ? (
            <div className={`cell-delta ${s.deltaDir ?? 'flat'}`}>{s.delta}</div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

/* ── The subject-card grid — the colour band is the hit of pigment ─────────── */

export interface SubjectCardModel {
  topicId: string;
  subjectName: string;
  code: string;
  accent: SubjectAccent;
  /** The current focus topic under this subject. */
  focus: string;
  /** Plain-language state line — never a raw score. */
  caption: string;
  /** Fill 0–100 — a relative read of how far this subject is, not a mark. */
  progress: number;
  /** Plain-language progress label. */
  progressLabel: string;
  /** True when the latest demonstration was unaided (lights the inline ignite). */
  independent?: boolean;
}

/**
 * The colour-on-top subject grid. The band carries the subject identity (cool
 * hues only); the body holds the focus topic, a plain-language state, and an
 * animated progress bar tinted to the subject. Each card drills into the topic.
 */
export function SubjectGrid({ subjects }: { subjects: SubjectCardModel[] }) {
  return (
    <div className="matrix" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
      {subjects.map((s, i) => (
        <SubjectCard
          key={s.topicId}
          name={s.subjectName}
          code={s.code}
          accent={s.accent}
          className={`reveal reveal-${Math.min(i + 1, 8)}`}
        >
          <div className="row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
            {s.independent ? <CrystallizeNode variant="b" inline resolved label="On your own" /> : null}
            <div className="display-sm" style={{ fontSize: 20 }}>
              {s.focus}
            </div>
          </div>
          <p className="caption" style={{ marginTop: 5 }}>
            {s.caption}
          </p>
          <ProgressBar
            value={s.progress}
            animate
            label={`${s.subjectName} progress`}
            style={{ margin: '14px 0 8px', ['--subject-fill' as string]: `var(--${s.accent})` }}
            className="subject-progress"
          />
          <div className="row-between">
            <span className="data">{s.progressLabel}</span>
            <Link
              href={`/student/topic/${s.topicId}`}
              className="row caption"
              style={{ gap: 4, color: 'var(--text-secondary)' }}
            >
              Open
              <Icon name="arrow-right" size="sm" style={{ width: 13, height: 13 }} />
            </Link>
          </div>
        </SubjectCard>
      ))}
    </div>
  );
}

/* ── The dark ignite-card — the Crystallize / independent-mastery moment ───── */

export function IgniteCard({
  when,
  who,
  detail,
}: {
  when: string;
  who: string;
  detail: string;
}) {
  return (
    <div className="ignite-card reveal reveal-3">
      <div className="row-between" style={{ marginBottom: 14 }}>
        <span className="overline">{when}</span>
        <Icon name="flame" size="sm" style={{ color: 'var(--accent)' }} />
      </div>
      <div className="who">{who}</div>
      <p className="body-sm" style={{ opacity: 0.82, marginTop: 8 }}>
        {detail}
      </p>
    </div>
  );
}

/* ── A panel — the calm aside surface block, with a section head ───────────── */

export function Panel({
  title,
  meta,
  children,
}: {
  title: ReactNode;
  meta?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="panel">
      <div className="sec-head" style={{ marginBottom: 'var(--space-2)' }}>
        <h4 className="h4">{title}</h4>
        {meta != null ? meta : null}
      </div>
      {children}
    </div>
  );
}

/* ── A flag row — icon chip + claim + caption. Optionally a link. ──────────── */

export interface FlagModel {
  icon: IconName;
  title: ReactNode;
  caption: ReactNode;
  href?: string;
}

export function FlagRow({ flag }: { flag: FlagModel }) {
  const inner = (
    <>
      <div className="flag-ic">
        <Icon name={flag.icon} size="sm" />
      </div>
      <div>
        <div className="body-sm" style={{ fontWeight: 500 }}>
          {flag.title}
        </div>
        <p className="caption">{flag.caption}</p>
      </div>
    </>
  );
  return flag.href ? (
    <Link href={flag.href} className="flag flag-link">
      {inner}
    </Link>
  ) : (
    <div className="flag">{inner}</div>
  );
}

/* ── A timetable / schedule row ────────────────────────────────────────────── */

export interface SchedModel {
  t: string;
  title: ReactNode;
  caption: ReactNode;
}

export function SchedRow({ row }: { row: SchedModel }) {
  return (
    <div className="sched">
      <span className="t">{row.t}</span>
      <div>
        <div className="body-sm" style={{ fontWeight: 500 }}>
          {row.title}
        </div>
        <p className="caption">{row.caption}</p>
      </div>
    </div>
  );
}

/* ── A Caveat handnote panel — the human aside the sample page closes on ───── */

export function HandnotePanel({ children }: { children: ReactNode }) {
  return (
    <div className="panel" style={{ padding: '18px 20px' }}>
      <p className="handnote" style={{ fontSize: 22 }}>
        {children}
      </p>
    </div>
  );
}

/* ── A section head at page scale ──────────────────────────────────────────── */

export function SecHead({ title, meta }: { title: ReactNode; meta?: ReactNode }) {
  return (
    <div className="sec-head">
      <h3 className="h3">{title}</h3>
      {meta != null ? meta : null}
    </div>
  );
}
