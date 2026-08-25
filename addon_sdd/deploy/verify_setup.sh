#!/usr/bin/env bash
# verify_setup.sh — check the team Claude Code setup.
# Run manually (./deploy/verify_setup.sh), via /verify-setup, or on SessionStart.
# Output: compact status. Always exits 0 (never blocks a session).
# --quiet = print nothing when everything is OK (used by the SessionStart hook).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS="$ROOT/memory-hooks"
QUIET="${1:-}"
ok=(); warn=(); fail=()

# pick the venv python per-platform, fall back to system python
if   [ -x "$HOOKS/.venv/bin/python" ];        then PYS="$HOOKS/.venv/bin/python"
elif [ -x "$HOOKS/.venv/Scripts/python.exe" ]; then PYS="$HOOKS/.venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1;      then PYS="python3"
else PYS="python"; fi

# 1) Neo4j env present? (env wins, else read from ~/.claude/settings.json)
URI="${HOOKS_NEO4J_URI:-}"; USR="${HOOKS_NEO4J_USER:-neo4j}"; PW="${HOOKS_NEO4J_PASSWORD:-}"
if [ -z "$URI" ] || [ -z "$PW" ]; then
  read -r URI USR PW < <("$PYS" - <<'PY' 2>/dev/null
import json, os
try:
    e = json.load(open(os.path.expanduser("~/.claude/settings.json"))).get("env", {})
    print(e.get("HOOKS_NEO4J_URI",""), e.get("HOOKS_NEO4J_USER","neo4j"), e.get("HOOKS_NEO4J_PASSWORD",""))
except Exception:
    print("", "", "")
PY
)
fi
[ -n "$URI" ] && ok+=("Neo4j configured ($URI)") \
              || fail+=("HOOKS_NEO4J_* not found — run deploy/bootstrap.py")

# 2) Bolt reachable + indexes ONLINE
if [ -n "$URI" ] && [ -n "$PW" ]; then
  RES=$(HOOKS_NEO4J_URI="$URI" HOOKS_NEO4J_USER="$USR" HOOKS_NEO4J_PASSWORD="$PW" "$PYS" - <<'PY' 2>/dev/null
import os
try:
    from neo4j import GraphDatabase
    d = GraphDatabase.driver(os.environ["HOOKS_NEO4J_URI"],
                             auth=(os.environ["HOOKS_NEO4J_USER"], os.environ["HOOKS_NEO4J_PASSWORD"]))
    d.verify_connectivity()
    with d.session() as s:
        idx = [r["state"] for r in s.run(
            "SHOW INDEXES YIELD name,state WHERE name STARTS WITH 'memory' RETURN state")]
    d.close()
    print(f"OK {sum(1 for x in idx if x=='ONLINE')} {len(idx)}")
except Exception as e:
    print("ERR " + type(e).__name__)
PY
)
  case "$RES" in
    OK*) read -r _ on tot <<<"$RES"; ok+=("Vector DB reachable — $on/$tot indexes ONLINE") ;;
    *)   fail+=("Vector DB unreachable (${RES#ERR }) — check VPN and password") ;;
  esac
fi

# 3) embedding model available? (hybrid vs fulltext-only)
EMB=$("$PYS" - <<'PY' 2>/dev/null
try:
    import sentence_transformers; print("yes")
except Exception:
    print("no")
PY
)
[ "$EMB" = yes ] && ok+=("Embedding model installed (hybrid search)") \
                 || warn+=("Embedding model missing — fulltext only. Run: uv pip install -e '.[embeddings]' in memory-hooks/")

# 4) project skills present in the current working directory
SKILLS_DIR="$(pwd)/.claude/skills"
if [ -d "$SKILLS_DIR" ]; then
  n=$(find "$SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
  names=$(find "$SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d -exec basename {} \; 2>/dev/null | paste -sd, -)
  ok+=("Project skills: $n ($names)")
else
  warn+=("No skills found in $(pwd)/.claude/skills — are you inside a project repo?")
fi

# --- output ---
if [ ${#fail[@]} -eq 0 ] && [ "$QUIET" = "--quiet" ]; then exit 0; fi
echo "── Claude Code setup ──"
for x in ${ok[@]+"${ok[@]}"};     do echo "  OK   $x"; done
for x in ${warn[@]+"${warn[@]}"}; do echo "  WARN $x"; done
for x in ${fail[@]+"${fail[@]}"}; do echo "  FAIL $x"; done
[ ${#fail[@]} -gt 0 ] && echo "  → see README.md / docs/ONBOARDING.md"
exit 0
