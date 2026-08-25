# Spec-Driven Development with OpenSpec (team standard)

OpenSpec is the **authoritative tracker** for every code-repo. Plans live in specs,
not in docs/ or chat. This doc is the single source for the workflow; each code-repo
keeps its own `openspec/`.

## The loop

1. **Propose** — create a change under `openspec/changes/<change-id>/`:
   - `proposal.md` — Why / What Changes / Impact
   - `tasks.md` — atomic, ordered `[ ]` checklist (phases)
   - `specs/<capability>/spec.md` — the requirement deltas
   Use the `/openspec:proposal` slash-command (shipped in `shared/.claude/commands/`).

2. **Spec delta format** (strict):
   ```
   ## ADDED Requirements
   ### Requirement: <name>
   #### Scenario: <name>
   - WHEN <condition>
   - THEN <expected outcome>
   ```
   Also `## MODIFIED Requirements` / `## REMOVED Requirements`.

3. **Implement** — work the `tasks.md` phases in order; tick `[ ] → [x]` as you go.
   For multi-service work (e.g. cc) use the project's subagents
   (spec-explorer → service-builder → architecture-reviewer → test-writer).

4. **Validate (merge gate)** — must be green before MR merge:
   ```bash
   openspec validate <change-id> --strict
   ```

5. **Archive** — after deploy, `/openspec:archive` moves the change to the archive;
   the capability spec in `openspec/specs/` reflects the new steady state.

## "Update specs as things change"
- Any behaviour change ships **with** its OpenSpec change in the **same MR**.
- CI blocks merge if `openspec validate --strict` fails (see `.gitlab-ci.yml` template).
- No silent drift: if code changes behaviour and the spec doesn't, the MR is incomplete.

## Reference
- `cc` is the reference implementation: 20+ capability specs, 5 subagents, 8 path-scoped
  rules, architecture invariants. Mirror its structure for new code-repos.
