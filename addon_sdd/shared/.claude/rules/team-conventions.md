---
description: Team-wide conventions for all Claude Code work — language, secret hygiene, SDD/OpenSpec, versioning
paths:
  - "**/*"
---

# Team conventions (all projects)

## Language
> Adjust to your team. Example policy below — replace `<TEAM_LANGUAGE>` with the
> language your business/domain terms are written in, or drop this section if the
> whole codebase is English.

- User-facing text, business/domain terms, comments → **`<TEAM_LANGUAGE>`**.
- Code identifiers, SQL, library names, CLI output → English.

## Secret hygiene (hard rule)
- **Never** put secrets (passwords, PAT/`glpat-*`, API keys, tokens) in committed files —
  not in `.claude/settings.json`, not in `.git/config` remotes, not in code.
- Secrets live in `.env` (gitignored) or a credential helper. `.claude/settings.local.json`
  is personal and gitignored — never commit it.
- DB/host creds come from env at runtime.

## Spec-driven development (OpenSpec)
- OpenSpec is the authoritative tracker. Plan/track work in `openspec/changes/<id>/`
  (proposal.md + tasks.md + per-capability spec deltas), not in docs/ or chat.
- Any behaviour change ships with its OpenSpec change in the same MR.
- `openspec validate <id> --strict` must be green before merge.

## Shared memory (Neo4j)
- Team memory graph is project-scoped: `HOOKS_NEO4J_URI` points at the shared host.
- Use the `memory-query` subagent for on-demand recall; auto-injection is relevance-gated.
- Write durable facts as memories; don't rely on conversation history across sessions.

## Versioning over rewrite
- Prefer `_v2`/`_v3` script/file versioning over in-place rewrites when a baseline
  must stay diff-able (team review pattern).
