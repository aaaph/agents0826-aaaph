#!/usr/bin/env python3
"""A/B benchmark an embedding model against the eval dataset — IN-PROCESS, no DB writes.

Pulls the real :Memory node contents from Neo4j once, embeds them + the eval
queries with the chosen model, ranks by cosine in numpy, and reports the same
metrics as eval_retrieval.py (Recall@K, MRR, relevant/irrelevant score separation,
best threshold). This lets us decide whether a bigger model is worth a production
re-embed BEFORE touching the live index.

    AGENT_MEMORY_EMBED_MODEL=e5-small uv run python hooks/bench_model.py
    AGENT_MEMORY_EMBED_MODEL=e5-large uv run python hooks/bench_model.py
    AGENT_MEMORY_EMBED_MODEL=bge-m3   uv run python hooks/bench_model.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embed import ACTIVE, EMBED_DIM, embed_passage, embed_query  # noqa: E402

from neo4j import GraphDatabase  # noqa: E402

NEO4J_URI = os.environ.get("HOOKS_NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("HOOKS_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("HOOKS_NEO4J_PASSWORD", "password")
DATASET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_dataset.json")
TOPK = 5
THRESHOLDS = [0.80, 0.82, 0.84, 0.86, 0.88, 0.90, 0.92, 0.94]


def load_nodes() -> list:
    d = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with d.session() as s:
        rows = list(s.run("MATCH (m:Memory) RETURN m.path AS path, "
                          "m.project AS project, m.content AS content"))
    d.close()
    return [{"path": r["path"], "project": r["project"], "content": r["content"]} for r in rows]


def cosine(a, b):
    # vectors are already L2-normalized by sentence-transformers
    return sum(x * y for x, y in zip(a, b))


def project_ok(node_project, q_project):
    if q_project is None:
        return True
    return node_project in (q_project, "global", None)


def rank(query, q_project, node_embs, nodes):
    qv = embed_query(query)
    scored = []
    for n, ev in zip(nodes, node_embs):
        if ev is None or not project_ok(n["project"], q_project):
            continue
        scored.append((cosine(qv, ev), n["path"]))
    scored.sort(reverse=True)
    return scored[:TOPK]


def main():
    nodes = load_nodes()
    node_embs = [embed_passage(n["content"]) for n in nodes]
    if all(e is None for e in node_embs):
        print(f"MODEL {ACTIVE}: embeddings unavailable (sentence-transformers/model missing)")
        return

    ds = json.load(open(DATASET))
    rel, irr = ds["relevant"], ds["irrelevant"]

    # ranking
    r1 = r3 = 0
    mrr = 0.0
    misses = []
    rel_top = []
    for c in rel:
        hits = rank(c["query"], c.get("project"), node_embs, nodes)
        paths = [p for _, p in hits]
        rel_top.append(hits[0][0] if hits else 0.0)
        expect = set(c["expect"])
        ix = next((i for i, p in enumerate(paths) if p in expect), None)
        if ix is not None:
            if ix == 0:
                r1 += 1
            if ix < 3:
                r3 += 1
            mrr += 1.0 / (ix + 1)
        else:
            misses.append((c["query"], c["expect"], paths[:3]))

    irr_top = []
    for c in irr:
        hits = rank(c["query"], c.get("project"), node_embs, nodes)
        irr_top.append(hits[0][0] if hits else 0.0)

    n = len(rel)
    # threshold sweep
    best = None
    sweep = []
    for t in THRESHOLDS:
        tp = sum(1 for s in rel_top if s >= t)
        fn = sum(1 for s in rel_top if s < t)
        fp = sum(1 for s in irr_top if s >= t)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        row = {"t": t, "P": round(prec, 3), "R": round(rec, 3), "f1": round(f1, 3)}
        sweep.append(row)
        if best is None or (f1, t) > (best["f1"], best["t"]):
            best = row

    sep = min(rel_top) - max(irr_top)
    result = {
        "model": ACTIVE, "dim": EMBED_DIM,
        "recall@1": round(r1 / n, 3), "recall@3": round(r3 / n, 3), "mrr": round(mrr / n, 3),
        "rel_min": round(min(rel_top), 3), "irr_max": round(max(irr_top), 3),
        "separation": round(sep, 3), "best_threshold": best["t"], "best_f1": best["f1"],
        "misses": [{"q": q[:50], "got": [p.split("/")[-1] for p in g]} for q, _, g in misses],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
