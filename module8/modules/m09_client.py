"""
МОДУЛЬ 9 — Клієнтський шар

Додаємо: стрімінг відповіді. Користувач бачить перші слова одразу,
а не чекає, поки агент завершить усі кроки.

Метрика модуля — час до першого токена (TTFT), а не якість відповіді.
"""

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
