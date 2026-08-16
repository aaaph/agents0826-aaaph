"""
М7 — тиха деградація, найсильніший момент курсу, однією командою.

Сценарій: агент НЕ змінювався. Вийшов «реліз API v2» бекенду:
  · дні в дорозі тепер рахуються від останнього сканування (стало 3
    замість 15) — типовий дрейф семантики поля;
  · статуси перекодовано — «Розшук» тепер віддається як «В дорозі».

Жодних помилок: агент чесно і впевнено переказує зіпсуті дані, логи
чисті — а гейт падає, бо агент відмовляє в поверненні тим, кому воно
належить. Урок: eval ловить деградацію ДАНИХ, не лише промптів — саме
тому потрібні online-евали, а не разова перевірка перед релізом.

(Історія попередніх спроб цього демо — окремий урок, див. README:
вимкнення retrieval і навіть викидання текстів правил з інструментів
деградації НЕ дало — політика продубльована у типізованих полях бекенду.)

УВАГА: це 2 × (14 кейсів × 2 LLM-виклики) — кілька хвилин і ~десятки центів.

    python degradation_demo.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from domain import backend
from modules import m07_evaluation as m07


def run_eval(label: str) -> dict:
    print(f"\n=== Прогін: {label} ===")
    r = m07.run()
    for c in r["cases"]:
        mark = "PASS" if c["pass"] else "FAIL"
        print(f"  [{mark}] {c['id']:<22} tool_ok={c['tool_ok']} judge={c['judge_pass']}")
    print(f"  → {r['score']}  gate: {r['gate']}")
    return r


def _api_v2_drift() -> dict:
    """«Реліз API v2»: дрейф семантики полів. Повертає бекап для відкату."""
    saved = {k: (v["days_in_transit"], v["status"]) for k, v in backend.ORDERS.items()}
    for o in backend.ORDERS.values():
        o["days_in_transit"] = 3                       # дні від останнього сканування
        if o["status"] == "Розшук":
            o["status"] = "В дорозі"                   # нове кодування статусів
    return saved


def _rollback(saved: dict):
    for k, (days, status) in saved.items():
        backend.ORDERS[k]["days_in_transit"] = days
        backend.ORDERS[k]["status"] = status


if __name__ == "__main__":
    healthy = run_eval("здоровий (бекенд v1)")

    # Деградація: агент той самий — «оновився» бекенд. Помилок немає. У тому й суть.
    saved = _api_v2_drift()
    try:
        degraded = run_eval("деградований (дрейф даних: API v2)")
    finally:
        _rollback(saved)

    print("\n" + "═" * 60)
    print(f"  здоровий:      {healthy['score']}  gate {healthy['gate']}")
    print(f"  деградований:  {degraded['score']}  gate {degraded['gate']}")
    flipped = [c["id"] for c, d in zip(healthy["cases"], degraded["cases"])
               if c["pass"] and not d["pass"]]
    print(f"  зламались кейси: {', '.join(flipped) if flipped else '—'}")
    print("\n  Логи чисті. Помилок немає. Відповіді впевнені.")
    print("  У звичайному софті зламане падає — в агентах зламане продовжує відповідати.")
