#!/usr/bin/env python3
"""UserPromptSubmit hook: relevance-gated memory injection.

Guaranteed to RUN on every prompt, but only INJECTS context when the memory
graph has something genuinely relevant — gated on raw cosine vector similarity
(VSCORE_THRESHOLD). Below threshold → emit nothing → no context-window cost.

This is the controlled middle ground between "never inject" (pure on-demand
subagent) and "inject on every prompt" (firehose / context rot).

Scope: current project (basename of cwd) + shared 'global' memories.

Reads HOOKS_NEO4J_* + the hook JSON payload (with `prompt`, `cwd`) from stdin.
Emits the Claude Code hook contract:
  {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                          "additionalContext": "..."}}
Always exits 0 and never raises — a memory hook must never block a prompt.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Inject a memory only if its cosine similarity clears this bar. The right value
# is MODEL-SPECIFIC — different models score on different scales — so the default
# is keyed to the active embedding model. Thresholds below were measured on the
# eval set via the LIVE DB query path (full per-query vscore distribution through
# the real Neo4j index, 2026-05-31, 22 nodes) — NOT the in-process bench_model.py,
# whose raw-cosine scale differs (Neo4j normalizes cosine to (1+cos)/2):
#   bge-m3   -> 0.76  (clean: rel_min 0.778 > irr_max 0.738, gap +0.040; perfect split)
#   e5-small -> 0.90  (best F1 0.909, precision 0.833 — overlap, could not reach fp 0)
#   e5-large -> 0.82  (bench-only, not promoted to DB)
# Override explicitly with AUTO_MEMORY_VSCORE_THRESHOLD. Re-run the eval after the
# graph grows substantially and re-tune (small 22-node eval — treat as provisional).
_MODEL_DEFAULT_THRESHOLD = {"bge-m3": 0.76, "e5-small": 0.90, "e5-large": 0.82}
_active_model = os.environ.get("AGENT_MEMORY_EMBED_MODEL", "e5-small")
VSCORE_THRESHOLD = float(os.environ.get(
    "AUTO_MEMORY_VSCORE_THRESHOLD",
    _MODEL_DEFAULT_THRESHOLD.get(_active_model, 0.90)))
MAX_INJECT = int(os.environ.get("AUTO_MEMORY_MAX_INJECT", "3"))
SNIPPET_CHARS = 500
MIN_PROMPT_CHARS = 12  # skip trivial prompts ("ok", "yes", "go")

# Path prefixes excluded from AUTO injection. `profile/*` describes the user
# broadly (high cosine to almost everything) AND is already loaded at
# SessionStart by the memory-compiler — auto-injecting it would duplicate and
# crowd out specific, query-relevant memories. The memory-query subagent can
# still reach these on demand.
EXCLUDE_PREFIXES = tuple(
    p for p in os.environ.get("AUTO_MEMORY_EXCLUDE_PREFIXES", "profile/").split(",")
    if p
)


def _emit(context: str) -> None:
    if not context.strip():
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }, ensure_ascii=False))


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return  # malformed payload: stay silent

    prompt = (data.get("prompt") or "").strip()
    if len(prompt) < MIN_PROMPT_CHARS:
        return

    cwd = data.get("cwd") or os.getcwd()
    project = os.path.basename(cwd.rstrip("/")) or None

    try:
        from query_memory_v2 import search
    except Exception:
        return  # backend import failed: stay silent

    try:
        res = search(prompt, project, MAX_INJECT)
    except Exception:
        return  # neo4j down / query error: never block the prompt

    # Relevance gate: keep only hits whose cosine vscore clears the bar.
    # fulltext-only hits (vscore is None) are NOT auto-injected — without a
    # vector score we can't trust relevance enough for unsolicited injection.
    # Also drop excluded prefixes (e.g. profile/*, already in SessionStart).
    kept = [
        r for r in res.get("results", [])
        if r.get("vscore") is not None
        and r["vscore"] >= VSCORE_THRESHOLD
        and not (r.get("path") or "").startswith(EXCLUDE_PREFIXES)
    ]
    if not kept:
        return

    lines = [
        "# Relevant project memory (auto-retrieved, relevance-gated)",
        f"_scope: {project or 'all'} + global · cosine ≥ {VSCORE_THRESHOLD}_",
        "",
    ]
    for r in kept:
        snippet = (r["content"] or "").strip().replace("\n", " ")
        if len(snippet) > SNIPPET_CHARS:
            snippet = snippet[:SNIPPET_CHARS] + "…"
        lines.append(f"- **{r['path']}** (sim={r['vscore']}, project={r['project']}): {snippet}")
    lines.append("")
    lines.append("_If relevant, use this; otherwise ignore. "
                 "For deeper recall, dispatch the `memory-query` subagent._")

    _emit("\n".join(lines))


if __name__ == "__main__":
    main()
