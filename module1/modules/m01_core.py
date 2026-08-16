"""
МОДУЛЬ 1 — Ядро агента

Додаємо: цикл «міркуй → дій → спостерігай» + один інструмент.
Агент уміє подивитись статус, але не має права нічого зробити.
"""

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
