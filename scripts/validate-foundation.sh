#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$repo_root"
source scripts/dev-env.sh >/dev/null

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing .venv. Run scripts/bootstrap-local.sh first." >&2
  exit 1
fi

echo "Running Python syntax checks..."
find app tests -name "*.py" -print0 | xargs -0 .venv/bin/python -m py_compile

echo "Running pytest..."
.venv/bin/python -m pytest

if command -v docker >/dev/null 2>&1; then
  echo "Validating docker compose..."
  docker compose config >/dev/null
else
  echo "Docker CLI not available in this environment."
  exit 1
fi

echo "Foundation validation complete."
