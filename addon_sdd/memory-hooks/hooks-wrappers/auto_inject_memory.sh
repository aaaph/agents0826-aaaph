#!/usr/bin/env bash
# Repo-relative wrapper for relevance-gated memory auto-injection.
# Never blocks the prompt: swallows errors, always exits 0.
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$HOOKS_DIR/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
"$PY" "$HOOKS_DIR/hooks/auto_inject_memory.py" 2>/dev/null || true
exit 0
