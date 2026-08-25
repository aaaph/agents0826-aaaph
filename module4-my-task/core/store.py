"""
Store — факти, що переживають окремі звернення.

Не історія діалогу: сюди їде не текст відповіді, а витяг із trace —
які прогони розглядались і які в них метрики. Витягує код, не модель.

Сесія (те, що з'ясували зараз) vs Store (що знаємо взагалі): тут другий.
Переживає процес — інакше два послідовні `run.py` нічого одне про одного
не знають. У проді замість файлу Redis чи Postgres із ключем по користувачу.
"""

import json

from config import OUT_DIR

_PATH = OUT_DIR / "store.json"
_LIMIT = 5  # більше не тримаємо: store — витяг, не архів


def _load() -> tuple[dict[str, dict], list[str]]:
    if not _PATH.exists():
        return {}, []
    try:
        data = json.loads(_PATH.read_text(encoding="utf-8"))
        return data.get("mem", {}), data.get("order", [])
    except (json.JSONDecodeError, OSError):
        return {}, []


def _save() -> None:
    _PATH.write_text(
        json.dumps({"mem": _MEM, "order": _ORDER}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


_MEM, _ORDER = _load()


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
    _save()


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
    """Новий діалог. У проді — новий ключ, а не очищення."""
    _MEM.clear()
    _ORDER.clear()
    _PATH.unlink(missing_ok=True)
