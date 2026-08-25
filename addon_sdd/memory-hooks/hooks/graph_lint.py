#!/usr/bin/env python3
"""Health checks for the agent-memory graph (2.6 graph hygiene).

The markdown memory-compiler has lint.py for files; this is its graph equivalent.
Read-only by default — reports issues so they can be fixed deliberately. Use
--fix-projects to backfill obviously-missing project tags (the one safe auto-fix).

Checks:
  1. missing-project    — :Memory with no project tag (should be 0 post-migration)
  2. missing-embedding  — :Memory with no embedding vector (degrades to fulltext)
  3. empty-content      — :Memory with blank/near-empty content
  4. duplicates         — node pairs with cosine >= DUP_THRESHOLD (merge candidates)
  5. contradictions     — high-similarity pairs in DIFFERENT projects (possible conflict)
  6. broken-links       — [[wikilinks]] in content pointing to a non-existent path
  7. stale              — not updated in > STALE_DAYS (informational; needs updated_at)

    uv run python hooks/graph_lint.py
    uv run python hooks/graph_lint.py --json
    uv run python hooks/graph_lint.py --fix-projects
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from neo4j import GraphDatabase  # noqa: E402

NEO4J_URI = os.environ.get("HOOKS_NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("HOOKS_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("HOOKS_NEO4J_PASSWORD", "password")

DUP_THRESHOLD = float(os.environ.get("LINT_DUP_THRESHOLD", "0.95"))
CONTRA_THRESHOLD = float(os.environ.get("LINT_CONTRA_THRESHOLD", "0.93"))
STALE_DAYS = int(os.environ.get("LINT_STALE_DAYS", "120"))
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def fetch_nodes(s):
    return list(s.run(
        "MATCH (m:Memory) RETURN m.path AS path, m.project AS project, "
        "m.content AS content, m.embedding AS embedding, m.updated_at AS updated_at"
    ))


def cosine(a, b):
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b))  # vectors are normalized


def lint(fix_projects: bool) -> dict:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    issues = {k: [] for k in (
        "missing-project", "missing-embedding", "empty-content",
        "duplicates", "contradictions", "broken-links", "stale")}

    with get_driver() as driver, driver.session() as s:
        nodes = fetch_nodes(s)
        paths = {n["path"] for n in nodes}

        for n in nodes:
            p = n["path"]
            if not n["project"]:
                issues["missing-project"].append(p)
            if n["embedding"] is None:
                issues["missing-embedding"].append(p)
            if not (n["content"] or "").strip() or len((n["content"] or "").strip()) < 30:
                issues["empty-content"].append(p)
            for tgt in WIKILINK_RE.findall(n["content"] or ""):
                tgt = tgt.strip()
                # tolerate name vs path: match by suffix
                if tgt not in paths and not any(pp.endswith(tgt) or pp.endswith(tgt + ".md") for pp in paths):
                    issues["broken-links"].append({"in": p, "link": tgt})

        # pairwise similarity (only nodes that have embeddings)
        emb = [(n["path"], n["project"], n["embedding"]) for n in nodes if n["embedding"]]
        for i in range(len(emb)):
            for j in range(i + 1, len(emb)):
                sim = cosine(emb[i][2], emb[j][2])
                if sim >= DUP_THRESHOLD:
                    issues["duplicates"].append({"a": emb[i][0], "b": emb[j][0], "cos": round(sim, 4)})
                elif sim >= CONTRA_THRESHOLD and emb[i][1] != emb[j][1]:
                    issues["contradictions"].append(
                        {"a": emb[i][0], "b": emb[j][0], "cos": round(sim, 4),
                         "projects": [emb[i][1], emb[j][1]]})

        # stale (best-effort; needs updated_at)
        # leave as informational count via cypher
        stale = list(s.run(
            "MATCH (m:Memory) WHERE m.updated_at IS NOT NULL "
            "AND m.updated_at < datetime() - duration({days: $d}) "
            "RETURN m.path AS path ORDER BY m.updated_at", d=STALE_DAYS))
        issues["stale"] = [r["path"] for r in stale]

        fixed = []
        if fix_projects and issues["missing-project"]:
            from upsert_memory import derive_project
            for p in issues["missing-project"]:
                proj = derive_project(p)
                s.run("MATCH (m:Memory {path:$p}) SET m.project=$proj", p=p, proj=proj)
                fixed.append({"path": p, "project": proj})

    return {"total_nodes": len(nodes), "issues": issues,
            "fixed_projects": fixed if fix_projects else []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix-projects", action="store_true",
                    help="backfill missing project tags from path (safe auto-fix)")
    args = ap.parse_args()

    rep = lint(args.fix_projects)

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return

    print(f"# Graph health — {rep['total_nodes']} :Memory nodes\n")
    order = ["missing-project", "missing-embedding", "empty-content",
             "duplicates", "contradictions", "broken-links", "stale"]
    total = 0
    for k in order:
        items = rep["issues"][k]
        total += len(items)
        flag = "OK " if not items else "!! "
        print(f"{flag}{k}: {len(items)}")
        for it in items[:8]:
            print(f"      {it}")
        if len(items) > 8:
            print(f"      … +{len(items) - 8} more")
    if rep["fixed_projects"]:
        print(f"\nFIXED {len(rep['fixed_projects'])} project tags:")
        for f in rep["fixed_projects"]:
            print(f"      {f['path']} -> {f['project']}")
    print(f"\nTOTAL issues: {total}")


if __name__ == "__main__":
    main()
