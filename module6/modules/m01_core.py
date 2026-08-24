"""
МОДУЛЬ 1 — Ядро агента

Додаємо: цикл «міркуй → дій → спостерігай» + один інструмент.
Агент уміє подивитись статус, але не має права нічого зробити.
"""

if __name__ == "__main__":            # прямий запуск: корінь модуля у sys.path
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.agent import run_agent
from domain.backend import tools_for
from config import BASE_PROMPT

TITLE = "Ядро агента"
ADDS  = "цикл «міркуй → дій → спостерігай» + один інструмент"
FILES = ["core/agent.py", "domain/backend.py"]


def run(query: str) -> dict:
    return run_agent(
        system=BASE_PROMPT,
        tools=tools_for(1),
        query=query,
    )


if __name__ == "__main__":
    # те саме, що `python run.py 1`, лише без підсумкових метрик і вартості
    from config import USER_QUERY

    print(f"[{TITLE}] додає: {ADDS}\n")
    _r = run(USER_QUERY)
    _tools = [t["tool"] for t in _r.get("trace", [])]
    if _tools:
        print("інструменти:", " → ".join(_tools))
    print("\n" + _r["answer"])
    print("\nПовний прогін з метриками і вартістю:  python run.py 1")
