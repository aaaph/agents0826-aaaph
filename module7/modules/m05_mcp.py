"""
МОДУЛЬ 5 — Протоколи інтеграції (MCP / A2A)

Додаємо: інструменти більше не зашиті в код агента, а беруться
з єдиного реєстру. Той самий інструмент — усім агентам одразу.

Тут відповідь агента майже не змінюється — і це правильно.
Цінність модуля не у відповіді, а в тому, скільки коштує
підключити наступний інструмент.
"""

if __name__ == "__main__":            # прямий запуск: корінь модуля у sys.path
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.agent import run_agent
from domain.backend import TOOL_SCHEMAS, CAPABILITIES
from domain.knowledge import as_context
from config import BASE_PROMPT

TITLE = "Протоколи інтеграції (MCP)"
ADDS  = "інструменти через єдиний реєстр замість жорсткої привʼязки"
FILES = ["modules/m05_mcp.py", "domain/backend.py"]


class ToolRegistry:
    """Спрощена модель MCP-реєстру: сервери реєструють свої інструменти."""

    def __init__(self):
        self._servers = {}

    def register(self, server: str, tool_names: list):
        self._servers[server] = tool_names
        return self

    def discover(self) -> list:
        return [TOOL_SCHEMAS[n] for names in self._servers.values() for n in names]

    def describe(self) -> dict:
        return {s: len(n) for s, n in self._servers.items()}


def build_registry() -> ToolRegistry:
    return (ToolRegistry()
            .register("mcp://tracking",  ["get_order_status"])
            .register("mcp://billing",   ["check_refund_eligibility"])
            .register("mcp://claims",    ["create_claim"]))


def run(query: str) -> dict:
    registry = build_registry()
    result = run_agent(
        system=BASE_PROMPT + "\n\nІнструменти надані через MCP-реєстр." + as_context(query),
        tools=registry.discover(),
        query=query,
    )
    result["registry"] = registry.describe()
    return result


if __name__ == "__main__":
    # те саме, що `python run.py 5`, лише без підсумкових метрик і вартості
    from config import USER_QUERY

    print(f"[{TITLE}] додає: {ADDS}\n")
    _r = run(USER_QUERY)
    _tools = [t["tool"] for t in _r.get("trace", [])]
    if _tools:
        print("інструменти:", " → ".join(_tools))
    print("\n" + _r["answer"])
    print("\nПовний прогін з метриками і вартістю:  python run.py 5")
