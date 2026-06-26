'use client';

import { useEffect, useState } from 'react';
import { Button, Icon, Input, Matrix, SpotlightCard, Tag } from '@classess/design-system';
import { StatCell } from './StatCell';
import { EvidenceDrawer } from './EvidenceDrawer';
import { SourceNote } from './SourceNote';
import type { ReadSource } from '@/lib/vizData';
import type { AdminConfigValue } from '@/lib/adminConfig';

/* ============================================================================
   AccessControlConfig — attendance ACCESS-CONTROL configuration, in the v3
   grammar. The v2 "Attendance Access Control (geofencing)" screen, recomposed.

   What it sets: a CAMPUS geofence (centre latitude / longitude + a radius in
   metres) and a daily TIME WINDOW (open → close) within which a mark may be
   taken, plus the capture method (manual roster / auto / staff-assisted). It is
   a RULE about WHERE and WHEN a mark is valid — it is campus geometry, never a
   tracker of a person. No location is ever read or stored for any individual;
   the geofence is checked at the moment of a mark and the result (inside /
   outside the window) is all that is kept.

   v3 laws honoured here:
     · Permission ladder — the config is PREPARED in the form and only saved on
       an explicit "Save the access rule" press; nothing is auto-applied, and a
       wall denial / no-db simply leaves the form editable on the seed.
     · PII-free — coordinates describe the campus, not a student. The copy says
       so plainly; an EvidenceDrawer makes the reasoning auditable.
     · Cool ultramarine signature, hairline + tonal depth, NO shadow,
       reduced-motion safe. Pure + data-driven; the host owns persistence.
   ============================================================================ */

type CaptureMethod = 'manual' | 'auto' | 'staff';

const METHOD_LABEL: Record<CaptureMethod, string> = {
  manual: 'Manual roster',
  auto: 'Automatic (geofenced)',
  staff: 'Staff-assisted',
};

const METHOD_NOTE: Record<CaptureMethod, string> = {
  manual: 'A teacher marks the roster; the geofence and window are advisory only — never blocking.',
  auto: 'A mark is accepted only inside the campus geofence and within the time window. Outside either, it is held for a person, never silently rejected.',
  staff: 'Front-office staff mark on a student’s behalf; the same window and geofence apply as advisory checks.',
};

/** The persisted shape this surface owns — plain scalars on the admin-config seam. */
export interface AccessControlValues {
  enabled: boolean;
  method: CaptureMethod;
  /** Decimal degrees, as strings so the field stays empty-able. */
  lat: string;
  lng: string;
  /** Radius in metres. */
  radius: string;
  /** "HH:MM" tokens. */
  openTime: string;
  closeTime: string;
}

export const ACCESS_CONTROL_FALLBACK: AccessControlValues = {
  enabled: false,
  method: 'manual',
  lat: '12.9716',
  lng: '77.5946',
  radius: '150',
  openTime: '08:00',
  closeTime: '09:30',
};

export interface AccessControlConfigProps {
  /** The persisted config (merged over the seed) from the admin-config seam. */
  config: Record<string, AdminConfigValue>;
  source?: ReadSource;
  /** Persist one config set through the wall — host owns the round-trip. */
  onSet: (key: string, value: AdminConfigValue) => Promise<{ persisted: boolean }>;
}

function readValues(config: Record<string, AdminConfigValue>): AccessControlValues {
  const method = config.acMethod;
  return {
    enabled: config.acEnabled === true,
    method: method === 'auto' || method === 'staff' || method === 'manual' ? (method as CaptureMethod) : 'manual',
    lat: typeof config.acLat === 'string' ? config.acLat : ACCESS_CONTROL_FALLBACK.lat,
    lng: typeof config.acLng === 'string' ? config.acLng : ACCESS_CONTROL_FALLBACK.lng,
    radius:
      typeof config.acRadius === 'string'
        ? config.acRadius
        : typeof config.acRadius === 'number'
          ? String(config.acRadius)
          : ACCESS_CONTROL_FALLBACK.radius,
    openTime: typeof config.acOpen === 'string' ? config.acOpen : ACCESS_CONTROL_FALLBACK.openTime,
    closeTime: typeof config.acClose === 'string' ? config.acClose : ACCESS_CONTROL_FALLBACK.closeTime,
  };
}

const COORD_RE = /^-?\d{1,3}(\.\d+)?$/;
const TIME_RE = /^([01]?\d|2[0-3]):[0-5]\d$/;

export function AccessControlConfig({ config, source = 'fallback', onSet }: AccessControlConfigProps) {
  const saved = readValues(config);
  // Local draft — the form prepares; saving persists through the wall.
  const [draft, setDraft] = useState<AccessControlValues>(saved);
  const [saved_, setSaved_] = useState(false);

  // Re-seed the draft when the rehydrated config arrives (gateway read-back).
  useEffect(() => {
    setDraft(readValues(config));
    setSaved_(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.acEnabled, config.acMethod, config.acLat, config.acLng, config.acRadius, config.acOpen, config.acClose]);

  const latOk = COORD_RE.test(draft.lat.trim()) && Math.abs(Number(draft.lat)) <= 90;
  const lngOk = COORD_RE.test(draft.lng.trim()) && Math.abs(Number(draft.lng)) <= 180;
  const radiusOk = /^\d{2,5}$/.test(draft.radius.trim()) && Number(draft.radius) >= 25;
  const openOk = TIME_RE.test(draft.openTime.trim());
  const closeOk = TIME_RE.test(draft.closeTime.trim());
  const windowOk = openOk && closeOk && draft.openTime < draft.closeTime;
  const valid = latOk && lngOk && radiusOk && windowOk;

  const dirty =
    draft.enabled !== saved.enabled ||
    draft.method !== saved.method ||
    draft.lat !== saved.lat ||
    draft.lng !== saved.lng ||
    draft.radius !== saved.radius ||
    draft.openTime !== saved.openTime ||
    draft.closeTime !== saved.closeTime;

  async function save() {
    // Persist each field as one attributed, append-only config set. The host's
    // seam authorizes at the wall and degrades to seed; nothing auto-applies.
    await Promise.all([
      onSet('acEnabled', draft.enabled),
      onSet('acMethod', draft.method),
      onSet('acLat', draft.lat.trim()),
      onSet('acLng', draft.lng.trim()),
      onSet('acRadius', draft.radius.trim()),
      onSet('acOpen', draft.openTime.trim()),
      onSet('acClose', draft.closeTime.trim()),
    ]);
    setSaved_(true);
  }

  const minutesBetween = (open: string, close: string): number => {
    const [oh = 0, om = 0] = open.split(':').map(Number);
    const [ch = 0, cm = 0] = close.split(':').map(Number);
    return ch * 60 + cm - (oh * 60 + om);
  };
  const windowMins = windowOk ? minutesBetween(draft.openTime, draft.closeTime) : 0;
  const savedWindowMins =
    TIME_RE.test(saved.openTime) && TIME_RE.test(saved.closeTime) && saved.openTime < saved.closeTime
      ? minutesBetween(saved.openTime, saved.closeTime)
      : 0;

  return (
    <div className="stack" style={{ gap: 'var(--space-5)' }}>
      <Matrix columns={4}>
        <StatCell
          label="Access rule"
          value={saved.enabled ? 1 : 0}
          unit={saved.enabled ? ' on' : ' off'}
          delta={saved.enabled ? `applied · ${METHOD_LABEL[saved.method].toLowerCase()}` : 'advisory only'}
          tone={saved.enabled ? 'up' : 'flat'}
        />
        <StatCell label="Geofence radius" value={Number(saved.radius) || 0} unit=" m" delta="around the campus point" tone="flat" />
        <StatCell
          label="Daily window"
          value={savedWindowMins}
          unit=" min"
          delta={`${saved.openTime} → ${saved.closeTime}`}
          tone="flat"
        />
        <StatCell
          label="Held outside the rule"
          value={0}
          delta="a mark is held for a person, never rejected"
          tone="flat"
        />
      </Matrix>

      <SpotlightCard padLg>
        <div className="row-between" style={{ alignItems: 'flex-start', gap: 'var(--space-4)' }}>
          <div>
            <h3 className="body-lg" style={{ margin: 0 }}>
              Attendance access rule
            </h3>
            <p className="body-sm muted" style={{ marginTop: 'var(--space-2)', maxWidth: 560 }}>
              Set where a mark is valid (a campus geofence) and when (a daily window). This is campus
              geometry — it is never a tracker of a person. No individual location is read or stored;
              only whether a mark falls inside the rule.
            </p>
          </div>
          <Button
            variant={draft.enabled ? 'primary' : 'secondary'}
            size="sm"
            aria-pressed={draft.enabled}
            onClick={() => setDraft((d) => ({ ...d, enabled: !d.enabled }))}
          >
            {draft.enabled ? 'Rule on' : 'Rule off'}
          </Button>
        </div>

        <div className="divider" />

        {/* Capture method */}
        <p className="overline" style={{ margin: '0 0 var(--space-2)' }}>How a mark is taken</p>
        <div className="segmented" role="group" aria-label="Capture method">
          {(['manual', 'auto', 'staff'] as CaptureMethod[]).map((m) => (
            <button
              key={m}
              type="button"
              className={draft.method === m ? 'active' : ''}
              aria-pressed={draft.method === m}
              onClick={() => setDraft((d) => ({ ...d, method: m }))}
            >
              {METHOD_LABEL[m]}
            </button>
          ))}
        </div>
        <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
          {METHOD_NOTE[draft.method]}
        </p>

        <div className="divider" />

        {/* Geofence */}
        <p className="overline" style={{ margin: '0 0 var(--space-3)' }}>Campus geofence</p>
        <Matrix columns={3}>
          <Input
            label="Centre latitude"
            inputMode="decimal"
            value={draft.lat}
            onChange={(e) => setDraft((d) => ({ ...d, lat: e.target.value }))}
            error={draft.lat && !latOk ? 'Enter a latitude between −90 and 90.' : undefined}
            placeholder="12.9716"
          />
          <Input
            label="Centre longitude"
            inputMode="decimal"
            value={draft.lng}
            onChange={(e) => setDraft((d) => ({ ...d, lng: e.target.value }))}
            error={draft.lng && !lngOk ? 'Enter a longitude between −180 and 180.' : undefined}
            placeholder="77.5946"
          />
          <Input
            label="Radius (metres)"
            inputMode="numeric"
            hint="At least 25 m, to cover the campus."
            value={draft.radius}
            onChange={(e) => setDraft((d) => ({ ...d, radius: e.target.value }))}
            error={draft.radius && !radiusOk ? 'Enter a radius of 25 m or more.' : undefined}
            placeholder="150"
          />
        </Matrix>

        <div className="divider" />

        {/* Time window */}
        <p className="overline" style={{ margin: '0 0 var(--space-3)' }}>Daily time window</p>
        <Matrix columns={2}>
          <Input
            label="Opens"
            type="time"
            value={draft.openTime}
            onChange={(e) => setDraft((d) => ({ ...d, openTime: e.target.value }))}
            error={draft.openTime && !openOk ? 'Enter a valid time.' : undefined}
          />
          <Input
            label="Closes"
            type="time"
            value={draft.closeTime}
            onChange={(e) => setDraft((d) => ({ ...d, closeTime: e.target.value }))}
            error={
              draft.closeTime && !closeOk
                ? 'Enter a valid time.'
                : openOk && closeOk && draft.openTime >= draft.closeTime
                  ? 'Close must be after open.'
                  : undefined
            }
          />
        </Matrix>
        {windowOk ? (
          <p className="caption quiet" style={{ marginTop: 'var(--space-2)' }}>
            A {windowMins}-minute window each day. A mark outside it is held for a person, never silently rejected.
          </p>
        ) : null}

        <EvidenceDrawer
          claim="How the access rule is checked"
          evidence={[
            'The geofence is campus geometry — a centre point and a radius. It is checked at the moment of a mark; no individual location is read or stored.',
            'The time window defines when a mark is valid. Outside the window or the fence, a mark is held for a person — never auto-rejected, never penalised.',
            'The rule is prepared in this form and applied only when you save it. Nothing changes silently.',
          ]}
          whySeeing="Access control decides where and when an attendance mark counts. Keeping it explicit and PII-free means the rule is auditable and never becomes a tracker of people."
        />

        <div className="divider" />

        {saved_ && !dirty ? (
          <div className="rec-actions">
            <span className="body-sm row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
              <Tag tone="success" dot>Saved</Tag>
              The access rule is recorded. It reads back on your next visit.
            </span>
          </div>
        ) : (
          <div className="rec-actions">
            <Button variant="accent" size="sm" disabled={!valid || !dirty} onClick={save}>
              Save the access rule
            </Button>
            <span className="caption muted">
              {dirty
                ? 'Nothing applies until you save. You hold the rule.'
                : 'No changes to save yet — edit a field above.'}
            </span>
          </div>
        )}
      </SpotlightCard>

      <div className="row" style={{ gap: 'var(--space-3)', alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="caption quiet row" style={{ gap: 'var(--space-2)', alignItems: 'center' }}>
          <Icon name="info" size="sm" /> Campus geometry, not a person — the fence checks a mark, it never tracks anyone.
        </span>
      </div>

      <SourceNote source={source} />
    </div>
  );
}
