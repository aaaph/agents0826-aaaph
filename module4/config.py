"""Конфігурація. Ключ береться з .env — у код нічого не зашивається."""

import os
import pathlib
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    raise SystemExit(
        "Не знайдено ANTHROPIC_API_KEY.\n"
        "  cp .env.example .env   і впишіть ключ у .env"
    )

# ── каскад моделей ────────────────────────────────────────────
# Дорога модель — тільки там, де потрібне міркування.
# Роутер, guardrail і judge роблять просту роботу — їм вистачає дешевої.
MODEL      = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")       # цикл агента
MODEL_FAST = os.getenv("ANTHROPIC_MODEL_FAST", "claude-haiku-4-5-20251001")  # допоміжні виклики

MAX_TOKENS = int(os.getenv("MAX_TOKENS", 1200))
MAX_TURNS  = int(os.getenv("MAX_TURNS", 6))

# ── пороги ескалації на людину ────────────────────────────────
ESCALATE_ON = {
    "guardrail_block":  True,   # відповідь не пройшла перевірку
    "turns_exhausted":  True,   # агент не вклався в MAX_TURNS
    "tool_error":       True,   # інструмент повернув помилку, яку агент не обійшов
    "user_asked":       True,   # клієнт прямо попросив людину
}

DATA_DIR = ROOT / "data"
OUT_DIR  = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)

# Наскрізний запит курсу. Один на всі девʼять модулів.
USER_QUERY = (
    "Посилка EE123456789UA не прийшла вже два тижні. "
    "Я хочу повернути гроші за доставку."
)

BASE_PROMPT = ("Ти — асистент підтримки поштового оператора. Відповідай стисло, українською, "
               "простим текстом без Markdown-таблиць та емодзі — це чат підтримки.")
