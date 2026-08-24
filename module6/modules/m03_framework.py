"""
МОДУЛЬ 3 — Шар фреймворку

Додаємо: явні стани замість вільного циклу + чекпоінт після кожного стану.
Якщо процес перерветься — агент продовжить з місця зупинки,
а не почне розмову спочатку.

Право діяти ще НЕ з'явилось: стани VERIFY → DECIDE → CONFIRM,
без ACT. Оформлення претензії стане можливим на модулі 4.
"""

if __name__ == "__main__":            # прямий запуск: корінь модуля у sys.path
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import json
from core.agent import run_agent
from domain.backend import tools_for
from domain.knowledge import as_context
from config import BASE_PROMPT, OUT_DIR

TITLE = "Шар фреймворку"
ADDS  = "явні стани, чекпоінт, відновлення після збою"
FILES = ["modules/m03_framework.py"]

STATES = ["VERIFY", "DECIDE", "CONFIRM"]
CHECKPOINT = OUT_DIR / "checkpoint.json"


def save_checkpoint(state: str, payload: dict):
    CHECKPOINT.write_text(
        json.dumps({"state": state, "payload": payload}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_checkpoint() -> dict | None:
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return None


def run(query: str, resume: bool = False) -> dict:
    if resume and (cp := load_checkpoint()):
        return {**cp["payload"], "resumed_from": cp["state"]}

    system = (
        BASE_PROMPT
        + f"\n\nПрацюй за станами: {' → '.join(STATES)}. "
          "Познач поточний стан на початку відповіді."
        + as_context(query)
    )

    result = run_agent(
        system=system,
        tools=tools_for(3),          # статус + право: подивитись і дізнатись, ще не діяти
        query=query,
    )

    result["states"] = STATES
    result["checkpoint"] = {"state": "CONFIRM", "resumable": True}
    save_checkpoint("CONFIRM", {"answer": result["answer"], "trace": result["trace"]})
    return result


if __name__ == "__main__":
    # те саме, що `python run.py 3`, лише без підсумкових метрик і вартості
    from config import USER_QUERY

    print(f"[{TITLE}] додає: {ADDS}\n")
    _r = run(USER_QUERY)
    _tools = [t["tool"] for t in _r.get("trace", [])]
    if _tools:
        print("інструменти:", " → ".join(_tools))
    print("\n" + _r["answer"])
    print("\nПовний прогін з метриками і вартістю:  python run.py 3")
