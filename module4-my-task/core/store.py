"""
Store — факти, що переживають окремі звернення.

Не історія діалогу: сюди їде не текст відповіді, а витяг із trace —
які прогони розглядались і які в них метрики. Витягує код, не модель.

Сесія (те, що з'ясували зараз) vs Store (що знаємо взагалі): тут другий,
у пам'яті процесу. У проді — Redis або Postgres із ключем по користувачу.
"""

_MEM: dict[str, dict] = {}
_ORDER: list[str] = []
_LIMIT = 5  # більше не тримаємо: store — витяг, не архів


def remember(result: dict) -> None:
    """Складає в store run_id і метрики, які агент реально бачив."""
    for step in result.get("trace", []):
        rid = step.get("input", {}).get("run_id")
        if not rid:
            continue
        entry = _MEM.setdefault(rid, {})
        if rid not in _ORDER:
            _ORDER.append(rid)
        out = step.get("output", {})
        for key in ("ate_rmse_m", "sequence", "algorithm", "config"):
            if key in out:
                entry[key] = out[key]
        if out.get("error"):
            entry["error"] = out["error"]
    del _ORDER[:-_LIMIT]


def recall() -> str:
    """Один рядок для промпта. Порожньо — значить порожньо."""
    if not _ORDER:
        return ""
    parts = []
    for rid in _ORDER:
        e = _MEM[rid]
        bits = [rid]
        if e.get("sequence"):
            bits.append(e["sequence"])
        if e.get("ate_rmse_m") is not None:
            bits.append(f"ATE RMSE {e['ate_rmse_m']}")
        if e.get("error"):
            bits.append(e["error"])
        parts.append(" ".join(bits))
    return "\n\nРаніше в цій розмові розглядались: " + "; ".join(parts) + "."


def reset() -> None:
    _MEM.clear()
    _ORDER.clear()
