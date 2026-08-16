"""
М3 — той самий агент на LangGraph.

Стани з modules/m03_framework (VERIFY → DECIDE → CONFIRM) стають вузлами
графа, чекпоінт — checkpointer з коробки. LLM тут лише один раз, у CONFIRM:
перші два стани — детерміновані виклики бекенду. Порівняйте з m03: там ті
самі стани «просить» тримати модель — тут їх тримає граф.

Право діяти (create_claim) з'явиться на модулі 4 — тому граф завершується
рішенням «належить / не належить», без оформлення.

    python run_langgraph.py             # весь граф
    python run_langgraph.py --pause     # зупинка після DECIDE + resume
"""

import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    raise SystemExit("Потрібен LangGraph:  pip install langgraph")

from typing import TypedDict
from config import USER_QUERY
from core.agent import ask
from domain import backend


class S(TypedDict, total=False):
    query: str
    tracking: str
    status: dict
    eligibility: dict
    answer: str


def verify(s: S) -> S:
    m = re.search(r"[A-Z]{2}\d{9}[A-Z]{2}", s["query"].upper())
    tracking = m.group(0) if m else "—"
    return {"tracking": tracking, "status": backend.get_order_status(tracking)}


def decide(s: S) -> S:
    return {"eligibility": backend.check_refund_eligibility(s["tracking"])}


def confirm(s: S) -> S:
    facts = {k: s.get(k) for k in ("status", "eligibility")}
    answer = ask(
        "Ти — асистент підтримки поштового оператора. Сформулюй коротку відповідь "
        "клієнту українською строго за наведеними фактами, нічого не додумуй. "
        "Оформлювати претензію ти поки не вмієш — поясни, що належить клієнту.",
        f"Звернення: {s['query']}\nФакти: {facts}",
        max_tokens=400, fast=False,
    )
    return {"answer": answer}


def build():
    g = StateGraph(S)
    for name, fn in [("VERIFY", verify), ("DECIDE", decide), ("CONFIRM", confirm)]:
        g.add_node(name, fn)
    g.add_edge(START, "VERIFY")
    g.add_edge("VERIFY", "DECIDE")
    g.add_edge("DECIDE", "CONFIRM")
    g.add_edge("CONFIRM", END)
    return g.compile(checkpointer=MemorySaver(),
                     interrupt_after=["DECIDE"] if "--pause" in sys.argv else [])


if __name__ == "__main__":
    app = build()
    cfg = {"configurable": {"thread_id": "demo-1"}}

    out = app.invoke({"query": USER_QUERY}, cfg)

    if "--pause" in sys.argv:
        # граф зупинився після DECIDE — стан лежить у чекпоінтері
        snap = app.get_state(cfg)
        print("── Пауза після DECIDE (стан у чекпоінтері) ──")
        print("  eligibility:", snap.values.get("eligibility", {}).get("eligible"))
        print("  далі:", snap.next)
        print("  …тут людина могла б підтвердити наступний крок (human-in-the-loop)\n")
        out = app.invoke(None, cfg)          # resume: продовжуємо, не починаючи спочатку

    print("── Результат ──")
    print("  eligibility:", out.get("eligibility", {}).get("eligible"),
          "| сума:", out.get("eligibility", {}).get("refundable_amount_uah", "—"), "грн")
    print("  →", out["answer"][:300])
