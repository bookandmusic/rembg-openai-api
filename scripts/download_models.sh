#!/usr/bin/env bash
# Usage:
#   ./scripts/download_models.sh              # list
#   ./scripts/download_models.sh u2netp ...   # pull listed
#   ./scripts/download_models.sh --all        # pull all
# Env: U2NET_HOME (default: ./models)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export U2NET_HOME="${U2NET_HOME:-$ROOT/models}"
mkdir -p "$U2NET_HOME"

cd "$ROOT"
if [[ $# -eq 0 ]]; then
  exec uv run models list --dir "$U2NET_HOME"
fi
if [[ "$1" == "--all" ]]; then
  exec uv run models pull --all --dir "$U2NET_HOME"
fi
exec uv run models pull --dir "$U2NET_HOME" "$@"
