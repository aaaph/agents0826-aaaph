"""
М6 — PreToolUse-хуки: детермінований шар ПЕРЕД виконанням інструмента.

Модель помиляється — код ні. Хук перехоплює dispatch і відхиляє виклик,
який порушує правило, ще до того, як бекенд його побачить.

    python hooks.py     # офлайн-перевірка правил, без ключа
"""

import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from domain import backend

_TRACK_RE = re.compile(r"^[A-Z]{2}\d{9}[A-Z]{2}$")
_claims_this_session = {"count": 0}
MAX_CLAIMS_PER_SESSION = 3


def _rule_valid_tracking(name: str, args: dict) -> str | None:
    if name == "create_claim" and not _TRACK_RE.match(str(args.get("tracking", "")).strip().upper()):
        return "create_claim без валідного трек-номера"
    return None


def _rule_claims_limit(name: str, args: dict) -> str | None:
    if name == "create_claim" and _claims_this_session["count"] >= MAX_CLAIMS_PER_SESSION:
        return f"більше {MAX_CLAIMS_PER_SESSION} претензій за сесію"
    return None


PRE_TOOL_RULES = [_rule_valid_tracking, _rule_claims_limit]

_original_dispatch = backend.dispatch


def guarded_dispatch(name: str, args: dict) -> dict:
    for rule in PRE_TOOL_RULES:
        denied = rule(name, args)
        if denied:
            return {"error": f"hook_denied: {denied}",
                    "hint": "Виклик заблоковано політикою. Поясни клієнту або ескалюй."}
    result = _original_dispatch(name, args)
    if name == "create_claim" and "error" not in result:
        _claims_this_session["count"] += 1
    return result


def install():
    """run_agent імпортує dispatch при кожному виклику — підміна працює одразу."""
    backend.dispatch = guarded_dispatch


def uninstall():
    backend.dispatch = _original_dispatch


if __name__ == "__main__":
    install()
    print("── Офлайн-перевірка правил (бекенд фейковий, ключ не потрібен) ──")
    print("1. create_claim з кривим номером:")
    print("  ", backend.dispatch("create_claim", {"tracking": "не памʼятаю", "reason": "загубилась"}))
    print("2. чесний виклик проходить:")
    print("  ", backend.dispatch("create_claim", {"tracking": "EE123456789UA", "reason": "прострочення"}))
    print("3. ліміт претензій за сесію:")
    for _ in range(MAX_CLAIMS_PER_SESSION):
        backend.dispatch("create_claim", {"tracking": "EE123456789UA", "reason": "прострочення"})
    print("  ", backend.dispatch("create_claim", {"tracking": "EE123456789UA", "reason": "ще одна"}))
