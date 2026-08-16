"""
М8 — той самий агент за HTTP: логіка не змінилась, змінився спосіб запуску.

POST /ask      — повний цикл (оркестрація М4 + ескалація), JSON з метриками
GET  /stream   — стрімінг відповіді (SSE), метрика — TTFT, як у m09
GET  /health   — для проби живучості в оркестраторі

    pip install fastapi uvicorn
    uvicorn api:app --port 8000
    curl -s localhost:8000/ask -X POST -H 'content-type: application/json' \
         -d '{"query": "Посилка EE123456789UA не прийшла вже два тижні. Поверніть гроші."}'
"""

import json
import sys
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel
except ImportError:
    raise SystemExit("Потрібно:  pip install fastapi uvicorn")

from config import BASE_PROMPT, MODEL, MAX_TOKENS
from core import cost
from core.agent import USAGE, client, reset_usage
from domain.knowledge import as_context
from modules import m04_orchestration

app = FastAPI(title="agentpro", version="0.1.0")


class Ask(BaseModel):
    query: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/ask")
def ask(body: Ask):
    started = time.time()
    reset_usage()
    result = m04_orchestration.run(body.query)
    return {
        "answer": result["answer"],
        "outcome": result.get("outcome"),
        "routed_to": result.get("routed_to"),
        "escalated": result.get("escalated", False),
        "tools": [t["tool"] for t in result.get("trace", [])],
        "elapsed_sec": round(time.time() - started, 2),
        "cost_usd": cost.usd(USAGE["by_model"]),
    }


@app.get("/stream")
def stream(query: str):
    """SSE: стрімінг + інструменти.

    Нюанс продакшену: наївний стрімінг (як у m09) не має інструментів —
    на «де посилка?» агент чесно відповідає, що не бачить трекінгу.
    Тому спершу детермінована фаза інструментів (з проміжними подіями
    прогресу), а стрімиться лише фінальна генерація відповіді.
    TTFT — час до першого токена саме її.
    """
    import re
    from domain import backend

    def gen():
        started = time.time()

        m = re.search(r"[A-Z]{2}\d{9}[A-Z]{2}", query.upper())
        facts = {}
        if m:
            tracking = m.group(0)
            yield f"data: {json.dumps({'stage': 'tools', 'tool': 'get_order_status'})}\n\n"
            facts["status"] = backend.get_order_status(tracking)
            yield f"data: {json.dumps({'stage': 'tools', 'tool': 'check_refund_eligibility'})}\n\n"
            facts["eligibility"] = backend.check_refund_eligibility(tracking)

        system = (BASE_PROMPT + as_context(query)
                  + (f"\n\nФакти з бекенду (використовуй тільки їх): {facts}" if facts
                     else "\n\nТрек-номера в запиті немає — попроси його, нічого не вигадуй."))

        first = None
        with client.messages.stream(
            model=MODEL, max_tokens=MAX_TOKENS, system=system,
            messages=[{"role": "user", "content": query}],
        ) as s:
            for text in s.text_stream:
                if first is None:
                    first = round(time.time() - started, 2)
                yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
            usage = s.get_final_message().usage      # стрімінг оминає _call()
        from core.agent import _track
        _track(MODEL, usage)
        yield f"data: {json.dumps({'done': True, 'ttft_sec': first})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
