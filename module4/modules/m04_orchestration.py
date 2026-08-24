"""
МОДУЛЬ 4 — Оркестрація

Додаємо: маршрутизатор визначає категорію звернення і передає
профільному агенту. Профільні агенти мають право діяти.

Саме тут та сама фраза користувача вперше доводиться до результату.
"""

if __name__ == "__main__":            # прямий запуск: корінь модуля у sys.path
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core import escalation
from core.agent import run_agent, ask
from domain.backend import tools_for
from domain.knowledge import as_context
from config import BASE_PROMPT

TITLE = "Оркестрація"
ADDS  = "маршрутизатор + профільні агенти, право діяти"
FILES = ["modules/m04_orchestration.py"]

ROUTER = (
    "Класифікуй звернення клієнта в одну категорію: "
    "STATUS, FINANCE, CLAIM, HUMAN. "
    "HUMAN — якщо клієнт просить зʼєднати з людиною. "
    "Відповідай одним словом."
)

SPECIALISTS = {
    "STATUS":  "Ти агент зі статусів відправлень.",
    "FINANCE": "Ти агент з фінансових питань і повернення коштів. Якщо інструмент "
               "підтвердив право на повернення — одразу оформи претензію через "
               "create_claim і назви її номер, не проси додаткових підтверджень.",
    "CLAIM":   "Ти агент з претензій. Якщо інструмент підтвердив право клієнта — "
               "одразу оформлюй претензію через create_claim і назви її номер, "
               "не проси додаткових підтверджень.",
    "HUMAN":   "Клієнт просить оператора — одразу виклич escalate_to_human.",
}


def run(query: str) -> dict:
    # роутер — дешева модель: класифікація не потребує міркування
    category = ask(ROUTER, query, max_tokens=20, fast=True).upper().strip(".")
    if category not in SPECIALISTS:
        category = "CLAIM"

    result = run_agent(
        system=f"{BASE_PROMPT} {SPECIALISTS[category]}" + as_context(query),
        tools=tools_for(4),
        query=query,
    )
    result["routed_to"] = category
    return escalation.apply(result, query, _tracking(query))


def _tracking(query: str) -> str:
    """Витягує трек-номер із тексту звернення."""
    import re
    m = re.search(r"[A-Z]{2}\d{9}[A-Z]{2}", query.upper())
    return m.group(0) if m else "—"


if __name__ == "__main__":
    # те саме, що `python run.py 4`, лише без підсумкових метрик і вартості
    from config import USER_QUERY

    print(f"[{TITLE}] додає: {ADDS}\n")
    _r = run(USER_QUERY)
    _tools = [t["tool"] for t in _r.get("trace", [])]
    if _tools:
        print("інструменти:", " → ".join(_tools))
    print("\n" + _r["answer"])
    print("\nПовний прогін з метриками і вартістю:  python run.py 4")
