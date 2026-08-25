#!/usr/bin/env python3
"""Retrieval eval harness for the agent-memory graph.

Measures retrieval quality against eval_dataset.json so the auto-inject threshold
and embedding model are tuned on DATA, not by guessing.

Two things it reports:
1. RANKING (threshold-independent): for each 'relevant' query, is an expected
   memory in the top-K hybrid results? → Recall@1, Recall@3, MRR.
2. THRESHOLD GATE (auto-inject behaviour): sweep cosine vscore thresholds and, at
   each, compute precision/recall over relevant-vs-irrelevant queries — i.e. does
   the gate fire on relevant prompts and stay silent on off-topic ones. Prints the
   best-F1 threshold so you can set AUTO_MEMORY_VSCORE_THRESHOLD from evidence.

Usage:
    uv run python hooks/eval_retrieval.py                 # full report
    uv run python hooks/eval_retrieval.py --thresholds 0.85 0.88 0.90 0.92
    uv run python hooks/eval_retrieval.py --json          # machine-readable
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from query_memory_v2 import search  # noqa: E402

DATASET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_dataset.json")
DEFAULT_THRESHOLDS = [0.84, 0.86, 0.88, 0.90, 0.92, 0.94]
TOPK = 5


def load_dataset() -> dict:
    with open(DATASET) as fh:
        return json.load(fh)


def _top_vscore(results: list) -> float:
    """Highest cosine vscore among results (0.0 if none / fulltext-only)."""
    vs = [r["vscore"] for r in results if r.get("vscore") is not None]
    return max(vs) if vs else 0.0


def eval_ranking(relevant: list) -> dict:
    """Threshold-independent: is an expected path in top-K?"""
    r1 = r3 = 0
    mrr = 0.0
    misses = []
    for case in relevant:
        res = search(case["query"], case.get("project"), TOPK)["results"]
        paths = [r["path"] for r in res]
        expect = set(case["expect"])
        rank = next((i for i, p in enumerate(paths) if p in expect), None)
        if rank is not None:
            if rank == 0:
                r1 += 1
            if rank < 3:
                r3 += 1
            mrr += 1.0 / (rank + 1)
        else:
            misses.append({"query": case["query"], "expected": case["expect"], "got": paths[:3]})
    n = len(relevant)
    return {
        "n": n,
        "recall@1": round(r1 / n, 3),
        "recall@3": round(r3 / n, 3),
        "mrr": round(mrr / n, 3),
        "misses": misses,
    }


def eval_thresholds(relevant: list, irrelevant: list, thresholds: list) -> list:
    """For each threshold: would the gate fire correctly?

    A relevant query is a true-positive if top vscore >= threshold (gate fires).
    An irrelevant query is a false-positive if top vscore >= threshold (gate fires
    when it shouldn't).
    """
    # cache top vscore per query once
    rel_scores = [_top_vscore(search(c["query"], c.get("project"), TOPK)["results"]) for c in relevant]
    irr_scores = [_top_vscore(search(c["query"], c.get("project"), TOPK)["results"]) for c in irrelevant]

    out = []
    for t in thresholds:
        tp = sum(1 for s in rel_scores if s >= t)       # fired on relevant ✓
        fn = sum(1 for s in rel_scores if s < t)        # missed relevant ✗
        fp = sum(1 for s in irr_scores if s >= t)       # fired on irrelevant ✗
        tn = sum(1 for s in irr_scores if s < t)        # silent on irrelevant ✓
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        out.append({"threshold": t, "precision": round(prec, 3), "recall": round(rec, 3),
                    "f1": round(f1, 3), "tp": tp, "fp": fp, "fn": fn, "tn": tn})
    return out, rel_scores, irr_scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thresholds", type=float, nargs="+", default=DEFAULT_THRESHOLDS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ds = load_dataset()
    rel, irr = ds["relevant"], ds["irrelevant"]

    ranking = eval_ranking(rel)
    gate, rel_scores, irr_scores = eval_thresholds(rel, irr, args.thresholds)
    best = max(gate, key=lambda g: (g["f1"], g["threshold"]))

    if args.json:
        print(json.dumps({"ranking": ranking, "gate": gate, "best_threshold": best},
                         ensure_ascii=False, indent=2))
        return

    print("=== RANKING (threshold-independent hybrid search quality) ===")
    print(f"  n={ranking['n']}  Recall@1={ranking['recall@1']}  "
          f"Recall@3={ranking['recall@3']}  MRR={ranking['mrr']}")
    if ranking["misses"]:
        print("  MISSES (expected not in top-5):")
        for m in ranking["misses"]:
            print(f"    q={m['query'][:60]!r}\n      expected {m['expected']}  got {m['got']}")

    print("\n=== THRESHOLD GATE (auto-inject precision/recall) ===")
    print(f"  {'thresh':>7} {'prec':>6} {'recall':>7} {'f1':>6}  (tp/fp/fn/tn)")
    for g in gate:
        mark = "  <- best F1" if g is best else ""
        print(f"  {g['threshold']:>7.2f} {g['precision']:>6.3f} {g['recall']:>7.3f} "
              f"{g['f1']:>6.3f}  ({g['tp']}/{g['fp']}/{g['fn']}/{g['tn']}){mark}")

    print(f"\n  score spread:")
    print(f"    relevant   top-vscores: min={min(rel_scores):.3f} max={max(rel_scores):.3f}")
    print(f"    irrelevant top-vscores: min={min(irr_scores):.3f} max={max(irr_scores):.3f}")
    sep = min(rel_scores) - max(irr_scores)
    print(f"    separation (min_rel - max_irr) = {sep:+.3f}  "
          f"({'CLEAN' if sep > 0 else 'OVERLAP — no perfect threshold'})")
    print(f"\n  RECOMMENDED AUTO_MEMORY_VSCORE_THRESHOLD = {best['threshold']:.2f} "
          f"(F1={best['f1']}, precision={best['precision']}, recall={best['recall']})")


if __name__ == "__main__":
    main()
