# Classess Backend — the single deployable

One FastAPI process that is the whole runnable backend: the **gateway is the
wall** (the only governed door into a capability), and the spine services
(`identity`, `event-store`) plus the capability modules (`institution`,
`ontology-ingestion`, `scheduling`, `content`, `planning`, `coursework`,
`learning`, `attendance`, `classroom`, `learner-record`, `communication`) are
wired **in-process behind it**. "Feature-based modules inside ONE deployable."

```
backend/
  main.py            the single FastAPI app (front door = gateway)
  loader.py          path-based aliasing of each repo `app` package
  requirements.txt   third-party runtime deps (repo libs are imported, not installed)
  Dockerfile         python:3.12-slim image; build context = REPO ROOT
  railway.json       Railway build + start + /health healthcheck
  tests/test_smoke.py  offline TestClient smoke tests
```

## Topology (one process)

| Path | What |
| --- | --- |
| `GET /health` | deployable liveness (bound to `PORT`); lists loaded capabilities + mounted spine |
| `POST /capabilities/{capability}/{operation}` | generic capability door — **every call passes the Wall**: rate-limit → authn → schema → RBAC → ABAC → consent → approval → child-safety → audit. Deny-by-default. |
| `POST /v1/route/{capability}/{operation}` | the gateway's governed routing entrypoint (the wall) |
| `POST /v1/policy/evaluate`, `GET /v1/tracks`, `GET /healthz` | gateway surface |
| `/internal/identity/*`, `/internal/event-store/*` | spine services mounted in-process (the gateway forwards to them when configured) |

No capability is reachable except through the wall. With no real token verifier
wired, the wall's safe defaults **deny every unauthenticated call** — it never
runs open.

## Configuration — environment ONLY, read by NAME (LAW)

No secret is hardcoded or logged. Every dependency is **optional**: absent its
env, the affected service degrades to a clearly-labelled in-memory adapter and
the process still serves `/health`.

| Env var (NAME) | Used by | Absent ⇒ |
| --- | --- | --- |
| `PORT` | the deployable listen port | defaults to 8080 |
| `CLSS_DATABASE_URL` | PII vault / event store / audit sink (pooler URL) | in-memory adapters |
| `CLSS_SUPABASE_URL`, `CLSS_SUPABASE_SERVICE_KEY` | OTP dispatch / auth | degraded dev OTP path |
| `CLSS_AIFABRIC_DEV_GEMINI_API_KEY` | ontology embeddings / AI fabric | AI paths degrade |
| `CLSS_AIFABRIC_DEV_CROSSCHECK_MODEL_KEY` | cross-check model | degrades |
| `REDIS_URL` | OTP/SSO state + rate-limit store | in-process state |

The gateway also reads its own `CLSS_GATEWAY_DEV_*` names (public JWT key,
capability base URLs, audit DB) — see `spine/gateway/app/config.py`. The gateway
holds the **public** verify key only, never the private signing key.

## Run locally

```bash
# from the repo root, using the repo venv
PYTHONPATH=. .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080
# then: curl localhost:8080/health
```

## Test (offline, installs nothing)

```bash
cd backend && ../.venv/bin/python -m pytest -q
```

`tests/test_smoke.py` asserts `/health` is 200 and that an unauthenticated
capability call is denied by the gateway. `conftest.py` puts the repo root on
`sys.path` (no `pip install`).

## Build the image

The Docker build context is the **repository root** (the loader resolves
`spine/` and `modules/` by path):

```bash
docker build -f backend/Dockerfile -t classess-backend .
docker run -e PORT=8080 -p 8080:8080 classess-backend
```

## Deploy on Railway

1. Create a Railway service from this repo. Leave the service **Root Directory
   unset** (= repo root) so the Docker build context includes `spine/` and
   `modules/`.
2. Railway reads `backend/railway.json`:
   - **Builder:** Dockerfile at `backend/Dockerfile`.
   - **Start:** `uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}`.
   - **Healthcheck:** `GET /health`.
   (If you set a `railway.json` per-service location is needed, copy this file to
   the repo root or point the service config at `backend/railway.json`.)
3. Set the env vars you want enabled (table above) in the Railway service
   **Variables**. `PORT` is injected by Railway automatically. Anything you omit
   degrades cleanly — deploy first, add dependencies incrementally.
4. Deploy. The release is healthy when `/health` returns 200.
