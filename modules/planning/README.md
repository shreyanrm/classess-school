# planning (d6) - Teacher planning & instruction design

Adaptive teacher planning for the Classess system. Builds annual, unit, weekly,
and daily plans mapped to ontology learning outcomes; adapts each plan to
yesterday's completion and performance; differentiates instruction by learner
readiness band; maintains a planned-vs-delivered teacher diary; and feeds a
pacing-protection signal to the scheduling module.

## Modules

- `app/plans.py` - adaptive annual/unit/weekly/daily plans mapped to the
  ontology. Incomplete items roll forward, weak outcomes gain reinforcement,
  strongly mastered outcomes are compressed.
- `app/differentiation.py` - readiness-aware differentiation. Each learner is
  assigned a mastery band (emerging, developing, secure, extending) from an
  opaque mastery estimate and receives a band-appropriate task. Tasks never
  cross band boundaries.
- `app/diary.py` - the teacher diary. Tracks planned vs delivered for each plan
  item and auto-updates from delivery signals.
- `app/pacing_link.py` - builds advisory pacing signals (behind / on-track /
  ahead) and routes them to scheduling. Consequential timetable changes are
  advisory only and never auto-fired.
- `app/events.py` - immutable, append-only planning events. Payloads carry only
  the opaque `canonical_uuid`; a runtime guard rejects PII-looking keys.

## Boundaries and invariants

- Behavioral data references subjects by opaque `canonical_uuid` only; never PII.
- Events are immutable and append-only; corrections are successor events.
- Cross-context dependencies (the ontology resolver, the scheduling intake
  adapter, the intelligence mastery source) are injected. With nothing injected
  the package degrades gracefully and runs with no network or DB.
- Pacing and any consequential action are advisory; human/scheduler approval
  applies downstream (permission ladder). A confidence gate withholds
  low-confidence signals for human review.
- The intelligence spine and scheduling module are consumed, never modified.

## Environment variables

Secrets are ENV-only and server-side (never `NEXT_PUBLIC_*`). Names follow
`clss.<app>.<env>.<purpose>`:

- `clss.planning.<env>.gateway_url` - gateway base URL all calls pass through.
- `clss.planning.<env>.gateway_token` - service token for gateway auth.
- `clss.planning.<env>.event_sink_dsn` - append-only event sink connection.
- `clss.planning.<env>.scheduling_intake_url` - scheduling pacing-intake adapter.
- `clss.planning.<env>.intelligence_mastery_url` - intelligence spine mastery
  read endpoint (consent-gated, returns canonical_uuid-keyed estimates).
- `clss.planning.<env>.ontology_resolver_url` - ontology outcome resolver.

No values are hardcoded. Absent any of these, the relevant feature degrades
gracefully and the rest of the package continues to function.

## Testing

```
pytest modules/planning/tests
```

Tests are import-safe and pass with no network or DB. They verify: plans map to
ontology outcomes, plans adapt to prior performance (rollover / reinforce /
compress), the diary tracks planned vs delivered, and differentiation respects
mastery bands.
