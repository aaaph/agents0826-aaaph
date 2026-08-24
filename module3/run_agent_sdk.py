"""
М3 — той самий агент на Claude Agent SDK: третій спосіб.

Порівняйте з run_langgraph.py (маршрут у графі) і run_create_agent.py
(маршрут обирає модель): тут ви віддаєте SDK взагалі все — цикл,
інструменти, дозволи — і керуєте лише опціями та хуками.

Три сцени зі слайдів розділу Claude Agent SDK:
  1. ланцюжок інструментів — статус → право на повернення → відповідь;
  2. hook як бізнес-політика: повернення понад ліміт — лише через
     оператора; deny спрацьовує ДО виконання, це код, а не промпт;
  3. невідомий трек — агент чесно відмовляє, нічого не вигадує.

    pip install claude-agent-sdk       # Python 3.10+, Node не потрібен
    python run_agent_sdk.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import anyio

try:
    from claude_agent_sdk import (
        query, tool, create_sdk_mcp_server, ClaudeAgentOptions,
        HookMatcher, AssistantMessage, TextBlock, ToolUseBlock, ResultMessage,
    )
except ImportError:
    raise SystemExit("Потрібен SDK:  pip install claude-agent-sdk")

from config import USER_QUERY
from domain import backend

# ── наші інструменти = MCP-сервер прямо в цьому процесі ──────
@tool("get_order_status", "Статус відправлення за трек-номером, напр. EE123456789UA",
      {"tracking": str})
async def get_order_status(args):
    return {"content": [{"type": "text",
                         "text": str(backend.get_order_status(args["tracking"]))}]}


@tool("check_refund", "Право на повернення ВАРТОСТІ ДОСТАВКИ за трек-номером",
      {"tracking": str})
async def check_refund(args):
    return {"content": [{"type": "text",
                         "text": str(backend.check_refund_eligibility(args["tracking"]))}]}


@tool("create_refund", "Оформити повернення коштів клієнту",
      {"tracking": str, "amount_uah": int})
async def create_refund(args):
    return {"content": [{"type": "text",
        "text": f"{{'refund_id': 'RF-0001', 'amount_uah': {args['amount_uah']}, "
                f"'status': 'оформлено'}}"}]}


server = create_sdk_mcp_server(name="post", version="1.0.0",
                               tools=[get_order_status, check_refund,
                                      create_refund])

LIMIT_UAH = 1000                     # понад — лише через оператора


# ── hook: бізнес-політика кодом, а не проханням у промпті ─────
async def refund_policy(input_data, tool_use_id, context):
    amount = input_data.get("tool_input", {}).get("amount_uah", 0)
    verdict = "deny" if amount > LIMIT_UAH else "allow"
    print(f"  [hook] create_refund({amount} грн) → {verdict}")
    if amount > LIMIT_UAH:
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason":
                    f"{amount} грн понад ліміт {LIMIT_UAH}: "
                    "потрібне підтвердження оператора"}}
    return {}


async def run(title: str, prompt: str, opts: ClaudeAgentOptions) -> None:
    print(f"\n═══ {title} ═══")
    print(f"Запит: «{prompt}»")
    async for msg in query(prompt=prompt, options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, ToolUseBlock):
                    print(f"  tool → {b.name}({b.input})")
                elif isinstance(b, TextBlock) and b.text.strip():
                    print(f"  → {b.text.strip()[:350]}")
        elif isinstance(msg, ResultMessage):
            print(f"  [{msg.num_turns} турів · ${(msg.total_cost_usd or 0):.4f}]")


async def main() -> None:
    base = dict(
        system_prompt="Ти — підтримка поштового оператора. Українською, коротко, "
                      "лише за даними інструментів — нічого не вигадуй.",
        mcp_servers={"post": server},
        setting_sources=[],          # у проді ЗАВЖДИ: не тягнути налаштування з машини
        max_turns=6,                 # наш MAX_TURNS з М1 — одне поле
    )

    await run("Сцена 1 · ланцюжок інструментів",
              "Де посилка EE123456789UA і чи належить мені повернення "
              "за прострочення?",
              ClaudeAgentOptions(**base,
                  allowed_tools=["mcp__post__get_order_status",
                                 "mcp__post__check_refund"]))

    scene2 = dict(base, system_prompt=(
        "Ти — виконавчий шар бек-офісу. Рішення вже ухвалене людиною вище: "
        "виклич create_refund окремо на КОЖНУ суму із запиту, без власних "
        "перевірок — контроль лімітів робить система, не ти. Українською."))
    await run("Сцена 2 · hook: ліміт на повернення",
              "Погоджені повернення по EE123456789UA: 120 грн і 5000 грн. "
              "Оформи обидва.",
              ClaudeAgentOptions(**scene2,
                  allowed_tools=["mcp__post__create_refund"],
                  hooks={"PreToolUse": [HookMatcher(
                      matcher="mcp__post__create_refund",
                      hooks=[refund_policy])]}))

    await run("Сцена 3 · невідомий трек",
              "Де посилка XX000000000XX?",
              ClaudeAgentOptions(**base,
                  allowed_tools=["mcp__post__get_order_status",
                                 "mcp__post__check_refund"]))

    print("\nПуант сцени 2: 120 грн пройшло без людини, 5000 — зупинив hook, КОДОМ.")
    print("Цикл, дозволи і сесії ви не писали — лише інструменти й політику.")
    print("Ціна зручності: harness щоразу їде в контекст. Порівняйте вартість зі")
    print("run_create_agent.py — і вирішіть, що з цього потрібно вашій задачі.")


if __name__ == "__main__":
    anyio.run(main)
