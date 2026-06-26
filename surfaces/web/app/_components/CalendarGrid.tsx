'use client';

import { useMemo } from 'react';
import { SourceNote } from './SourceNote';
import type { CalendarEvent, CalendarMonth, EventType, ReadSource } from '@/lib/vizData';

/* ============================================================================
   CalendarGrid — a monthly calendar with cool/brand-coded event types. The v2
   academic calendar + event view, carried into the v3 grammar: one calm month
   grid, an upcoming list, a legend; depth = hairline + tonal step, NO shadow,
   reduced-motion safe. Event types use the cool accent palette only — never a
   coral / warm-orange. Pure + data-driven (takes a CalendarMonth prop).
   ============================================================================ */

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const EVENT_LABEL: Record<EventType, string> = {
  exam: 'Assessment',
  ptm: 'Parent meeting',
  holiday: 'Holiday',
  homework: 'Homework due',
  activity: 'Activity',
};

export interface CalendarGridProps {
  month: CalendarMonth;
  source?: ReadSource;
}

export function CalendarGrid({ month, source = 'fallback' }: CalendarGridProps) {
  // Index events by day so each cell can render its dots.
  const byDay = useMemo(() => {
    const map = new Map<number, CalendarEvent[]>();
    for (const e of month.events) {
      const list = map.get(e.day) ?? [];
      list.push(e);
      map.set(e.day, list);
    }
    return map;
  }, [month.events]);

  const upcoming = useMemo(
    () => [...month.events].sort((a, b) => a.day - b.day),
    [month.events],
  );

  const usedTypes = useMemo(() => {
    const set = new Set<EventType>();
    for (const e of month.events) set.add(e.type);
    return [...set];
  }, [month.events]);

  return (
    <div className="stack viz-card" style={{ gap: 'var(--space-4)' }}>
      <div className="sec-head">
        <h4 className="h4" style={{ margin: 0 }}>{month.label}</h4>
        <span className="overline">{month.events.length} events</span>
      </div>

      <div className="cal-grid" role="grid" aria-label={`${month.label} calendar`}>
        {WEEKDAYS.map((wd) => (
          <div className="cal-weekday" key={wd} role="columnheader">{wd}</div>
        ))}
        {Array.from({ length: month.startWeekday }).map((_, i) => (
          <div className="cal-cell cal-cell-pad" key={`pad-${i}`} aria-hidden="true" />
        ))}
        {Array.from({ length: month.days }).map((_, i) => {
          const day = i + 1;
          const events = byDay.get(day) ?? [];
          return (
            <div className="cal-cell" key={day} role="gridcell" aria-label={`${month.label} ${day}${events.length ? `, ${events.length} events` : ''}`}>
              <span className="cal-daynum">{day}</span>
              {events.length > 0 ? (
                <div className="cal-events">
                  {events.map((e, j) => (
                    <span className="cal-event" data-type={e.type} key={j} title={`${EVENT_LABEL[e.type]}: ${e.label}`}>
                      <span className="cal-event-dot" data-type={e.type} aria-hidden="true" />
                      <span className="cal-event-label">{e.label}</span>
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="cal-legend" aria-hidden="true">
        {usedTypes.map((t) => (
          <span className="cal-legend-item" key={t}>
            <span className="cal-event-dot" data-type={t} /> {EVENT_LABEL[t]}
          </span>
        ))}
      </div>

      <div className="stack" style={{ gap: 'var(--space-2)' }}>
        <p className="overline">Coming up</p>
        <ul className="cal-upcoming">
          {upcoming.map((e, i) => (
            <li className="cal-upcoming-row" key={i}>
              <span className="cal-event-dot" data-type={e.type} aria-hidden="true" />
              <span className="data cal-upcoming-day">{month.label.slice(0, 3)} {e.day}</span>
              <span className="cal-upcoming-label">{e.label}</span>
            </li>
          ))}
        </ul>
      </div>

      <SourceNote source={source} />
    </div>
  );
}
