#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PATH="$repo_root/.tools/bin:$PATH"
export GH_CONFIG_DIR="$repo_root/.tools/gh-config"

echo "Falange POC environment loaded"
echo "PATH includes: $repo_root/.tools/bin"
echo "GH_CONFIG_DIR: $GH_CONFIG_DIR"
