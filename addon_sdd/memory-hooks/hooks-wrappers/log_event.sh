#!/usr/bin/env bash
# Repo-relative wrapper — works for any teammate regardless of clone location.
# Resolves the memory-hooks dir from this script's path, prefers local .venv.
set -euo pipefail
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$HOOKS_DIR/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
exec "$PY" "$HOOKS_DIR/hooks/log_event.py" --client claude_code
