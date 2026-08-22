"""
МОДУЛЬ 2 — Шар знань (RAG)

Додаємо: правила й тарифи з бази знань підмішуються в системний промпт.
Агент починає посилатися на реальні правила, а не вигадувати їх.
Діяти все ще не може — інструментів не побільшало.
"""

if __name__ == "__main__":            # прямий запуск: корінь модуля у sys.path
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

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


if __name__ == "__main__":
    # те саме, що `python run.py 2`, лише без підсумкових метрик і вартості
    from config import USER_QUERY

    print(f"[{TITLE}] додає: {ADDS}\n")
    _r = run(USER_QUERY)
    _tools = [t["tool"] for t in _r.get("trace", [])]
    if _tools:
        print("інструменти:", " → ".join(_tools))
    print("\n" + _r["answer"])
    print("\nПовний прогін з метриками і вартістю:  python run.py 2")
