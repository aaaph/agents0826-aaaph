"""
МОДУЛЬ 6 — Безпека і спостережуваність

Додаємо два незалежні механізми:
  1) трейсинг — кожен крок агента фіксується зі структурою й таймінгом;
  2) guardrail — відповідь перевіряється ПЕРЕД показом користувачу.

Ключова думка: без цього ви не знаєте, ЧОМУ агент відповів саме так.
"""

if __name__ == "__main__":            # прямий запуск: корінь модуля у sys.path
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import time
from core.agent import run_agent, ask_json
from core import escalation
from domain.backend import tools_for
from domain.knowledge import as_context
from config import BASE_PROMPT

TITLE = "Спостережуваність і безпека"
ADDS  = "трейсинг кроків + перевірка відповіді перед показом"
FILES = ["modules/m06_security.py"]

GUARDRAIL = (
    "Ти — перевірка безпеки відповіді служби підтримки. Оціни текст і поверни JSON: "
    '{"pii_leak": bool, "unsupported_promise": bool, '
    '"verdict": "pass" | "block", "reason": "коротко"}'
)


class Tracer:
    """Мінімальний збирач трейсів. На продакшні тут OTEL-експортер."""

    def __init__(self):
        self.spans = []
        self._t0 = time.time()

    def __call__(self, step: dict):
        self.spans.append({
            "tool": step["tool"],
            "at_ms": round((time.time() - self._t0) * 1000),
            "ok": "error" not in step.get("output", {}),
        })

    def summary(self) -> dict:
        return {
            "spans": len(self.spans),
            "failed": sum(1 for s in self.spans if not s["ok"]),
            "timeline": self.spans,
        }


def run(query: str) -> dict:
    tracer = Tracer()

    result = run_agent(
        system=BASE_PROMPT + as_context(query),
        tools=tools_for(6),
        query=query,
        on_step=tracer,
    )

    result["tracing"] = tracer.summary()
    result["guardrail"] = ask_json(
        GUARDRAIL,
        result["answer"],
        fallback={"verdict": "pass", "reason": "не розпарсено"},
    )

    if result["guardrail"].get("verdict") == "block":
        result["answer_blocked"] = result["answer"]

    from modules.m04_orchestration import _tracking
    return escalation.apply(result, query, _tracking(query))


if __name__ == "__main__":
    # те саме, що `python run.py 6`, лише без підсумкових метрик і вартості
    from config import USER_QUERY

    print(f"[{TITLE}] додає: {ADDS}\n")
    _r = run(USER_QUERY)
    _tools = [t["tool"] for t in _r.get("trace", [])]
    if _tools:
        print("інструменти:", " → ".join(_tools))
    print("\n" + _r["answer"])
    print("\nПовний прогін з метриками і вартістю:  python run.py 6")
