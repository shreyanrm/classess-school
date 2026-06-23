#!/usr/bin/env bash
# The full local CI gate — the same checks the GitHub workflow runs.
# Usage: bash scripts/ci.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "═══ 1/4  TypeScript typecheck (contracts · design-system · web) ═══"
npm run typecheck

echo "═══ 2/4  TypeScript tests (vitest: contracts · design-system · web) ═══"
npx vitest run

echo "═══ 3/4  Python tests (intelligence · ai-fabric · workflow · coursework · learning · content) ═══"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  # shellcheck disable=SC1091
  . .venv/bin/activate
  pip install -q --upgrade pip
  pip install -q -r requirements-dev.txt
fi
bash scripts/test-python.sh

echo "═══ 4/4  Web production build (catches RSC / route errors) ═══"
npm run build -w @classess/web

echo ""
echo "✓ CI GATE PASSED"
