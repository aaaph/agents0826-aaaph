"""
М7 — історія eval-прогонів: «до/після» однією командою.

Кожен прогін дописується в out/eval_history.jsonl з міткою варіанта —
скор сам по собі не значить нічого, значить дельта після зміни.

    python eval_history.py baseline        # прогнати й записати
    python eval_history.py new-prompt      # ще один варіант
    python eval_history.py --compare       # таблиця без прогону
"""

import json
import sys
import pathlib
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from config import OUT_DIR

HISTORY = OUT_DIR / "eval_history.jsonl"


def append(record: dict):
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def compare():
    if not HISTORY.exists():
        print("Історії ще немає — спершу: python eval_history.py baseline")
        return
    rows = [json.loads(line) for line in HISTORY.read_text(encoding="utf-8").splitlines()]
    print(f"{'коли':<17} {'варіант':<20} {'скор':<8} {'гейт':<6} {'зламані кейси'}")
    for r in rows:
        print(f"{r['at']:<17} {r['variant']:<20} {r['score']:<8} {r['gate']:<6} "
              f"{', '.join(r['failed']) or '—'}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--compare":
        compare()
        raise SystemExit

    variant = args[0]
    from modules import m07_evaluation as m07

    print(f"Прогін eval, варіант «{variant}»…")
    r = m07.run()
    append({
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "variant": variant,
        "score": r["score"],
        "pass_rate": r["pass_rate"],
        "gate": r["gate"],
        "failed": [c["id"] for c in r["cases"] if not c["pass"]],
    })
    print(f"  → {r['score']}  gate: {r['gate']}  (записано в {HISTORY.name})\n")
    compare()
