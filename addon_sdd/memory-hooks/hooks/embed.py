#!/usr/bin/env python3
"""Local multilingual embeddings for agent memory (offline, no external API).

Model: intfloat/multilingual-e5-small (384 dims, cosine). Handles Ukrainian +
English content. e5 models require role prefixes: "query: " for search queries
and "passage: " for stored documents — this module applies them for you.

Degrades gracefully: if sentence-transformers / the model is unavailable,
``embed_*()`` returns ``None`` and callers fall back to fulltext-only search.

Install (one-off):
    uv sync --extra embeddings
First run downloads the model (~120 MB) into the HF cache; afterwards offline.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

# Model registry: name -> (hf_id, dim). Select via AGENT_MEMORY_EMBED_MODEL env.
# e5-small is the production default (384d, ~120MB). Larger models are challengers
# evaluated via eval_retrieval.py before being promoted.
MODELS = {
    "e5-small": ("intfloat/multilingual-e5-small", 384),
    "e5-large": ("intfloat/multilingual-e5-large", 1024),
    "bge-m3":   ("BAAI/bge-m3", 1024),
}
ACTIVE = os.environ.get("AGENT_MEMORY_EMBED_MODEL", "e5-small")
MODEL_NAME, EMBED_DIM = MODELS.get(ACTIVE, MODELS["e5-small"])


def vector_property() -> str:
    """Node property holding this model's embedding. Dim-suffixed so models of
    different dims coexist (instant rollback): 384 -> 'embedding', else 'embedding_<dim>'."""
    return "embedding" if EMBED_DIM == 384 else f"embedding_{EMBED_DIM}"


def vector_index() -> str:
    """Vector index name paired with vector_property()."""
    return "memory_embedding" if EMBED_DIM == 384 else f"memory_embedding_{EMBED_DIM}"

_models: dict = {}
_load_failed: set = set()


def _get_model():
    """Lazy-load the active model once per process. Returns None if unavailable."""
    if ACTIVE in _models:
        return _models[ACTIVE]
    if ACTIVE in _load_failed:
        return None
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        m = SentenceTransformer(MODEL_NAME)
        _models[ACTIVE] = m
        return m
    except Exception as e:  # noqa: BLE001 - never hard-fail the hook
        print(f"[embed] model {ACTIVE} unavailable, fulltext fallback: {e}", file=sys.stderr)
        _load_failed.add(ACTIVE)
        return None


def _embed(text: str, prefix: str) -> Optional[list]:
    model = _get_model()
    if model is None or not text or not text.strip():
        return None
    # e5 models REQUIRE "query:"/"passage:" prefixes; bge-m3 does NOT use them.
    payload = text if ACTIVE.startswith("bge") else f"{prefix}: {text}"
    vec = model.encode(payload, normalize_embeddings=True)
    return [float(x) for x in vec]


def embed_passage(text: str) -> Optional[list]:
    """Embed a memory body for storage."""
    return _embed(text, "passage")


def embed_query(text: str) -> Optional[list]:
    """Embed a search query."""
    return _embed(text, "query")


# Backwards-friendly default alias
embed = embed_passage


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "тестовий запит про DWH таблиці"
    v = embed_query(q)
    if v is None:
        print("EMBEDDINGS UNAVAILABLE (fulltext fallback active)")
    else:
        print(f"dim={len(v)} first5={v[:5]}")
