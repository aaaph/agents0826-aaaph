"""
МОДУЛЬ 4 — Оркестрація: маршрутизатор + профільні спеціалісти

Патерн за порадою choose_pattern.py — Supervisor. Дешева модель класифікує
запит, далі працює спеціаліст зі СВОЇМ набором інструментів і прав.

Другий патерн усередині: Evaluator–Optimizer на гілці ACTION — критик
перевіряє чернетку перед єдиною дією, що змінює стан.

Права різні не для краси:

  Store: витяг із trace (які прогони й метрики вже бачили) їде і в промпт
спеціаліста, і в промпт роутера — інакше «а чому так погано?» без контексту
класифікується як UNKNOWN.

  TRIAGE   від симптому вниз: логи → прогін → метрики. Без find_runs:
           якщо інженер прийшов зі скаргою, а не з ідентифікатором,
           пошук за алгоритмом лише спокушає вгадати не той прогін.
  METRICS  від ідентифікатора: find_runs і деталізація. Без search_logs —
           сканувати всі логи, коли run_id уже названо, це марна робота.
  POLICY   ЖОДНОГО інструмента. Питання про норму має відповідатись
           правилом, а не даними. З доступом до бекенду спеціаліст почав би
           підмішувати числа конкретних прогонів у відповідь про політику —
           і клієнт не відрізнив би норму від прикладу.
  ACTION   єдиний із request_rerun. Право змінювати стан ізольоване в одній
           гілці, і саме її прикриває критик.
  UNKNOWN  роутер не впорався → людина. Не «здогадатись», а ескалювати.
"""

from config import BASE_PROMPT
from core import store
from core.agent import ask, run_agent
from domain.backend import (
    ACTION,
    METRICS,
    POLICY,
    TOOL_SCHEMAS,
    TRIAGE,
    escalate_to_human,
)
from domain.knowledge_vec import as_context

from modules.m01_core import _ref, finish

TITLE = "Оркестрація"
ADDS = "маршрутизатор + профільні спеціалісти, право діяти"
FILES = ["modules/m04_orchestration.py"]

ROUTER = """Ти — маршрутизатор запитів до асистента бенчмарків SLAM/VIO.
Віднеси запит до однієї категорії й поверни ЛИШЕ її назву, без пояснень.

TRIAGE  — інженер описує симптом і не знає, який прогін дивитись:
          «щось зламалось», «де зривався трекінг», «що вночі впало».
METRICS — названо алгоритм, датасет, сиквенс або run_id: питання про числа.
POLICY  — питання про норму, поріг, методику чи політику команди.
          Про те, «як у нас заведено», а не про конкретний прогін.
ACTION  — просять щось зробити: переганяти, поставити в чергу.
HUMAN   — прямо просять людину або питання поза компетенцією асистента.

Якщо категорія неочевидна — поверни UNKNOWN. Вгадувати не треба."""

CRITIC = """Ти — критик. Перед тобою чернетка відповіді агента, який має право
поставити прогін на переобрахунок. Перевір ЛИШЕ два пункти:
1) чи названо конкретний run_id;
2) чи вказано причину переобрахунку з посиланням на правило або на дані.
Якщо обидва є — поверни OK. Якщо ні — поверни одним рядком, чого бракує."""

SPECIALISTS = {
    "TRIAGE": (TRIAGE, "Ти ведеш тріаж: від симптому до прогону й метрик."),
    "METRICS": (METRICS, "Ти відповідаєш на питання про числа конкретних прогонів."),
    "POLICY": (
        POLICY,
        (
            "Ти відповідаєш ЛИШЕ за правилами команди з контексту. Доступу до даних "
            "прогонів у тебе немає — якщо правило не покриває питання, скажи це прямо."
        ),
    ),
    "ACTION": (
        ACTION,
        (
            "Ти можеш поставити прогін на переобрахунок. Перед дією переконайся, "
            "що знаєш run_id і причину."
        ),
    ),
}


def route(query: str) -> str:
    verdict = ask(ROUTER + store.recall(), query, max_tokens=10).strip().upper()
    return verdict if verdict in {*SPECIALISTS, "HUMAN"} else "UNKNOWN"


def run(query: str) -> dict:
    kind = route(query)

    if kind in ("HUMAN", "UNKNOWN"):
        reason = (
            "клієнт просить людину"
            if kind == "HUMAN"
            else "маршрутизатор не розпізнав тип запиту"
        )
        return {
            "answer": f"Передаю інженеру — {reason}.",
            "outcome": "ok",
            "route": kind,
            "trace": [],
            "failures": [],
            "escalated": True,
            "escalation": {
                **escalate_to_human("—", reason),
                "reason": kind.lower(),
                "explain": reason,
            },
        }

    tool_names, role = SPECIALISTS[kind]
    result = run_agent(
        system=f"{BASE_PROMPT}\n\n{role}{as_context(query)}{store.recall()}",
        tools=[TOOL_SCHEMAS[n] for n in tool_names],
        query=query,
    )
    result["route"] = kind
    store.remember(result)

    # другий патерн: критик прикриває єдину гілку, що змінює стан
    if kind == "ACTION" and result.get("outcome") == "ok":
        verdict = ask(CRITIC, result["answer"], max_tokens=60).strip()
        result["critic"] = verdict
        if not verdict.upper().startswith("OK"):
            result["answer"] += f"\n\n[критик] {verdict}"
            result["escalated"] = True
            reason = "критик відхилив чернетку"
            result["escalation"] = {
                **escalate_to_human(_ref(result), reason),
                "reason": "critic_block",
                "explain": reason,
            }
            return result

    return finish(result, query)
