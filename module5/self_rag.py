"""
М2 — Self-RAG / CRAG: перевірити знайдене ДО того, як відповідати.

Ідея одна: між retrieval і генерацією стоїть ВОРОТА. Якщо контексту не
досить — не вигадуємо, а щось робимо: переформулюємо запит, шукаємо ще
раз, і лише потім здаємось і кличемо людину.

Тут два рівні воріт — від найдешевшого до найдорожчого:

  1. ПОРІГ (детермінований, $0, миттєвий)
     схожість нижча за поріг → вважаємо, що не знайшли. Це вже є в
     knowledge_vec.as_context(): fail-closed.

  2. LLM-GRADE (дешева модель, ~100 токенів)
     схожість може бути високою, а контекст усе одно не відповідає на
     питання. Питаємо модель: RELEVANT чи WEAK.

  Що робити на WEAK — це і є різниця між підходами:
     CRAG      — переформулювати запит і шукати ще раз (у нас: rewrite)
     Self-RAG  — модель сама вирішує, коли шукати і чи критикувати себе
     наш вибір — rewrite, а якщо й це не дало нічого → ескалація на людину

    python self_rag.py           # три запити: звичайний, складний, поза доменом
    python self_rag.py --no-llm  # лише поріг, без LLM-судді (офлайн, без ключа)
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from core.agent import ask
from domain.backend import escalate_to_human

try:
    from knowledge_vec import retrieve, _THRESHOLD, scores
except ImportError:                       # запасний варіант — лексичний
    from domain.knowledge import retrieve
    _THRESHOLD, scores = 0.0, None

GRADE = (
    "Ти — воротар RAG-системи. Дано витяг правил і питання клієнта.\n"
    "Оціни, чи ДОСТАТНЬО цього витягу, щоб відповісти по суті.\n"
    "Відповідай одним словом: RELEVANT або WEAK."
)
REWRITE = (
    "Переформулюй запит клієнта в 3–6 слів так, щоб він збігався з мовою "
    "внутрішніх правил поштового оператора (терміни: прострочення, "
    "компенсація, розшук, вкладення, вартість доставки). Поверни лише запит."
)

QUERIES = [
    "Посилка EE123456789UA йде вже два тижні, поверніть гроші за доставку",
    "Кур'єр десь подів мою бандероль, хочу відшкодування за речі всередині",
    "Яка погода у Львові і чи варто йти на відділення?",
]


def grade(ctx: list[str], query: str, use_llm: bool = True) -> str:
    """Ворота. Повертає RELEVANT або WEAK."""
    if not ctx:
        return "WEAK"                      # поріг уже відсіяв усе — питати нема про що
    if not use_llm:
        return "RELEVANT"                  # рівень 1: довіряємо порогу
    verdict = ask(GRADE, f"Питання: {query}\n\nВитяг правил:\n" + "\n".join(ctx),
                  max_tokens=10)
    return "WEAK" if "WEAK" in verdict.upper() else "RELEVANT"


def answer_with_gate(query: str, use_llm: bool = True) -> dict:
    trace = []
    ctx = retrieve(query, k=3)
    trace.append(f"retrieve → {len(ctx)} правил (поріг {_THRESHOLD})")

    verdict = grade(ctx, query, use_llm)
    trace.append(f"grade → {verdict}")

    if verdict == "WEAK":
        # CRAG: переформулювати мовою предметної області і спробувати ще раз
        better = ask(REWRITE, query, max_tokens=40) if use_llm else query
        ctx2 = retrieve(better, k=3)
        trace.append(f"rewrite → «{better}» → {len(ctx2)} правил")
        if ctx2 and grade(ctx2, query, use_llm) == "RELEVANT":
            ctx, verdict = ctx2, "RELEVANT (після rewrite)"
        else:
            ticket = escalate_to_human("—", "немає правила під запит")
            trace.append(f"ескалація → {ticket['ticket']}")
            return {"answer": "Передаю звернення оператору — не знайшов правила "
                              "під ваш запит.", "verdict": "WEAK", "trace": trace,
                    "escalated": True}

    return {"answer": "Відповідаю за правилами:\n· " + "\n· ".join(t[:90] for t in ctx),
            "verdict": verdict, "trace": trace, "escalated": False}


if __name__ == "__main__":
    use_llm = "--no-llm" not in sys.argv
    print(f"Ворота: поріг {_THRESHOLD}" + (" + LLM-grade" if use_llm else " (лише поріг)"))
    print("=" * 70)
    for q in QUERIES:
        r = answer_with_gate(q, use_llm)
        print(f"\n«{q}»")
        for step in r["trace"]:
            print(f"   {step}")
        print(f"   → {r['answer'][:150]}")
    print("\n" + "=" * 70)
    print("Пуант: жодного разу агент не вигадав правило. Або знайшов, або")
    print("переформулював і знайшов, або чесно віддав людині.")
