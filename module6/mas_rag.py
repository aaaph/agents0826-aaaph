"""
М2 — MAS RAG вручну: два субагенти з ізольованим контекстом + синтез.

Без фреймворків і SDK: субагент — це просто вузький промпт над ОДНИМ джерелом.
Кожен бачить лише своє і не знає про інше — тому платить за своє вікно.

  rules   — шукає у базі знань (retrieve) і виписує лише релевантні правила
  orders  — дістає факти з бекенду (статус, дні, суми)
  синтез  — оркестратор бачить два коротких конспекти, а не два сирих джерела

Пуант для заняття: порівняйте input-токени MAS проти «все в один промпт».
Ізоляція — це не тільки чистота, це гроші.

    python mas_rag.py              # MAS проти наївного «все в один промпт»
    python mas_rag.py --big        # те саме на базі з 210 правил — де MAS виграє
    python mas_rag.py --sequential # без паралельності, щоб побачити різницю в часі
"""

import re
import sys
import time
import pathlib
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from config import USER_QUERY
from core.agent import USAGE, ask, reset_usage
from domain import backend
from domain.knowledge import KB, retrieve

RULES_PROMPT = (
    "Ти — субагент бази знань поштового оператора. Тобі дано витяг правил. "
    "Випиши ТІЛЬКИ ті, що стосуються запиту, по одному рядку. "
    "Нічого не додумуй і не рахуй суми."
)
ORDERS_PROMPT = (
    "Ти — субагент довідки про відправлення. Тобі дано факти з бекенду. "
    "Випиши стисло: статус, скільки днів у дорозі, заявлений строк, суму доставки."
)
SYNTH_PROMPT = (
    "Ти — асистент підтримки. Тобі дано два конспекти від субагентів: правила і "
    "факти про відправлення. Дай коротку відповідь клієнту українською, спираючись "
    "лише на них, і назви правило, яким керуєшся."
)


def _tracking(query: str) -> str:
    m = re.search(r"[A-Z]{2}\d{9}[A-Z]{2}", query.upper())
    return m.group(0) if m else "—"


# ── субагенти: кожен бачить ЛИШЕ своє джерело ─────────────────
def agent_rules(query: str) -> str:
    excerpt = "\n".join(retrieve(query, k=3))
    return ask(RULES_PROMPT, f"Запит: {query}\n\nПравила:\n{excerpt}", max_tokens=300)


def agent_orders(query: str) -> str:
    tracking = _tracking(query)
    facts = {
        "status": backend.get_order_status(tracking),
        "eligibility": backend.check_refund_eligibility(tracking),
    }
    return ask(ORDERS_PROMPT, f"Запит: {query}\n\nФакти: {facts}", max_tokens=300)


def run_mas(query: str, parallel: bool = True) -> dict:
    started = time.time()
    if parallel:
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_rules = pool.submit(agent_rules, query)
            f_orders = pool.submit(agent_orders, query)
            rules, orders = f_rules.result(), f_orders.result()
    else:
        rules, orders = agent_rules(query), agent_orders(query)

    answer = ask(SYNTH_PROMPT,
                 f"Запит: {query}\n\nПравила:\n{rules}\n\nВідправлення:\n{orders}",
                 max_tokens=500, fast=False)
    return {"answer": answer, "rules": rules, "orders": orders,
            "elapsed_sec": round(time.time() - started, 2)}


def run_naive(query: str, kb=None) -> dict:
    """Контрольний варіант: усе в один промпт, без ізоляції."""
    tracking = _tracking(query)
    kb = kb if kb is not None else KB
    everything = (
        "Усі правила оператора:\n" + "\n".join(text for _, text in kb) +
        f"\n\nВсі дані про відправлення: {backend.get_order_status(tracking)}"
        f"\n{backend.check_refund_eligibility(tracking)}"
    )
    started = time.time()
    answer = ask("Ти — асистент підтримки поштового оператора. Відповідай стисло.",
                 f"{everything}\n\nЗапит клієнта: {query}", max_tokens=500, fast=False)
    return {"answer": answer, "elapsed_sec": round(time.time() - started, 2)}


if __name__ == "__main__":
    parallel = "--sequential" not in sys.argv
    # --big: та сама база, роздута до розміру реальної (регіональні уточнення тощо)
    kb = KB * 15 if "--big" in sys.argv else KB

    reset_usage()
    mas = run_mas(USER_QUERY, parallel=parallel)
    mas_in, mas_calls = USAGE["in"], USAGE["calls"]

    reset_usage()
    naive = run_naive(USER_QUERY, kb=kb)
    naive_in = USAGE["in"]

    print(f"── Субагент rules ({'паралельно' if parallel else 'послідовно'}) ──")
    print("  " + mas["rules"][:200].replace("\n", "\n  "))
    print("\n── Субагент orders ──")
    print("  " + mas["orders"][:200].replace("\n", "\n  "))
    print(f"\n── Синтез ──\n  {mas['answer'][:260]}")

    print("\n" + "═" * 64)
    print(f"  база знань: {len(kb)} правил")
    print(f"  MAS:    {mas_in:>6} вхідних токенів · {mas_calls} виклики · {mas['elapsed_sec']}с")
    print(f"  наївно: {naive_in:>6} вхідних токенів · 1 виклик · {naive['elapsed_sec']}с")
    if mas_in > naive_in:
        print(f"\n  MAS ДОРОЖЧИЙ на {(mas_in / naive_in - 1) * 100:.0f}%: на маленькій базі")
        print("  ізоляція не окупається — три виклики коштують більше, ніж заощаджують.")
        print("  Спробуйте: python mas_rag.py --big")
    else:
        print(f"\n  MAS дешевший у {naive_in / mas_in:.1f}× — і майже не залежить від розміру")
        print("  бази: субагент бачить top-K, а не всю KB. Наївний промпт росте лінійно.")
    print("\n  Кожен субагент платить лише за своє джерело, але кожен виклик має ціну.")
    print("  Повноцінний MAS з маршрутизацією і правом діяти — на модулі 4.")
