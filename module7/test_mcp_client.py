"""
М5 — швидка перевірка MCP-сервера без Inspector: підключаємось як клієнт
по stdio, перелічуємо інструменти і викликаємо get_order_status.

    python test_mcp_client.py
"""

import asyncio
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    raise SystemExit("Потрібно:  pip install 'mcp[cli]'")


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "tracking_mcp.py")],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Інструменти сервера:")
            for t in tools.tools:
                print(f"  · {t.name} — {t.description}")
            result = await session.call_tool("get_order_status",
                                             {"tracking": "EE123456789UA"})
            print("\nget_order_status(EE123456789UA) →")
            print(" ", result.content[0].text[:300])


if __name__ == "__main__":
    asyncio.run(main())
