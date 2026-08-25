#!/usr/bin/env python3
"""On-demand hybrid memory search — vector + fulltext, project-scoped.

Retrieval backend for the `memory-query` subagent. Called JIT (when the model
actually needs memory) instead of injecting on every prompt. Returns compact
JSON the subagent distills into a summary.

Scoping: --project X returns memories where project = X OR project = 'global'.
Ranking: Reciprocal Rank Fusion (RRF) over the vector and fulltext result
lists, so it works even when embeddings are unavailable (fulltext-only).

CLI:
    uv run python hooks/query_memory_v2.py "how do we index 22M row tables" \\
        --project dwh --limit 8
    uv run python hooks/query_memory_v2.py "SIP register race" --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Optional

from neo4j import GraphDatabase

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embed import embed_query, vector_index  # noqa: E402

NEO4J_URI = os.environ.get("HOOKS_NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("HOOKS_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("HOOKS_NEO4J_PASSWORD", "password")

RRF_K = 60  # standard RRF damping constant
STOPWORDS = {
    "this", "that", "with", "from", "have", "what", "when", "where", "which",
    "would", "could", "should", "your", "their", "there", "about", "into",
    "they", "them", "then", "than", "some", "make", "like", "want", "need",
    "just", "only", "also", "still", "very", "much", "more", "most",
    "please", "thanks", "code", "file", "files",
}


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _lucene_terms(prompt: str) -> str:
    # keep Latin + Cyrillic word tokens
    words = re.findall(r"[0-9A-Za-zЀ-ӿ][\wЀ-ӿ-]+", prompt.lower())
    terms = [w for w in words if len(w) >= 3 and w not in STOPWORDS]
    return " OR ".join(terms) if terms else prompt


def _project_ok(node_project: Optional[str], project: Optional[str]) -> bool:
    if project is None:
        return True
    return node_project in (project, "global", None)


def vector_search(session, query: str, project: Optional[str], k: int) -> list:
    vec = embed_query(query)
    if vec is None:
        return []
    rows = session.run(
        f"""
        CALL db.index.vector.queryNodes('{vector_index()}', $k, $vec)
        YIELD node, score
        RETURN node.path AS path, node.content AS content,
               node.project AS project, score
        """,
        k=k * 4, vec=vec,
    )
    out = []
    for r in rows:
        if _project_ok(r["project"], project):
            out.append({"path": r["path"], "content": r["content"],
                        "project": r["project"], "vscore": r["score"]})
    return out[: k * 2]


def fulltext_search(session, query: str, project: Optional[str], k: int) -> list:
    lucene = _lucene_terms(query)
    try:
        rows = session.run(
            """
            CALL db.index.fulltext.queryNodes('memory_fulltext', $q)
            YIELD node, score
            RETURN node.path AS path, node.content AS content,
                   node.project AS project, score
            ORDER BY score DESC LIMIT $lim
            """,
            q=lucene, lim=k * 4,
        )
    except Exception:
        return []
    out = []
    for r in rows:
        if _project_ok(r["project"], project):
            out.append({"path": r["path"], "content": r["content"],
                        "project": r["project"], "fscore": r["score"]})
    return out[: k * 2]


def rrf_merge(vec_hits: list, ft_hits: list, limit: int) -> list:
    """Reciprocal Rank Fusion over two ranked lists, keyed by path."""
    scores: dict = {}
    meta: dict = {}
    for ranked in (vec_hits, ft_hits):
        for rank, hit in enumerate(ranked):
            p = hit["path"]
            scores[p] = scores.get(p, 0.0) + 1.0 / (RRF_K + rank + 1)
            meta.setdefault(p, hit)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    result = []
    for path, rrf in ordered[:limit]:
        m = meta[path]
        result.append({
            "path": path,
            "project": m.get("project"),
            "content": m["content"],
            "rrf": round(rrf, 5),
            # raw cosine vector similarity (0..1), None if fulltext-only hit.
            # Used by the auto-inject hook to threshold on real relevance.
            "vscore": round(m["vscore"], 5) if m.get("vscore") is not None else None,
        })
    return result


def search(query: str, project: Optional[str], limit: int) -> dict:
    with get_driver() as driver, driver.session() as s:
        vec = vector_search(s, query, project, limit)
        ft = fulltext_search(s, query, project, limit)
    merged = rrf_merge(vec, ft, limit)
    return {
        "query": query,
        "project": project,
        "mode": "hybrid" if vec else "fulltext-only",
        "count": len(merged),
        "results": merged,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("query")
    p.add_argument("--project", default=None,
                   help="scope to this project (+ global); omit for all")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    res = search(args.query, args.project, args.limit)

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    print(f"# memory search [{res['mode']}] project={res['project']} "
          f"({res['count']} hits)\n")
    for r in res["results"]:
        print(f"[{r['rrf']}] {r['path']}  (project={r['project']})")
        print(f"  {r['content'][:240]}")
        print()


if __name__ == "__main__":
    main()
