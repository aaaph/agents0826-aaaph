"""
МОДУЛЬ 2 — Шар знань (RAG)

Додаємо: правила команди підмішуються в системний промпт. Агент починає
посилатися на «Правило 1.2» замість вигадувати поріг прийняття.
Інструментів не побільшало — діяти він так само не може.

Уся різниця з модулем 1 — один доданок у system:

    BASE_PROMPT + as_context(query)

Ретрив лексичний і **fail-closed**: якщо нічого не знайшлось, у промпт
не йде нічого. Курсовий knowledge.py у такому разі віддає найменш
нерелевантне правило — ми обрали інакше: хибне правило про поріг
заблокує коректний мердж, а порожній контекст лише зробить відповідь
загальною.
"""

from config import BASE_PROMPT
from core.agent import run_agent
from domain.backend import tools_for
from domain.knowledge_vec import as_context, retrieve
from modules.m01_core import finish

TITLE = "Шар знань (RAG)"
ADDS = "база правил команди в контексті"
FILES = ["domain/knowledge.py", "modules/m02_rag.py"]


def run(query: str) -> dict:
    result = run_agent(
        system=BASE_PROMPT + as_context(query),
        tools=tools_for(2),
        query=query,
    )
    result["retrieved"] = len(retrieve(query))
    return finish(result, query)
