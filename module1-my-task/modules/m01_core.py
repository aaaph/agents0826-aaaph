"""
МОДУЛЬ 1 — Ядро агента

Додаємо: цикл «міркуй → дій → спостерігай» + один інструмент.
Агент уміє знайти прогін і подивитись метрики, але не має права нічого змінити.
"""

from config import BASE_PROMPT
from core.agent import run_agent
from domain.backend import tools_for

TITLE = "Ядро агента"
ADDS = "цикл «міркуй → дій → спостерігай» + один інструмент"
FILES = ["core/agent.py", "domain/backend.py"]


def run(query: str) -> dict:
    return run_agent(
        system=BASE_PROMPT,
        tools=tools_for(1),
        query=query,
    )
