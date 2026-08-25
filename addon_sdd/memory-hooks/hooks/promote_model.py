#!/usr/bin/env python3
"""Promote an embedding model to production: create its dim-specific vector index
and (re)embed every :Memory node into that model's property.

Non-destructive: writes to a model-dim-specific property/index, so existing
vectors (e.g. e5-small's 384-dim) stay intact for instant rollback. Switching the
active model is just the AGENT_MEMORY_EMBED_MODEL env var.

    AGENT_MEMORY_EMBED_MODEL=bge-m3 uv run python hooks/promote_model.py
    AGENT_MEMORY_EMBED_MODEL=bge-m3 uv run python hooks/promote_model.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embed import ACTIVE, EMBED_DIM, embed_passage, vector_index, vector_property  # noqa: E402

from neo4j import GraphDatabase  # noqa: E402

NEO4J_URI = os.environ.get("HOOKS_NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("HOOKS_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("HOOKS_NEO4J_PASSWORD", "password")


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    idx, prop = vector_index(), vector_property()
    print(f"model={ACTIVE} dim={EMBED_DIM} index={idx} property={prop}")

    # confirm model loads before touching the DB
    if embed_passage("healthcheck") is None:
        print("ABORT: embeddings unavailable (model not installed).")
        sys.exit(1)

    with get_driver() as driver, driver.session() as s:
        if not args.dry_run:
            s.run(
                f"CREATE VECTOR INDEX {idx} IF NOT EXISTS "
                f"FOR (m:Memory) ON (m.{prop}) "
                "OPTIONS { indexConfig: { "
                f"`vector.dimensions`: {EMBED_DIM}, "
                "`vector.similarity_function`: 'cosine' } }"
            )
            print(f"  index {idx} ensured")

        rows = list(s.run("MATCH (m:Memory) RETURN m.path AS path, m.content AS content"))
        done = 0
        for r in rows:
            emb = embed_passage(r["content"] or "")
            if emb is None:
                continue
            if not args.dry_run:
                s.run(
                    f"MATCH (m:Memory {{path:$p}}) "
                    f"CALL db.create.setNodeVectorProperty(m, '{prop}', $e)",
                    p=r["path"], e=emb,
                )
            done += 1
        print(f"  {'would embed' if args.dry_run else 'embedded'} {done}/{len(rows)} nodes")

    if not args.dry_run:
        print(f"\nDONE. To activate, set in ~/.claude/settings.json env:")
        print(f'  "AGENT_MEMORY_EMBED_MODEL": "{ACTIVE}"')
        print(f"  and the eval-tuned AUTO_MEMORY_VSCORE_THRESHOLD for this model.")


if __name__ == "__main__":
    main()
