"""
Фейковий бекенд поштового оператора. Детермінований.

Кожне відправлення — окремий сценарій, щоб eval мав що перевіряти:
  EE1 прострочене · EE2 втрачене · EE3 вручене · EE4 невірна адреса · EE5 у строку
"""

ORDERS = {
    # прострочене — класичний кейс повернення вартості доставки
    "EE123456789UA": {
        "tracking": "EE123456789UA", "status": "В дорозі",
        "last_scan": "12.07.2026, сортувальний центр Київ",
        "days_in_transit": 15, "declared_delivery_days": 5,
        "shipping_paid_uah": 120, "declared_value_uah": 2400,
        "service": "Експрес", "recipient_city": "Львів",
    },
    # втрачене — повернення доставки + компенсація вкладення
    "EE222333444UA": {
        "tracking": "EE222333444UA", "status": "Розшук",
        "last_scan": "02.06.2026, митний пост Одеса",
        "days_in_transit": 55, "declared_delivery_days": 7,
        "shipping_paid_uah": 180, "declared_value_uah": 5000,
        "service": "Міжнародний", "recipient_city": "Дніпро",
    },
    # вручене вчасно — повернення не належить
    "EE555666777UA": {
        "tracking": "EE555666777UA", "status": "Вручено",
        "last_scan": "10.08.2026, відділення №7 Харків",
        "days_in_transit": 4, "declared_delivery_days": 5,
        "shipping_paid_uah": 90, "declared_value_uah": 800,
        "service": "Стандарт", "recipient_city": "Харків",
    },
    # невірна адреса — провина відправника, повернення не належить
    "EE888999000UA": {
        "tracking": "EE888999000UA", "status": "Повернення відправнику",
        "last_scan": "08.08.2026, відділення №3 Полтава",
        "days_in_transit": 12, "declared_delivery_days": 5,
        "shipping_paid_uah": 110, "declared_value_uah": 1500,
        "service": "Стандарт", "recipient_city": "Полтава",
        "return_reason": "невірна адреса, вказана відправником",
    },
    # у межах строку — ще рано щось вимагати
    "EE111222333UA": {
        "tracking": "EE111222333UA", "status": "В дорозі",
        "last_scan": "15.08.2026, сортувальний центр Львів",
        "days_in_transit": 3, "declared_delivery_days": 5,
        "shipping_paid_uah": 100, "declared_value_uah": 1200,
        "service": "Стандарт", "recipient_city": "Ужгород",
    },
}

_claims = {}


# ── інструменти ───────────────────────────────────────────────
def get_order_status(tracking: str) -> dict:
    o = ORDERS.get(tracking.strip().upper())
    if not o:
        return {"error": "not_found", "tracking": tracking,
                "hint": "Перевірте номер або уточніть у відправника."}
    return {k: o[k] for k in
            ("tracking", "status", "last_scan", "days_in_transit",
             "declared_delivery_days", "service", "recipient_city")}


def check_refund_eligibility(tracking: str) -> dict:
    o = ORDERS.get(tracking.strip().upper())
    if not o:
        return {"error": "not_found", "tracking": tracking}

    overdue = o["days_in_transit"] - o["declared_delivery_days"]

    if o["status"] == "Повернення відправнику":
        return {"eligible": False, "reason": "return_sender",
                "rule": "Правило 4.7. Якщо відправлення повернуто через невірну адресу, "
                        "вказану відправником, вартість доставки не повертається.",
                "details": o.get("return_reason")}

    if o["status"] == "Вручено" and overdue < 5:
        return {"eligible": False, "reason": "delivered_on_time", "overdue_days": overdue,
                "rule": "Правило 4.2. Повернення — лише при простроченні від 5 днів."}

    if overdue < 5:
        return {"eligible": False, "reason": "within_term", "overdue_days": max(overdue, 0),
                "days_left": max(o["declared_delivery_days"] - o["days_in_transit"], 0),
                "rule": "Правило 4.2. Строк доставки ще не вичерпано."}

    return {"eligible": True, "overdue_days": overdue,
            "refundable_amount_uah": o["shipping_paid_uah"],
            "rule": "Правило 4.2. Прострочення від 5 днів — повертається вартість доставки. "
                    "Вартість вкладення не повертається."}


def check_compensation(tracking: str) -> dict:
    """Компенсація за вкладення — лише для втрачених після розшуку."""
    o = ORDERS.get(tracking.strip().upper())
    if not o:
        return {"error": "not_found", "tracking": tracking}
    if o["status"] != "Розшук":
        return {"eligible": False, "reason": "not_lost",
                "rule": "Правило 7.3. Компенсація за вкладення — лише після розшуку."}
    return {"eligible": True, "max_amount_uah": o["declared_value_uah"],
            "rule": "Правило 7.3. Компенсація в межах оголошеної цінності "
                    "після завершення розшуку."}


def create_claim(tracking: str, reason: str) -> dict:
    if tracking.strip().upper() not in ORDERS:
        return {"error": "not_found", "tracking": tracking}
    cid = f"CLM-{len(_claims) + 1:05d}"
    _claims[cid] = {"tracking": tracking, "reason": reason, "status": "Прийнято"}
    return {"claim_id": cid, "status": "Прийнято", "sla_days": 10}


def escalate_to_human(tracking: str, reason: str) -> dict:
    """Передати звернення оператору. Викликається, коли агент не може закрити сам."""
    return {"escalated": True, "queue": "support-l2",
            "ticket": f"ESC-{abs(hash(tracking)) % 90000 + 10000}",
            "reason": reason, "eta_minutes": 15}


IMPL = {
    "get_order_status": get_order_status,
    "check_refund_eligibility": check_refund_eligibility,
    "check_compensation": check_compensation,
    "create_claim": create_claim,
    "escalate_to_human": escalate_to_human,
}


def dispatch(name: str, args: dict) -> dict:
    fn = IMPL.get(name)
    if not fn:
        return {"error": f"unknown_tool:{name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"bad_args: {e}"}


# ── схеми ─────────────────────────────────────────────────────
def _schema(name, desc, props, required):
    return {"name": name, "description": desc,
            "input_schema": {"type": "object", "properties": props, "required": required}}


_TRACK = {"tracking": {"type": "string", "description": "Трек-номер, напр. EE123456789UA"}}

TOOL_SCHEMAS = {
    "get_order_status": _schema(
        "get_order_status",
        "Повертає статус відправлення за трек-номером.", _TRACK, ["tracking"]),
    "check_refund_eligibility": _schema(
        "check_refund_eligibility",
        "Перевіряє право на повернення ВАРТОСТІ ДОСТАВКИ.", _TRACK, ["tracking"]),
    "check_compensation": _schema(
        "check_compensation",
        "Перевіряє право на компенсацію за ВКЛАДЕННЯ (лише для втрачених).",
        _TRACK, ["tracking"]),
    "create_claim": _schema(
        "create_claim", "Створює претензію і повертає її номер.",
        {**_TRACK, "reason": {"type": "string", "description": "Причина звернення"}},
        ["tracking", "reason"]),
    "escalate_to_human": _schema(
        "escalate_to_human",
        "Передає звернення оператору. Використовуй, якщо не можеш вирішити сам "
        "або клієнт прямо просить людину.",
        {**_TRACK, "reason": {"type": "string", "description": "Чому потрібна людина"}},
        ["tracking", "reason"]),
}

BASIC = ["get_order_status"]
FULL  = ["get_order_status", "check_refund_eligibility", "check_compensation",
         "create_claim", "escalate_to_human"]

READ = ["get_order_status", "check_refund_eligibility"]

# 1–2: тільки подивитись · 3: дізнатись право (фреймворк, ще без дій)
# 4+: право діяти — з оркестрації з'являється create_claim
CAPABILITIES = {1: BASIC, 2: BASIC, 3: READ, 4: FULL, 5: FULL,
                6: FULL, 7: FULL, 8: FULL, 9: FULL}


def tools_for(module: int) -> list:
    return [TOOL_SCHEMAS[n] for n in CAPABILITIES[module]]
