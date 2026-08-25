#!/usr/bin/env python3
"""One-off migration to memory schema v2: project tags + vector embeddings.

Steps:
  1. Apply schema_v2.cypher (project index + vector index; idempotent).
  2. Backfill `project` on every :Memory lacking it (derived from path).
  3. Backfill `embedding` on every :Memory lacking one (if embeddings available).

Safe to re-run: only touches nodes missing the relevant property.

    uv run python hooks/migrate_v2.py            # full migration
    uv run python hooks/migrate_v2.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
import os
import sys

from neo4j import GraphDatabase

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embed import embed_passage  # noqa: E402
from upsert_memory import derive_project  # noqa: E402

NEO4J_URI = os.environ.get("HOOKS_NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("HOOKS_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("HOOKS_NEO4J_PASSWORD", "password")

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema_v2.cypher")


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def apply_schema(session):
    with open(SCHEMA_FILE) as fh:
        raw = fh.read()
    stmts = []
    for chunk in raw.split(";"):
        lines = [ln for ln in chunk.splitlines() if not ln.strip().startswith("//")]
        stmt = "\n".join(lines).strip()
        if stmt:
            stmts.append(stmt)
    for stmt in stmts:
        session.run(stmt)
    print(f"  schema: applied {len(stmts)} statements")


def backfill_projects(session, dry: bool) -> int:
    rows = list(session.run(
        "MATCH (m:Memory) WHERE m.project IS NULL RETURN m.path AS path"
    ))
    for r in rows:
        proj = derive_project(r["path"])
        if not dry:
            session.run("MATCH (m:Memory {path:$p}) SET m.project=$proj",
                        p=r["path"], proj=proj)
        print(f"  project: {r['path']} -> {proj}{' (dry)' if dry else ''}")
    return len(rows)


def backfill_embeddings(session, dry: bool):
    rows = list(session.run(
        "MATCH (m:Memory) WHERE m.embedding IS NULL "
        "RETURN m.path AS path, m.content AS content"
    ))
    done = 0
    for r in rows:
        emb = embed_passage(r["content"] or "")
        if emb is None:
            continue  # embeddings unavailable; leave for later re-run
        if not dry:
            session.run(
                "MATCH (m:Memory {path:$p}) "
                "CALL db.create.setNodeVectorProperty(m, 'embedding', $e)",
                p=r["path"], e=emb,
            )
        done += 1
        print(f"  embed: {r['path']} ({len(emb)}d){' (dry)' if dry else ''}")
    return len(rows), done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run

    with get_driver() as driver, driver.session() as s:
        print("== schema ==")
        if not dry:
            apply_schema(s)
        else:
            print("  (dry-run: schema not applied)")

        print("== backfill project ==")
        n_proj = backfill_projects(s, dry)

        print("== backfill embeddings ==")
        n_missing, n_done = backfill_embeddings(s, dry)

    print("\n== summary ==")
    print(f"  projects tagged:    {n_proj}")
    print(f"  embeddings missing: {n_missing}")
    print(f"  embeddings written: {n_done}")
    if n_missing and n_done == 0:
        print("  NOTE: embeddings unavailable — run `uv sync --extra embeddings`, "
              "then re-run this migration to backfill vectors.")


if __name__ == "__main__":
    main()
