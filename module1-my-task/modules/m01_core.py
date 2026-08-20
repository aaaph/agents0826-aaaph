"""
МОДУЛЬ 1 — Ядро агента

Додаємо: цикл «міркуй → дій → спостерігай» + інструменти каскаду.
Агент уміє знайти виконання й подивитись метрики, але не має права нічого змінити.

Тут же під'єднана ескалація: якщо агент не закрив питання сам —
воно йде інженеру з номером тікета, а не лише текстом у відповіді.
"""

from config import BASE_PROMPT
from core import escalation
from core.agent import run_agent
from domain.backend import tools_for

TITLE = "Ядро агента"
ADDS = "цикл «міркуй → дій → спостерігай» + каскад інструментів"
FILES = ["core/agent.py", "domain/backend.py"]


def _ref(result: dict) -> str:
    """Перший run_id, якого агент устиг торкнутись — щоб тікет був не порожній."""
    for step in result.get("trace", []):
        rid = step.get("input", {}).get("run_id")
        if rid:
            return rid
    return "—"


# Свідоме рішення: no_tool_used НЕ ескалюємо.
# Користувач — інженер; питання про теорію VIO він оцінить сам, а бекенд і не був
# для нього джерелом. Ескалація тут смикала б чергового намарно.
# Прапорець при цьому лишається у відповіді — метрику видно, дію за нею не робимо.
# (У core/escalation.py ця причина єдина, що не гейтиться через ESCALATE_ON,
#  тому вимикаємо її тут, а не конфігом.)
NO_ESCALATE = {"no_tool_used"}


def run(query: str) -> dict:
    result = run_agent(system=BASE_PROMPT, tools=tools_for(1), query=query)
    if escalation.decide(result, query) in NO_ESCALATE:
        result["escalated"] = False
        return result
    return escalation.apply(result, query, _ref(result))
