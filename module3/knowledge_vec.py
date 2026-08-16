"""
М2 — де ламається лексичний retriever і як його лагодить векторний.

Частина 1 (офлайн, без ключів): три запити-синоніми, на яких лексичний
скоринг з domain/knowledge.py реально промахується — «загубили» не
матчиться з «втрачено», «відшкодування» тягне не туди.

Частина 2: ті самі запити через справжні ембединги. Бекенд обирається сам:
  OPENAI_API_KEY є     → text-embedding-3-small (API)
  інакше               → sentence-transformers intfloat/multilingual-e5-small
                         (локально, без мережі після першого завантаження)

Інтерфейс (retrieve / as_context) той самий — агент про заміну не дізнається.
Наступний крок лаби — покласти ці ж вектори в Qdrant/Chroma.

    python knowledge_vec.py
"""

import math
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from domain.knowledge import KB
from domain import knowledge as lex

# Запити, на яких лексика промахується (перевірено на поточній KB):
#   «загубив/загубили» ≠ «втрата/втрачено» → тягне 4.5 чи 7.8 замість 7.3/6.1
DEMO_QUERIES = [
    "Кур'єр загубив мій пакунок, що мені виплатять?",
    "Мою бандероль загубили, хочу відшкодування вартості товару.",
    "Чи можу я отримати відшкодування за запізнілу доставку?",
]

_USE_OPENAI = bool(os.getenv("OPENAI_API_KEY"))
_LOCAL_MODEL = "intfloat/multilingual-e5-small"
# нижче порога вважаємо, що не знайшли нічого (fail-closed);
# у e5 косинуси зсунуті вгору, тому поріг вищий за openai
_THRESHOLD = 0.25 if _USE_OPENAI else 0.78

_st_model = None


def _embed(texts: list[str], kind: str) -> list[list[float]]:
    """kind: 'query' | 'passage' — потрібно для e5-моделей."""
    if _USE_OPENAI:
        from openai import OpenAI
        resp = OpenAI().embeddings.create(model="text-embedding-3-small", input=texts)
        return [d.embedding for d in resp.data]

    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise SystemExit("Потрібно:  pip install sentence-transformers "
                             "(або задайте OPENAI_API_KEY)")
        _st_model = SentenceTransformer(_LOCAL_MODEL)
    vecs = _st_model.encode([f"{kind}: {t}" for t in texts], normalize_embeddings=True)
    return [v.tolist() for v in vecs]


def _cos(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb or 1.0)


_index: list[tuple[list[float], str]] | None = None


def _ensure_index():
    global _index
    if _index is None:
        vecs = _embed([f"{keys}. {text}" for keys, text in KB], kind="passage")
        _index = list(zip(vecs, [text for _, text in KB]))


def retrieve(query: str, k: int = 3) -> list:
    _ensure_index()
    q = _embed([query], kind="query")[0]
    scored = sorted(((_cos(q, v), t) for v, t in _index), key=lambda x: -x[0])
    return [t for s, t in scored[:k] if s >= _THRESHOLD]


def scores(query: str, k: int = 3) -> list[tuple[float, str]]:
    """Для дебагу порога на занятті."""
    _ensure_index()
    q = _embed([query], kind="query")[0]
    return sorted(((_cos(q, v), t) for v, t in _index), key=lambda x: -x[0])[:k]


def as_context(query: str, k: int = 3) -> str:
    hits = retrieve(query, k)
    if not hits:
        return ""      # fail-closed: краще порожньо, ніж хибне правило
    return "\n\nВитяг з бази знань:\n" + "\n---\n".join(hits)


if __name__ == "__main__":
    print("── Частина 1. Промахи лексичного скорингу (офлайн) ─────────")
    for q in DEMO_QUERIES:
        print(f"\nЗапит: «{q}»")
        print("  лексичний:", lex.retrieve(q, 1)[0][:75])
    print("\n  «загубили» ≠ «втрачено» — префіксне порівняння тут безсиле.")

    backend = "text-embedding-3-small (OpenAI)" if _USE_OPENAI else f"{_LOCAL_MODEL} (локально)"
    print(f"\n── Частина 2. Ті самі запити через ембединги: {backend} ──")
    for q in DEMO_QUERIES:
        top = scores(q, 1)
        print(f"\nЗапит: «{q}»")
        if top and top[0][0] >= _THRESHOLD:
            print(f"  векторний ({top[0][0]:.2f}):", top[0][1][:75])
        else:
            got = f" (топ {top[0][0]:.2f} < поріг {_THRESHOLD})" if top else ""
            print(f"  векторний: — нічого, fail-closed{got}")
