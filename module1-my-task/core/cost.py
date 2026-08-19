"""
Розрахунок вартості прогону.

Ціни — за мільйон токенів, станом на 2026-08. Правити тут, якщо змінились.
"""

PRICES = {
    "claude-sonnet-4-6":          {"in": 3.00, "out": 15.00},
    "claude-haiku-4-5-20251001":  {"in": 1.00, "out": 5.00},
}


def usd(by_model: dict) -> float:
    total = 0.0
    for model, u in by_model.items():
        p = PRICES.get(model)
        if not p:
            continue
        total += u["in"] / 1e6 * p["in"] + u["out"] / 1e6 * p["out"]
    return round(total, 6)


def breakdown(by_model: dict) -> list:
    rows = []
    for model, u in by_model.items():
        p = PRICES.get(model, {"in": 0, "out": 0})
        c = u["in"] / 1e6 * p["in"] + u["out"] / 1e6 * p["out"]
        rows.append({"model": model, "calls": u["calls"],
                     "in": u["in"], "out": u["out"], "usd": round(c, 6)})
    return sorted(rows, key=lambda r: -r["usd"])


def savings_vs_single_model(by_model: dict, expensive="claude-sonnet-4-6") -> dict:
    """Скільки коштував би той самий прогін, якби все йшло на дорогій моделі."""
    p = PRICES[expensive]
    all_in = sum(u["in"] for u in by_model.values())
    all_out = sum(u["out"] for u in by_model.values())
    single = all_in / 1e6 * p["in"] + all_out / 1e6 * p["out"]
    actual = usd(by_model)
    return {"actual_usd": actual, "single_model_usd": round(single, 6),
            "saved_pct": round((1 - actual / single) * 100, 1) if single else 0.0}
