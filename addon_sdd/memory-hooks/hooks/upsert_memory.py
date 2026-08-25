#!/usr/bin/env python3
"""Write path for :Memory nodes — sets project tag + vector embedding.

Use this instead of raw MERGE so every memory is consistently tagged with a
`project` (for scoping) and an `embedding` (for semantic search).

Project is derived from the path unless given explicitly:
    project/<name>/...   -> <name>
    profile/* concept/* decision/* qa/* general/* -> 'global' (shared)

CLI:
    uv run python hooks/upsert_memory.py --path project/dwh/large-table-perf \\
        --content "Partial indexes per filter on 22M+ row tables" --source manual
    echo '{"path": "...", "content": "..."}' | uv run python hooks/upsert_memory.py --stdin
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from neo4j import GraphDatabase

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embed import embed_passage, vector_property  # noqa: E402

NEO4J_URI = os.environ.get("HOOKS_NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("HOOKS_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("HOOKS_NEO4J_PASSWORD", "password")

SHARED_PREFIXES = ("profile", "concept", "decision", "qa", "general", "tools")


def derive_project(path: str) -> str:
    parts = path.split("/")
    if parts and parts[0] == "project" and len(parts) >= 2:
        # project/<name>/... -> <name>; project/<name>.md -> <name>
        return parts[1].rsplit(".", 1)[0]
    if parts and parts[0] in SHARED_PREFIXES:
        return "global"
    return "global"


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def upsert(path: str, content: str, source: str = "manual",
           project: Optional[str] = None) -> dict:
    proj = project or derive_project(path)
    emb = embed_passage(content)  # None if embeddings unavailable
    now = datetime.now(timezone.utc).isoformat()
    with get_driver() as driver, driver.session() as s:
        s.run(
            """
            MERGE (m:Memory {path: $path})
            ON CREATE SET m.created_at = $now
            SET m.content = $content,
                m.source  = $source,
                m.project = $project,
                m.updated_at = $now
            """,
            path=path, content=content, source=source, project=proj, now=now,
        )
        if emb is not None:
            s.run(
                "MATCH (m:Memory {path: $path}) "
                f"CALL db.create.setNodeVectorProperty(m, '{vector_property()}', $emb)",
                path=path, emb=emb,
            )
    return {"path": path, "project": proj, "embedded": emb is not None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--path")
    p.add_argument("--content")
    p.add_argument("--source", default="manual")
    p.add_argument("--project", default=None)
    p.add_argument("--stdin", action="store_true", help="read JSON object/array from stdin")
    args = p.parse_args()

    if args.stdin:
        data = json.loads(sys.stdin.read())
        items = data if isinstance(data, list) else [data]
    else:
        if not args.path or args.content is None:
            p.error("--path and --content required (or use --stdin)")
        items = [{"path": args.path, "content": args.content,
                  "source": args.source, "project": args.project}]

    for it in items:
        res = upsert(it["path"], it["content"],
                     it.get("source", "manual"), it.get("project"))
        print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
