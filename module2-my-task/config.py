"""Конфігурація. Ключ береться з .env — у код нічого не зашивається."""

import os
import pathlib

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    raise SystemExit(
        "Не знайдено ANTHROPIC_API_KEY.\n  cp .env.example .env   і впишіть ключ у .env"
    )

# ── каскад моделей ────────────────────────────────────────────
# Дорога модель — тільки там, де потрібне міркування.
# Роутер, guardrail і judge роблять просту роботу — їм вистачає дешевої.
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")  # цикл агента
MODEL_FAST = os.getenv(
    "ANTHROPIC_MODEL_FAST", "claude-haiku-4-5-20251001"
)  # допоміжні виклики

MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1200"))
MAX_TURNS = int(os.getenv("MAX_TURNS", "6"))

# Жорсткий ліміт вартості одного прогону, USD. 0 — без ліміту.
# Ліміт кроків не рятує від бюджету: одне віяло на 12 виконань уміщається
# в один крок і коштує стільки ж, скільки шість послідовних.
MAX_USD = float(os.getenv("MAX_USD", "0"))

# ── пороги ескалації на людину ────────────────────────────────
ESCALATE_ON = {
    "guardrail_block": True,  # відповідь не пройшла перевірку
    "turns_exhausted": True,  # агент не вклався в MAX_TURNS
    "tool_error": True,  # інструмент повернув помилку, яку агент не обійшов
    "user_asked": True,  # клієнт прямо попросив людину
}

DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)

# Наскрізний запит. Один на всі модулі.
USER_QUERY = (
    "Прогнав ORB-SLAM3 на EuRoC, здається точність просіла. Яка вийшла ATE на MH_01?"
)

BASE_PROMPT = (
    "Ти — асистент з бенчмарків/аналізу SLAM/VIO. Допомагаєш розібратись у результатах "
    "прогонів. Відповідай стисло, українською, простим текстом без Markdown-таблиць "
    "та емодзі."
    "Якщо запросили метрики, то поверни тільки метрики, без іншого тексту."
)
