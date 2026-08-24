"""
М4 — патерни MAS на LangGraph: ті самі приклади, що на слайдах колоди.

Кожен патерн — окрема команда, можна показувати по одному прямо за слайдом:

    python patterns_langgraph.py parallel     # Паралельний + Агрегатор (reducer)
    python patterns_langgraph.py supervisor   # Маршрутизатор: інтент → воркер
    python patterns_langgraph.py loop         # Петля: генератор ↔ критик
    python patterns_langgraph.py network      # Мережа: Command(goto=...)
    python patterns_langgraph.py fanout       # Orchestrator–Worker: Send
    python patterns_langgraph.py store        # Памʼять: checkpointer + Store
    python patterns_langgraph.py              # усі по черзі

Це навмисно НЕ один великий граф: на занятті цінніше бачити кожен патерн
голим, без сусідів. Продакшн-версія роутера з правом діяти — run.py 4.
"""

import operator
import sys
import pathlib
from typing import Annotated, TypedDict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.store.memory import InMemoryStore
    from langgraph.types import Command, Send
except ImportError:
    raise SystemExit("Потрібен LangGraph:  pip install -r requirements.txt")

from core.agent import ask
from domain import backend, knowledge

QUERY = "Посилка EE123456789UA не прийшла вже два тижні. Я хочу повернути гроші за доставку."


class S(TypedDict, total=False):
    query: str
    route: str
    tasks: list
    results: Annotated[list, operator.add]   # reducer: паралельні записи ЗЛИВАЮТЬСЯ
    verdict: str
    loops: int
    answer: str


def _synth(s: S) -> S:
    """Спільний агрегатор: зводить results в одну відповідь клієнту."""
    answer = ask("Ти — підтримка поштового оператора. Зведи факти в коротку "
                 "відповідь клієнту українською, нічого не додумуй.",
                 f"Звернення: {s['query']}\nФакти:\n" + "\n".join(map(str, s["results"])),
                 max_tokens=300)
    return {"answer": answer}


# ── Паралельний + Агрегатор: два ребра зі START, злиття чекає обидві ──
def demo_parallel() -> None:
    def rules(s: S) -> S:
        return {"results": [f"Правила: {knowledge.retrieve(s['query'], 2)}"]}

    def orders(s: S) -> S:
        return {"results": [f"Бекенд: {backend.get_order_status('EE123456789UA')}"]}

    g = StateGraph(S)
    for n, f in [("rules", rules), ("orders", orders), ("merge", _synth)]:
        g.add_node(n, f)
    g.add_edge(START, "rules")      # два ребра зі START =
    g.add_edge(START, "orders")     # = паралельний запуск
    g.add_edge("rules", "merge")
    g.add_edge("orders", "merge")   # merge виконається раз — коли готові ОБИДВІ
    g.add_edge("merge", END)

    out = g.compile().invoke({"query": QUERY, "results": []})
    print(f"  гілок відпрацювало: {len(out['results'])} (без reducer був би "
          f"InvalidUpdateError — два записи в одне поле)")
    print(f"  → {out['answer'][:180]}…")


# ── Маршрутизатор (Supervisor): дешева модель класифікує, граф веде ──
def demo_supervisor() -> None:
    def router(s: S) -> S:
        raw = ask("Класифікуй звернення клієнта пошти. Відповідай СУВОРО одним "
                  "словом:\nSTATUS — питає, де посилка\nREFUND — хоче повернення "
                  "грошей чи компенсацію\nHUMAN — усе інше.",
                  s["query"], max_tokens=10).upper()
        # модель інколи додає крапку чи пояснення — шукаємо мітку, не рівність
        return {"route": next((r for r in ("REFUND", "STATUS") if r in raw), "HUMAN")}

    def status_worker(s: S) -> S:
        facts = [backend.get_order_status("EE123456789UA")]
        return {"results": facts, **_synth({"query": s["query"], "results": facts})}

    def refund_worker(s: S) -> S:
        facts = [backend.get_order_status("EE123456789UA"),
                 backend.check_refund_eligibility("EE123456789UA")]
        return {"results": facts, **_synth({"query": s["query"], "results": facts})}

    g = StateGraph(S)
    g.add_node("router", router)
    g.add_node("status", status_worker)   # воркери: кожен зі своїм набором дій
    g.add_node("refund", refund_worker)
    g.add_edge(START, "router")
    g.add_conditional_edges("router", lambda s: s["route"],
                            {"STATUS": "status", "REFUND": "refund", "HUMAN": END})
    for n in ("status", "refund"):
        g.add_edge(n, END)

    out = g.compile().invoke({"query": QUERY, "results": []})
    print(f"  router → {out['route']}")
    print(f"  → {out.get('answer', 'HUMAN: ескалація без витрат на воркера')[:180]}…")


# ── Петля (Evaluator–Optimizer): критик жене генератора по колу ──
def demo_loop() -> None:
    rules = "\n".join(knowledge.retrieve(QUERY, 3))   # генератор пише ЗА правилами

    def draft(s: S) -> S:
        note = "" if not s.get("loops") else " Обовʼязково назви суму і номер правила."
        return {"results": [], "answer": ask(
            "Відповідь клієнту пошти українською, 2 речення, строго за правилами:\n"
            + rules + note, s["query"], max_tokens=200)}

    def critic(s: S) -> S:                       # дешева модель, ~100 токенів
        verdict = ask("Ти критик. Правила:\n" + rules + "\nВідповідь нижче називає "
                      "суму і номер правила, і НЕ суперечить правилам? "
                      "Відповідай одним словом: OK або REVISE.",
                      s["answer"], max_tokens=5).strip().upper()
        return {"verdict": "REVISE" if "REVISE" in verdict else "OK",
                "loops": s.get("loops", 0) + 1}

    g = StateGraph(S)
    g.add_node("draft", draft)
    g.add_node("critic", critic)
    g.add_edge(START, "draft")
    g.add_edge("draft", "critic")
    g.add_conditional_edges(
        "critic",
        lambda s: "draft" if s["verdict"] == "REVISE" and s["loops"] < 3 else END)
    # без ліміту обертів критик-перфекціоніст = нескінченний цикл за ваші гроші

    out = g.compile().invoke({"query": QUERY})
    print(f"  обертів: {out['loops']}, фінальний вердикт: {out['verdict']}")
    print(f"  → {out['answer'][:180]}…")


# ── Мережа: кожен агент сам вирішує, кому передати (Command) ──
def demo_network() -> None:
    def billing(s: S) -> Command:
        if "статус" in s["query"].lower() or "де " in s["query"].lower():
            print("  billing: не моє питання → передаю tech")
            return Command(goto="tech")
        return Command(goto=END, update=_synth(
            {"query": s["query"],
             "results": [backend.check_refund_eligibility("EE123456789UA")]}))

    def tech(s: S) -> Command:
        if "грош" in s["query"].lower() or "поверн" in s["query"].lower():
            print("  tech: не моє питання → передаю billing")
            return Command(goto="billing")
        return Command(goto=END, update=_synth(
            {"query": s["query"],
             "results": [backend.get_order_status("EE123456789UA")]}))

    g = StateGraph(S)
    g.add_node("billing", billing)
    g.add_node("tech", tech)
    g.add_edge(START, "tech")            # свідомо не туди: хай передасть сам
    out = g.compile().invoke({"query": QUERY})
    print(f"  → {out['answer'][:180]}…")
    print("  маршрут не видно у визначенні графа — тому мережа в проді останній засіб")


# ── Orchestrator–Worker: Send розсилає підзадачі паралельно ──
def demo_fanout() -> None:
    def plan(s: S) -> S:                 # оркестратор: розбити задачу
        tasks = ask("Розбий звернення клієнта пошти на 2-3 незалежні підзадачі "
                    "для перевірки, по одній на рядок, без нумерації.",
                    s["query"], max_tokens=100).strip().splitlines()
        # модель попри інструкцію інколи додає заголовок — відсіюємо не-задачі
        tasks = [t.strip(" -*") for t in tasks
                 if t.strip() and not t.lstrip().startswith("#")
                 and not t.rstrip().endswith(":")]
        return {"tasks": tasks[:3]}

    def fan_out(s: S) -> list[Send]:     # кожна підзадача — окремий воркер
        return [Send("worker", {"query": s["query"], "tasks": [t]})
                for t in s["tasks"]]

    def worker(s: S) -> S:               # ізольований контекст: лише СВОЯ підзадача
        facts = {"status": backend.get_order_status("EE123456789UA")}
        return {"results": [ask("Дай відповідь на одну підзадачу за фактами, 1 речення.",
                                f"Підзадача: {s['tasks'][0]}\nФакти: {facts}",
                                max_tokens=100)]}

    g = StateGraph(S)
    g.add_node("plan", plan)
    g.add_node("worker", worker)
    g.add_node("aggregate", _synth)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", fan_out, ["worker"])   # паралельний fan-out
    g.add_edge("worker", "aggregate")
    g.add_edge("aggregate", END)

    out = g.compile().invoke({"query": QUERY, "results": []})
    print(f"  оркестратор нарізав підзадач: {len(out['tasks'])}")
    for t in out["tasks"]:
        print(f"    · {t[:70]}")
    print(f"  → {out['answer'][:180]}…")


# ── Памʼять: checkpointer (діалог) + Store (клієнт, між діалогами) ──
def demo_store() -> None:
    store = InMemoryStore()              # у проді: Postgres

    def worker(s: S) -> S:
        # воркер дописує факт про клієнта — namespace = клієнт, не діалог
        store.put(("clients", "client-42"), "profile",
                  {"tracking": "EE123456789UA", "vip": True})
        return _synth({"query": s["query"],
                       "results": [backend.get_order_status("EE123456789UA")]})

    g = StateGraph(S)
    g.add_node("worker", worker)
    g.add_edge(START, "worker")
    app = g.compile(checkpointer=MemorySaver(), store=store)

    app.invoke({"query": QUERY}, {"configurable": {"thread_id": "dialog-1"}})
    print("  діалог 1: відповіли, у Store записано профіль клієнта")

    # наступного тижня, НОВИЙ діалог (інший thread_id), питання без трек-номера:
    hits = store.search(("clients", "client-42"))
    profile = hits[0].value
    print(f"  діалог 2: Store віддав профіль без трек-номера → {profile}")
    print("  сесія (checkpointer) = «що зʼясували зараз»; Store = «що знаємо взагалі»")


DEMOS = {"parallel": demo_parallel, "supervisor": demo_supervisor,
         "loop": demo_loop, "network": demo_network,
         "fanout": demo_fanout, "store": demo_store}

if __name__ == "__main__":
    wanted = [a for a in sys.argv[1:] if a in DEMOS] or list(DEMOS)
    for name in wanted:
        print(f"\n=== {name} ===")
        DEMOS[name]()
