"""
Ескалація на людину.

Агент, який не може закрити звернення, не має мовчки віддавати
невпевнену відповідь — він передає його оператору.
"""

from config import ESCALATE_ON
from domain.backend import escalate_to_human

REASONS = {
    "guardrail_block": "відповідь не пройшла перевірку безпеки",
    "turns_exhausted": "агент не вклався у ліміт кроків",
    "api_error":       "збій сервісу моделі",
    "tool_error":      "інструмент повернув помилку",
    "user_asked":      "клієнт попросив оператора",
    "no_tool_used":    "агент відповів без звернення до бекенду",
}

_ASK_HUMAN = ("оператор", "людин", "менеджер", "консультант", "зателефон", "подзвон")


def user_asked_for_human(query: str) -> bool:
    q = query.lower()
    return any(w in q for w in _ASK_HUMAN)


def decide(result: dict, query: str = "") -> str | None:
    """Повертає причину ескалації або None, якщо агент упорався сам."""
    if ESCALATE_ON.get("user_asked") and user_asked_for_human(query):
        return "user_asked"
    if result.get("outcome") == "api_error":
        return "api_error"
    if ESCALATE_ON.get("turns_exhausted") and result.get("outcome") == "turns_exhausted":
        return "turns_exhausted"
    if ESCALATE_ON.get("guardrail_block") and \
            result.get("guardrail", {}).get("verdict") == "block":
        return "guardrail_block"
    if ESCALATE_ON.get("tool_error") and result.get("failures"):
        # ескалюємо лише якщо агент так і не отримав жодної успішної відповіді
        if all(s.get("failed") for s in result.get("trace", [])):
            return "tool_error"
    if result.get("no_tool_used") and result.get("trace") == []:
        return "no_tool_used"
    return None


def apply(result: dict, query: str, tracking: str = "—") -> dict:
    """Додає до результату блок ескалації, якщо вона потрібна."""
    reason = decide(result, query)
    if not reason:
        result["escalated"] = False
        return result

    ticket = escalate_to_human(tracking, REASONS[reason])
    result["escalated"] = True
    result["escalation"] = {**ticket, "reason": reason, "explain": REASONS[reason]}
    result["answer"] = (
        f"Передаю звернення оператору — {REASONS[reason]}.\n"
        f"Номер: {ticket['ticket']}. Орієнтовний час відповіді — "
        f"{ticket['eta_minutes']} хвилин."
    )
    return result
