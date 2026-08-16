"""
М8 — SLO-звіт з даних, які курс уже виробляє. Офлайн, без ключа.

Чотири метрики зі слайдів AIOps — усі рахуються з out/responses.json
та out/eval_history.jsonl, нічого нового збирати не треба:

  p95 часу відповіді · task success rate · вартість на успішну задачу ·
  escalation rate

    python run.py && python eval_history.py baseline   # дані
    python slo.py                                      # звіт
"""

import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

ROOT = pathlib.Path(__file__).resolve().parent
RESPONSES = ROOT / "out" / "responses.json"
HISTORY = ROOT / "out" / "eval_history.jsonl"


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    return xs[min(len(xs) - 1, int(round(0.95 * len(xs))) - 1)]


def main():
    if not RESPONSES.exists():
        raise SystemExit("Немає out/responses.json — спершу: python run.py")
    runs = json.loads(RESPONSES.read_text(encoding="utf-8")).values()

    latencies = [r["elapsed_sec"] for r in runs if r.get("elapsed_sec")]
    costs = [r["cost"]["usd"] for r in runs if r.get("cost")]
    escalated = sum(1 for r in runs if r.get("escalated"))
    graded = sum(1 for r in runs if "escalated" in r)

    if HISTORY.exists():
        last = json.loads(HISTORY.read_text(encoding="utf-8").splitlines()[-1])
        success_rate, eval_src = last["pass_rate"], f"eval «{last['variant']}» від {last['at']}"
    else:
        m7 = next((r for r in runs if r.get("pass_rate") is not None), None)
        success_rate = m7["pass_rate"] if m7 else None
        eval_src = "модуль 7 з responses.json" if m7 else "немає — прожени run.py 7"

    avg_cost = sum(costs) / len(costs) if costs else 0.0

    print("SLO агента (дані вже в проєкті — нічого нового не збирали)")
    print("─" * 58)
    print(f"  p95 часу відповіді        {p95(latencies):>8.1f} с   (n={len(latencies)})")
    if success_rate is not None:
        print(f"  task success rate         {success_rate:>8.0%}   ({eval_src})")
        cps = avg_cost / success_rate if success_rate else 0.0
        print(f"  вартість / успішну задачу ${cps:>8.4f}   (а не за запит!)")
    else:
        print(f"  task success rate            —      ({eval_src})")
    if graded:
        print(f"  escalation rate           {escalated / graded:>8.0%}   ({escalated}/{graded} прогонів)")
    print("─" * 58)
    print("  Пороги, алерти і щотижневий контрольний датасет — і це вже AIOps.")


if __name__ == "__main__":
    main()
