#!/usr/bin/env bash
# Onboard a teammate's machine to the shared Claude Code setup.
# Run once after cloning claude-platform: ./deploy/bootstrap-dev.sh
#
# Does:
#   1. Create memory-hooks venv + install deps (incl. e5-small embeddings).
#   2. Pre-download the e5-small model (~120MB).
#   3. Merge team-baseline hooks/plugins into ~/.claude/settings.json
#      (with the cloned memory-hooks path) and set HOOKS_NEO4J_* env.
#   4. Verify connectivity to the shared Neo4j.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS="$ROOT/memory-hooks"
SETTINGS="$HOME/.claude/settings.json"

echo "==> 1/4 venv + deps"
command -v uv >/dev/null 2>&1 || { echo "install uv first: https://docs.astral.sh/uv/"; exit 1; }
cd "$HOOKS"
uv venv --python 3.11 2>/dev/null || true
uv pip install -e ".[embeddings]"

echo "==> 2/4 pre-download e5-small"
"$HOOKS/.venv/bin/python" - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer("intfloat/multilingual-e5-small")
print("e5-small cached")
PY

echo "==> 3/4 merge team baseline into ~/.claude/settings.json"
read -rp "Shared Neo4j password (ask team lead): " -s NEO4J_PW; echo
URI="${HOOKS_NEO4J_URI:-bolt://<NEO4J_HOST>:7687}"
"$HOOKS/.venv/bin/python" - "$SETTINGS" "$ROOT/shared/.claude/settings.json" "$HOOKS" "$URI" "$NEO4J_PW" <<'PY'
import json, os, sys
settings_path, baseline_path, hooks_dir, uri, pw = sys.argv[1:6]
os.makedirs(os.path.dirname(settings_path), exist_ok=True)
cur = json.load(open(settings_path)) if os.path.exists(settings_path) else {}
base = json.load(open(baseline_path))
# merge hooks + plugins, substitute {{MEMORY_HOOKS}}
raw = json.dumps(base).replace("{{MEMORY_HOOKS}}", hooks_dir)
base = json.loads(raw)
cur.setdefault("hooks", {}).update(base.get("hooks", {}))
cur.setdefault("enabledPlugins", {}).update(base.get("enabledPlugins", {}))
cur.setdefault("env", {})
cur["env"]["HOOKS_NEO4J_URI"] = uri
cur["env"]["HOOKS_NEO4J_USER"] = "neo4j"
cur["env"]["HOOKS_NEO4J_PASSWORD"] = pw
json.dump(cur, open(settings_path, "w"), indent=2, ensure_ascii=False)
open(settings_path, "a").write("\n")
print("merged into", settings_path)
PY

echo "==> 4/4 verify shared Neo4j"
HOOKS_NEO4J_URI="$URI" HOOKS_NEO4J_USER=neo4j HOOKS_NEO4J_PASSWORD="$NEO4J_PW" \
  "$HOOKS/.venv/bin/python" "$HOOKS/hooks/query_memory_v2.py" "smoke test" --limit 1 2>/dev/null \
  && echo "OK — connected to shared memory" || echo "WARN — could not reach Neo4j (VPN? password?)"

echo "Done. Restart Claude Code to load hooks. Copy shared/.claude/{rules,agents,commands} into each code-repo as needed."
