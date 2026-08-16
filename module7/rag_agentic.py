"""
М2 — Agentic RAG: retrieval стає інструментом.

Static RAG (m02): правила підмішуються в промпт завжди, знайшлось чи ні.
Agentic RAG: агент сам вирішує, КОЛИ і ЩО шукати, і може зробити
кілька різних пошуків за один діалог.

    python rag_agentic.py                 # обидва варіанти поруч
    python rag_agentic.py --agentic-only
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from config import BASE_PROMPT, USER_QUERY
from core.agent import run_agent
from domain import backend
from domain.knowledge import retrieve


def _search_kb(query: str) -> dict:
    hits = retrieve(query, k=3)
    return {"rules": hits} if hits else {"rules": [], "note": "нічого не знайдено"}


SEARCH_KB_SCHEMA = {
    "name": "search_kb",
    "description": "Шукає правила й тарифи в базі знань поштового оператора. "
                   "Викликай перед будь-яким твердженням про правила чи суми.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string",
                                 "description": "Пошуковий запит, напр. «строк повернення доставки»"}},
        "required": ["query"],
    },
}


def run_agentic(query: str) -> dict:
    # реєструємо інструмент у тому ж диспетчері, що й решта бекенду
    backend.IMPL["search_kb"] = _search_kb
    tools = backend.tools_for(2) + [SEARCH_KB_SCHEMA]
    result = run_agent(
        system=BASE_PROMPT + " Правила бери ТІЛЬКИ з search_kb — не вигадуй.",
        tools=tools,
        query=query,
    )
    result["kb_searches"] = [t["input"].get("query") for t in result["trace"]
                             if t["tool"] == "search_kb"]
    return result


if __name__ == "__main__":
    from modules import m02_rag

    if "--agentic-only" not in sys.argv:
        print("── Static RAG (m02): правила підмішані в промпт ────────────")
        r = m02_rag.run(USER_QUERY)
        print(f"  retrieved: {r['retrieved']} правил (завжди, потрібні чи ні)")
        print(f"  → {r['answer'][:250]}\n")

    print("── Agentic RAG: retrieval як інструмент ────────────────────")
    r = run_agentic(USER_QUERY)
    print(f"  пошуки агента: {r['kb_searches']}")
    print(f"  → {r['answer'][:250]}")
