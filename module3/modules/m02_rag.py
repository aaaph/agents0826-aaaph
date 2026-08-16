"""
МОДУЛЬ 2 — Шар знань (RAG)

Додаємо: правила й тарифи з бази знань підмішуються в системний промпт.
Агент починає посилатися на реальні правила, а не вигадувати їх.
Діяти все ще не може — інструментів не побільшало.
"""

from core.agent import run_agent
from domain.backend import tools_for
from domain.knowledge import as_context, retrieve
from config import BASE_PROMPT

TITLE = "Шар знань (RAG)"
ADDS  = "база правил і тарифів у контексті"
FILES = ["domain/knowledge.py"]


def run(query: str) -> dict:
    result = run_agent(
        system=BASE_PROMPT + as_context(query),
        tools=tools_for(2),
        query=query,
    )
    result["retrieved"] = len(retrieve(query))
    return result
