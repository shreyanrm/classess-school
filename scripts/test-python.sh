#!/usr/bin/env bash
# Run the Python test suite across every spine engine and capability module.
# Each module owns its own `app` package, so they are tested in isolation
# (cd into the module) to avoid import-name collisions.
set -euo pipefail
cd "$(dirname "$0")/.."

MODULES=(
  spine/intelligence
  spine/ai-fabric
  spine/workflow
  modules/coursework
  modules/learning
  modules/content
  modules/institution
  modules/scheduling
  modules/learner-record
  modules/communication
  modules/intelligence-views
  modules/ontology-ingestion
  modules/teacher-growth
  spine/integration
  spine/governance
  spine/feature-store
  modules/attendance
  modules/planning
  modules/classroom
  modules/personalization
  spine/model-foundry
)

# Activate the local venv if present (CI installs deps globally instead).
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

fail=0
for m in "${MODULES[@]}"; do
  if [ -d "$m" ]; then
    echo "──────── pytest: $m ────────"
    if ( cd "$m" && python -m pytest -q ); then :; else fail=1; fi
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "PYTHON SUITE: FAILURES ABOVE"
  exit 1
fi
echo "PYTHON SUITE: ALL GREEN"
