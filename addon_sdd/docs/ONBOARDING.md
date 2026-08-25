# Onboarding — Claude Code team setup

New seat? 5 steps to get the shared setup. Requires VPN access to `<CORP_DOMAIN>`.

## Prerequisites
- Claude Code installed (`claude --version`).
- `uv` installed (https://docs.astral.sh/uv/).
- VPN connected (the shared Neo4j is on `<NEO4J_HOST>`, intranet only).

## Steps

1. **Clone the control-repo**
   ```bash
   git clone https://<GITLAB_HOST>/<GROUP>/claude-platform.git
   cd claude-platform
   ```

2. **Run bootstrap** (creates venv, downloads e5-small ~120MB, wires hooks, sets env)
   ```bash
   python deploy/bootstrap.py        # Windows: deploy\bootstrap.cmd
   ```
   It asks for the shared Neo4j password — get it from the team lead (out-of-band, not via git/chat history).

3. **Restart Claude Code** so it loads the memory hooks.

4. **Per code repo:** copy the shared Claude config in, or symlink:
   ```bash
   cp -r <ADDON_ROOT>/shared/.claude/{rules,agents,commands} <code-repo>/.claude/
   ```
   Project-specific rules/agents already in the code-repo stay; these add the team-wide ones.

5. **Verify** you see shared memory:
   ```bash
   cd claude-platform/memory-hooks
   .venv/bin/python hooks/query_memory_v2.py "DWH" --limit 2
   ```
   `mode=hybrid` + results = working.

## Rules (non-negotiable)
- **Secrets only in `.env` / credential helper** — never in committed files, `.claude/settings.json`, or git remotes.
- `.claude/settings.local.json` is personal — it's gitignored, keep it that way.
- Spec-driven: behaviour changes ship with their OpenSpec change (see `docs/SDD.md`).

## Troubleshooting
- `WARN could not reach Neo4j` → check VPN, then password.
- Hooks not firing → restart Claude Code, or open `/hooks` once to reload.
- Embeddings slow first run → e5-small downloads once, then cached.
