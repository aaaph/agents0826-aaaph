"""
Той самий інтерфейс, що в knowledge.py, але пошук за змістом.

Лексика порівнює слова, ембединги — сенс. Інтерфейс (`retrieve` / `as_context`)
однаковий, тож modules/m02_rag.py про заміну не знає.

Поріг — fail-closed: нижче нього вважаємо, що не знайшли нічого. Це не
константа з підручника, а рішення, яке тюниться на своїх даних (див. scores()).
"""

import math

from domain.knowledge import KB

_MODEL = "intfloat/multilingual-e5-small"
_THRESHOLD = 0.78

_st = None
_index: list[tuple[list[float], str]] = []


def _embed(texts: list[str], kind: str) -> list[list[float]]:
    """kind: 'query' | 'passage' — обовʼязковий префікс для e5-моделей."""
    global _st
    if _st is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise SystemExit("Потрібно: uv pip install sentence-transformers") from None
        _st = SentenceTransformer(_MODEL)
    vecs = _st.encode([f"{kind}: {t}" for t in texts], normalize_embeddings=True)
    return [v.tolist() for v in vecs]


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return dot / (na * nb or 1.0)


def _ensure_index() -> None:
    global _index
    if not _index:
        texts = [text for _, text in KB]
        _index = list(zip(_embed(texts, "passage"), texts))


def scores(query: str, k: int = 5) -> list[tuple[float, str]]:
    """Схожість без відсікання — щоб було видно, де ставити поріг."""
    _ensure_index()
    q = _embed([query], "query")[0]
    ranked = sorted(((_cos(q, v), t) for v, t in _index), key=lambda x: -x[0])
    return ranked[:k]


def retrieve(query: str, k: int = 3) -> list:
    return [t for s, t in scores(query, k) if s >= _THRESHOLD]


def as_context(query: str, k: int = 3) -> str:
    hits = retrieve(query, k)
    if not hits:
        return ""
    return "\n\nВитяг з бази знань команди:\n" + "\n---\n".join(hits)
