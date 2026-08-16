"""
М3 — той самий агент на langchain 1.x: create_agent + middleware.

Дві тези колоди М3 наживо:
  · @tool: type hints стають вхідною схемою, docstring — описом для моделі;
  · middleware — перехоплювачі до/після кроків agent loop. Наші ручні
    механізми виявляються вбудованими:
      MAX_TURNS (М1)           → ModelCallLimitMiddleware
      трейсинг кроків (буде М7)→ кастомний wrap_tool_call
      PII-фільтр (буде М6)     → PIIMiddleware
    (deny-хуки перед інструментами теж робляться через wrap_tool_call —
     напишемо руками на М6, коли з'явиться право діяти)

    python run_create_agent.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:
    from langchain.agents import create_agent
    from langchain.agents.middleware import (
        AgentMiddleware, ModelCallLimitMiddleware, PIIMiddleware)
    from langchain_anthropic import ChatAnthropic
    from langchain_core.tools import tool
except ImportError as e:
    raise SystemExit(f"Бракує пакета ({e.name}): pip install -r requirements.txt")

from config import BASE_PROMPT, MODEL, USER_QUERY
from domain import backend


# ── tools: type hints = схема, docstring = опис для моделі ────
@tool
def get_order_status(tracking: str) -> dict:
    """Повертає статус відправлення за трек-номером, напр. EE123456789UA."""
    return backend.get_order_status(tracking)


@tool
def check_refund_eligibility(tracking: str) -> dict:
    """Перевіряє право на повернення ВАРТОСТІ ДОСТАВКИ за трек-номером."""
    return backend.check_refund_eligibility(tracking)


# ── кастомний middleware: трейсинг кожного виклику інструмента ──
class SpanLogger(AgentMiddleware):
    """Перехоплює кожен tool-виклик. На М7 сюди стане OTEL/Langfuse."""

    def __init__(self):
        super().__init__()
        self.spans: list[str] = []

    def wrap_tool_call(self, request, handler):
        name = request.tool_call["name"]
        self.spans.append(f"{name}({request.tool_call.get('args', {})})")
        return handler(request)


if __name__ == "__main__":
    logger = SpanLogger()
    agent = create_agent(
        model=ChatAnthropic(model=MODEL, max_tokens=1000),
        tools=[get_order_status, check_refund_eligibility],
        system_prompt=BASE_PROMPT,
        middleware=[
            logger,                                            # трейсинг (М7 — руками)
            ModelCallLimitMiddleware(run_limit=6,              # MAX_TURNS з М1
                                     exit_behavior="end"),
            PIIMiddleware("credit_card", strategy="redact"),   # PII-фільтр (М6 — руками)
        ],
    )

    state = agent.invoke({"messages": [{"role": "user", "content": USER_QUERY}]})
    answer = state["messages"][-1].content
    if isinstance(answer, list):                               # anthropic content blocks
        answer = "".join(b.get("text", "") for b in answer if isinstance(b, dict))

    print(f"запит: «{USER_QUERY}»")
    for span in logger.spans:
        print(f"  tool: {span}")
    print(f"→ {answer[:300]}\n")
    print("Пуант: MAX_TURNS ми писали руками на М1 — у langchain 1.x це штатний")
    print("middleware. PII-фільтр і deny-хуки напишемо руками на М6, трейсинг —")
    print("на М7, і щоразу виявиться, що фреймворк уже має таку «розетку».")
    print("Фреймворк = ті самі шари, написані за вас. Але щоб знати, ЩО він")
    print("робить за вас, треба один раз зібрати їх власноруч.")
