"""
М1 — три демо-сцени заняття «Основи агентів».

    python demo.py        # всі
    python demo.py 2 3    # вибрані
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from config import USER_QUERY
from core import escalation
from modules import m01_core

TRAP_QUERY = "Яка зараз погода у Львові? І чи варто сьогодні йти на відділення?"


def show(result: dict, query: str):
    tools = [t["tool"] for t in result.get("trace", [])]
    print(f"  запит:       «{query}»")
    print(f"  інструменти: {' → '.join(tools) if tools else 'не викликались'}")
    print(f"  outcome:     {result.get('outcome')}"
          + ("  (no_tool_used!)" if result.get("no_tool_used") else ""))
    reason = escalation.decide(result, query)
    print(f"  ескалація:   {escalation.REASONS[reason] if reason else 'не потрібна'}")
    print(f"  відповідь:   {result['answer'][:300]}")
    print()


def scene_1():
    print("── Сцена 1. Чесна відмова: право лише подивитись ──────────────")
    print("   CAPABILITIES[1] = ['get_order_status'] — повернення оформити нічим.\n")
    show(m01_core.run(USER_QUERY), USER_QUERY)


def scene_2():
    print("── Сцена 2. Питання-пастка: інструмента немає ─────────────────")
    print("   Агент, що відповідає «з голови», небезпечніший за того, що мовчить.\n")
    show(m01_core.run(TRAP_QUERY), TRAP_QUERY)


def scene_3():
    print("── Сцена 3. Зрив ліміту кроків ────────────────────────────────")
    print("   MAX_TURNS=1: агент не встигає завершити → turns_exhausted → оператор.\n")
    import core.agent as agent
    saved = agent.MAX_TURNS
    agent.MAX_TURNS = 1
    try:
        show(m01_core.run(USER_QUERY), USER_QUERY)
    finally:
        agent.MAX_TURNS = saved


SCENES = {1: scene_1, 2: scene_2, 3: scene_3}

if __name__ == "__main__":
    wanted = [int(a) for a in sys.argv[1:]] or sorted(SCENES)
    for n in wanted:
        SCENES[n]()
