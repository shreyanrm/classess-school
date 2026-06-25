# Intelligence views (capability module B11)

The dashboards and analytics composed over the spine proactive loop (A5) and the
governed semantic layer. B11 turns the observe -> interpret -> recommend loop into
"here is what I found, and what to do": a calm, ranked set of alerts, each
carrying its evidence, a confidence band, the owner, a due date, the consequence
of ignoring, and the plain-language why-am-i-seeing-this.

It owns no spine concern. Identity, the event contract, the ontology, and the
mastery/gap engine belong to the spine; B11 only COMPOSES their governed outputs.
Alerts are minted by the spine workflow builders, so the permission ladder and the
full provenance set hold by construction; a dashboard never re-mints a
recommendation and never auto-fires a consequential action.

## One metric, defined once, computed the same everywhere

The keystone is `app/semantic_layer.py`: every number on every screen resolves
through ONE registry. A metric is defined exactly once (key, plain-language label
and definition, the single compute function, grain, unit, and whether a learner
may see a raw number). Registering two definitions under one key raises. The
dashboard headline, the study quadrant, the forecast, target analytics, and
ask-anything all read the same definitions, so the cohort's "mastery" is the same
number wherever it appears.

No raw number or formula is ever surfaced to a learner or parent: non-learner-safe
metrics are banded into plain language; the raw value stays internal.

## Modules

| file | responsibility |
| --- | --- |
| `app/semantic_layer.py` | The governed metric registry — one definition per metric; views resolve through it. Refuses a redefinition. |
| `app/dashboards.py` | Composes the loop into ranked, fully-explainable alerts (spine recommendations) plus headline metrics. |
| `app/study_quadrant.py` | The effort x outcome quadrant; four quadrants, each a different response. |
| `app/target_analytics.py` | Target (human-set goal) vs trajectory, with gap-to-target and full explainability. |
| `app/prediction.py` | Trajectory / forecast from mastery + coverage; reproducible and advisory. |
| `app/ask_anything.py` | A governed natural-language query over the semantic layer: consent-gated, safety-screened, one-definition. `ask_aggregate` composes one question across many scopes (the `/admin/ask` dashboard), every scope resolved through the same definition so the rows are comparable, every gate held per scope. |
| `app/resolution.py` | Surfaces `gap.resolved` — "what improved after the last intervention". Diffs a previous vs current governed profile (the same rule the spine emitter uses) into plain-language, fully evidence-linked improvement items; rolls up across a cohort with a learner count. Mints nothing; advisory. |
| `app/spine_workflow.py` | Bridge that loads the spine workflow builders as source without an `app` name collision. |
| `app/config.py` | Settings; degrades gracefully and names (only) the env vars it needs. |
| `tests/` | pytest: every alert carries the full explainability set; one-metric-one-definition is enforced; predictions are reproducible; ask-anything governance holds. Import-safe, no network/DB. |

## Governance and safety

- Consent (INVARIANT 6): ask-anything refuses a cross-context read without a
  satisfied consent + purpose check.
- Child-safety on every free-text surface: ask-anything screens each question;
  an unscreened question is refused and a flagged question is escalated to a
  qualified human instead of answered.
- Permission ladder (INVARIANT 8): dashboard alerts are non-consequential
  preparation/surfacing steps; they never auto-fire and never sit at
  `safe_automatic`. Sending support material to learners or parents would be a
  separate, consequential recommendation that needs explicit human approval.
- Never from one score: an alert is raised only on a CONFIRMED, corroborated
  cohort gap; a single bad result never raises an alert.
- PII (INVARIANT 1/2): every input is keyed by the opaque `canonical_uuid` and
  opaque ontology ids; no PII enters a metric computation.

## Degraded operation

No live LLM keys or Supabase are required. With no gateway / feature-store /
semantic-layer / consent service configured, the module composes the spine's
deterministic in-memory projections through the built-in metric registry — and
because the composition is pure, the rendered view is identical either way, which
is what makes the dashboards reproducible. `degraded_reasons()` lists the env-var
names whose absence keeps the module on its deterministic path — names only, never
values.

## Environment variables (names only)

Secrets are environment-only, read by NAME, never hardcoded (INVARIANT 4). No
`NEXT_PUBLIC_` secret is ever used. The module holds no outward credentials
(INVARIANT 8); it only references governed services it reads THROUGH the gateway
(INVARIANT 3). Dotted contract names map to `CLSS_INTELLIGENCE_VIEWS_DEV_*`.

| contract name | env var | purpose |
| --- | --- | --- |
| `clss.intelligence_views.dev.gateway_url` | `CLSS_INTELLIGENCE_VIEWS_DEV_GATEWAY_URL` | the gateway every cross-service read passes through |
| `clss.intelligence_views.dev.feature_store_url` | `CLSS_INTELLIGENCE_VIEWS_DEV_FEATURE_STORE_URL` | read the precomputed projections the dashboards compose |
| `clss.intelligence_views.dev.semantic_layer_url` | `CLSS_INTELLIGENCE_VIEWS_DEV_SEMANTIC_LAYER_URL` | the governed semantic-layer resolution service (one definition per metric) |
| `clss.intelligence_views.dev.consent_service_url` | `CLSS_INTELLIGENCE_VIEWS_DEV_CONSENT_SERVICE_URL` | consent + purpose checks gating cross-context reads |
| `clss.intelligence_views.dev.ask_model_route` | `CLSS_INTELLIGENCE_VIEWS_DEV_ASK_MODEL_ROUTE` | route NAME for an optional model-assisted question resolver (the provider key lives in the gateway, never here) |

## Running the tests

The spine `intelligence` and `workflow` packages are consumed as source (no
install or build is run). The tests put them on the path automatically.

```
pip install -r requirements.txt
python -m pytest tests/ -q
```
