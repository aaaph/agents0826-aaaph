"""
МОДУЛЬ 9 — Клієнтський шар

Додаємо: стрімінг відповіді. Користувач бачить перші слова одразу,
а не чекає, поки агент завершить усі кроки.

Метрика модуля — час до першого токена (TTFT), а не якість відповіді.
"""

if __name__ == "__main__":            # прямий запуск: корінь модуля у sys.path
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import time
from core.agent import client, _track
from domain.knowledge import as_context
from config import BASE_PROMPT, MODEL, MAX_TOKENS

TITLE = "Клієнтський шар"
ADDS  = "стрімінг відповіді, час до першого токена"
FILES = ["modules/m09_client.py"]


def run(query: str) -> dict:
    started = time.time()
    first_token_at = None
    chunks = []

    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=BASE_PROMPT + as_context(query),
        messages=[{"role": "user", "content": query}],
    ) as stream:
        for text in stream.text_stream:
            if first_token_at is None:
                first_token_at = time.time() - started
            chunks.append(text)
        # стрімінг оминає _call() — вартість треба трекати окремо
        _track(MODEL, stream.get_final_message().usage)

    total = time.time() - started
    return {
        "answer": "".join(chunks).strip(),
        "trace": [],
        "ttft_sec": round(first_token_at or 0, 2),
        "total_sec": round(total, 2),
        "speedup": f"користувач бачить текст на {round(total - (first_token_at or 0), 1)}с раніше",
    }


if __name__ == "__main__":
    # те саме, що `python run.py 9`, лише без підсумкових метрик і вартості
    from config import USER_QUERY

    print(f"[{TITLE}] додає: {ADDS}\n")
    _r = run(USER_QUERY)
    _tools = [t["tool"] for t in _r.get("trace", [])]
    if _tools:
        print("інструменти:", " → ".join(_tools))
    print("\n" + _r["answer"])
    print("\nПовний прогін з метриками і вартістю:  python run.py 9")
