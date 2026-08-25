"""
Один агент проти маршрутизатора зі спеціалістами — на тих самих пʼяти запитах.

Базова лінія чесна: один агент отримує ПОВНИЙ набір інструментів (усе, що
разом мають спеціалісти) і ту саму базу знань. Різниця лише в архітектурі.

    uv run compare_mas.py
"""

import time

from config import BASE_PROMPT
from core import cost
from core.agent import USAGE, reset_usage, run_agent
from domain.backend import FULL, TOOL_SCHEMAS
from domain.knowledge_vec import as_context
from modules import m04_orchestration as mas

QUERIES = [
    "Де в нас зривався трекінг і що це був за прогін?",
    "Яка ATE у run-0141?",
    "Який поріг прийняття для difficult сиквенсів?",
    "Постав run-0209 на переобрахунок, там зірвався трекінг на 47 секунді",
    "Хто у вас відповідає за калібрування?",
]


def run_single(query: str) -> dict:
    """Один агент: усі інструменти, вся база знань, жодної маршрутизації."""
    return run_agent(
        system=BASE_PROMPT + as_context(query),
        tools=[TOOL_SCHEMAS[n] for n in FULL],
        query=query,
    )


def measure(fn, query: str) -> dict:
    reset_usage()
    t0 = time.time()
    result = fn(query)
    return {
        "sec": round(time.time() - t0, 1),
        "usd": cost.usd(USAGE["by_model"]),
        "calls": USAGE["calls"],
        "route": result.get("route", "—"),
        "escalated": bool(result.get("escalated")),
        "answer": result.get("answer", ""),
    }


def shippable(r: dict) -> bool:
    """Чи показали б цю відповідь клієнту: не збій і не порожньо."""
    return bool(r["answer"]) and "Сервіс тимчасово недоступний" not in r["answer"]


if __name__ == "__main__":
    rows = []
    for q in QUERIES:
        print(f"\n· {q}")
        one = measure(run_single, q)
        team = measure(mas.run, q)
        print(f"    один агент : {one['sec']:>5.1f} с  ${one['usd']:.5f}  "
              f"{one['calls']} викл.")
        print(f"    команда    : {team['sec']:>5.1f} с  ${team['usd']:.5f}  "
              f"{team['calls']} викл.  маршрут {team['route']}")
        rows.append((one, team))

    def total(i: int, key: str):
        return sum(r[i][key] for r in rows)

    print("\n" + "═" * 66)
    print(f"{'':12} {'час, с':>8} {'вартість':>11} {'викликів':>10} {'до клієнта':>12}")
    for i, name in ((0, "один агент"), (1, "команда")):
        ship = sum(shippable(r[i]) for r in rows)
        print(f"{name:12} {total(i, 'sec'):>8.1f} {total(i, 'usd'):>11.5f} "
              f"{total(i, 'calls'):>10} {ship:>9}/{len(rows)}")
