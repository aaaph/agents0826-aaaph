"""
МОДУЛЬ 1 — Ядро агента

Цикл «міркуй → дій → спостерігай» + каскад інструментів.
Агент уміє знайти виконання й подивитись метрики, але знань про домен
не має: чому 0.157 багато чи мало — сказати нічим.

Тут же ескалація: якщо агент не закрив питання сам — воно йде інженеру
з номером тікета, а не лише текстом у відповіді.
"""

from config import BASE_PROMPT
from core import escalation
from core.agent import run_agent
from domain.backend import tools_for

TITLE = "Ядро агента"
ADDS = "цикл «міркуй → дій → спостерігай» + каскад інструментів"
FILES = ["core/agent.py", "domain/backend.py"]

# Свідоме рішення: no_tool_used НЕ ескалюємо.
# Користувач — інженер; питання про теорію VIO він оцінить сам, а бекенд і не був
# для нього джерелом. Ескалація тут смикала б чергового намарно.
# Прапорець при цьому лишається у відповіді — метрику видно, дію за нею не робимо.
# (У core/escalation.py ця причина єдина, що не гейтиться через ESCALATE_ON,
#  тому вимикаємо її тут, а не конфігом.)
NO_ESCALATE = {"no_tool_used"}


def _ref(result: dict) -> str:
    """Перший run_id, якого агент устиг торкнутись — щоб тікет був не порожній."""
    for step in result.get("trace", []):
        rid = step.get("input", {}).get("run_id")
        if rid:
            return rid
    return "—"


def finish(result: dict, query: str) -> dict:
    """Спільний хвіст для всіх модулів: рішення про ескалацію."""
    if escalation.decide(result, query) in NO_ESCALATE:
        result["escalated"] = False
        return result
    return escalation.apply(result, query, _ref(result))


def run(query: str) -> dict:
    result = run_agent(system=BASE_PROMPT, tools=tools_for(1), query=query)
    return finish(result, query)
