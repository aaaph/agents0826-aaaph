"""
М5 — справжній MCP-сервер поверх того самого бекенду.

Ті самі функції з domain/backend.py, які щойно викликав наш агент,
тепер доступні будь-якому MCP-клієнту: Claude Code, Inspector, Cursor.
«Написав інструмент раз — віддав усім» перестає бути гаслом.

Запуск (stdio, ключ Anthropic НЕ потрібен — це лише бекенд):

    python tracking_mcp.py

Перевірка руками, без агента:

    npx @modelcontextprotocol/inspector python tracking_mcp.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# MCP SDK 1.x називав це FastMCP, у 2.0 — MCPServer; API той самий.
try:
    from mcp.server import MCPServer as _Server          # SDK >= 2.0
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as _Server  # SDK 1.x (як у колоді)
    except ImportError:
        raise SystemExit("Потрібен MCP SDK:  pip install 'mcp[cli]'")

from domain import backend

mcp = _Server("ukrpost-tracking")


@mcp.tool()
def get_order_status(tracking: str) -> dict:
    """Повертає статус відправлення за трек-номером, напр. EE123456789UA."""
    return backend.get_order_status(tracking)


@mcp.tool()
def check_refund_eligibility(tracking: str) -> dict:
    """Перевіряє право на повернення ВАРТОСТІ ДОСТАВКИ за трек-номером."""
    return backend.check_refund_eligibility(tracking)


@mcp.tool()
def create_claim(tracking: str, reason: str) -> dict:
    """Створює претензію за трек-номером і повертає її номер та SLA."""
    return backend.create_claim(tracking, reason)


if __name__ == "__main__":
    mcp.run()          # stdio — креденшли через env, OAuth для локального не потрібен
