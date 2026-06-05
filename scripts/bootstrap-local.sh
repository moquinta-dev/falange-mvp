#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$repo_root"
source scripts/dev-env.sh >/dev/null

if [ ! -d ".venv" ]; then
  uv venv .venv
fi

uv pip install -r requirements.txt

echo "Local Python environment ready."
echo "Activate with: source .venv/bin/activate"
