"""
М3 — той самий агент на Google ADK 2.0: четвертий спосіб.

Ті самі сцени, що в run_agent_sdk.py — порівнюйте один до одного:
  1. інструменти + callback-ліміт: 120 грн проходить, 5000 — скасовує КОД;
  2. sub_agents: координатор передає керування профільному агенту.

Моделі тут — Claude через LiteLLM (щоб не заводити другий ключ);
з GOOGLE_API_KEY можна замінити model=... на "gemini-3-flash".

    pip install "google-adk[extensions]"     # + litellm усередині
    python run_adk.py
"""

import asyncio
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

try:
    from google.adk.agents import LlmAgent
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.runners import InMemoryRunner
    from google.genai import types
except ImportError:
    raise SystemExit('Потрібен ADK:  pip install "google-adk[extensions]"')

from config import MODEL_FAST
from domain import backend

MODEL = lambda: LiteLlm(model=f"anthropic/{MODEL_FAST}")


# ── інструменти: звичайні функції, docstring читає модель ─────
def get_order_status(tracking: str) -> dict:
    """Статус відправлення за трек-номером, напр. EE123456789UA."""
    return backend.get_order_status(tracking)


def check_refund(tracking: str) -> dict:
    """Право на повернення вартості доставки за трек-номером."""
    return backend.check_refund_eligibility(tracking)


def create_refund(tracking: str, amount_uah: int) -> dict:
    """Оформити повернення коштів клієнту."""
    return {"refund_id": "RF-0001", "amount_uah": amount_uah, "status": "оформлено"}


LIMIT_UAH = 1000


def refund_policy(tool, args, tool_context):
    """before_tool_callback: понад ліміт — виклик скасовується ДО виконання."""
    if tool.name == "create_refund":
        amount = args.get("amount_uah", 0)
        verdict = "deny" if amount > LIMIT_UAH else "allow"
        print(f"  [callback] create_refund({amount} грн) → {verdict}")
        if amount > LIMIT_UAH:
            return {"error": f"{amount} грн понад ліміт {LIMIT_UAH}: "
                             "потрібне підтвердження оператора"}
    return None                       # None = пропустити виклик як є


async def run(title: str, agent: LlmAgent, prompt: str) -> None:
    print(f"\n═══ {title} ═══")
    print(f"Запит: «{prompt}»")
    runner = InMemoryRunner(agent=agent, app_name="post")
    session = await runner.session_service.create_session(app_name="post",
                                                          user_id="u1")
    msg = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for ev in runner.run_async(user_id="u1", session_id=session.id,
                                     new_message=msg):
        if ev.content and ev.content.parts:
            for part in ev.content.parts:
                if part.function_call:
                    print(f"  [{ev.author}] tool → {part.function_call.name}"
                          f"({dict(part.function_call.args)})")
                elif part.text and part.text.strip():
                    print(f"  [{ev.author}] → {part.text.strip()[:300]}")


async def main() -> None:
    # сцена 1: інструменти + callback-ліміт
    support = LlmAgent(
        name="support", model=MODEL(),
        instruction="Ти — виконавчий шар пошти. Рішення вже ухвалене людиною: "
                    "виклич create_refund на КОЖНУ суму із запиту, без власних "
                    "перевірок — ліміти контролює система. Українською, коротко.",
        tools=[get_order_status, create_refund],
        before_tool_callback=refund_policy,
    )
    await run("Сцена 1 · callback: ліміт на повернення", support,
              "Погоджені повернення по EE123456789UA: 120 грн і 5000 грн. "
              "Оформи обидва.")

    # сцена 2: sub_agents — делегування через transfer_to_agent
    billing = LlmAgent(
        name="billing", model=MODEL(),
        description="Питання грошей: повернення, компенсації, тарифи.",
        instruction="Ти — фінансовий спеціаліст пошти. Українською, коротко.",
        tools=[check_refund],
    )
    tech = LlmAgent(
        name="tech", model=MODEL(),
        description="Технічні питання: трекінг не працює, застосунок, сайт.",
        instruction="Ти — техпідтримка пошти. Українською, коротко.",
    )
    coordinator = LlmAgent(
        name="coordinator", model=MODEL(),
        instruction="Ти — координатор підтримки. Визнач тему звернення і "
                    "передай профільному агенту.",
        sub_agents=[billing, tech],
    )
    await run("Сцена 2 · sub_agents: координатор → спеціаліст", coordinator,
              "Чи належить мені повернення за прострочену доставку "
              "EE123456789UA?")

    print("\nПуант: ті самі механізми, що в Claude SDK, інші назви розеток:")
    print("hooks → callbacks, subagents → sub_agents, allowed_tools → tools.")
    print("Порівняйте цей файл із run_agent_sdk.py рядок до рядка.")


if __name__ == "__main__":
    asyncio.run(main())
