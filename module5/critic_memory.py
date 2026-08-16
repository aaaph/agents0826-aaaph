"""
М4 — два шари поверх оркестрації (m03):

  1) критик (Evaluator–Optimizer): дешева модель перевіряє чернетку
     відповіді за правилами і ОДИН раз повертає на доопрацювання;
  2) сесійна пам'ять: профіль клієнта живе між запитами в out/session.json —
     на другому зверненні агент вже знає трек-номер без перепитувань.

    python critic_memory.py
    python critic_memory.py --reset      # забути клієнта
"""

import json
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from config import BASE_PROMPT, OUT_DIR, USER_QUERY
from core.agent import ask, ask_json, run_agent
from domain.backend import tools_for
from domain.knowledge import as_context

SESSION = OUT_DIR / "session.json"

CRITIC = (
    "Ти — критик відповідей служби підтримки. Порівняй відповідь із правилами. "
    'Поверни JSON: {"ok": bool, "remarks": "що виправити, коротко"}. '
    "ok=false лише якщо відповідь суперечить правилам або обіцяє зайве."
)


# ── сесійна пам'ять ───────────────────────────────────────────
def load_profile() -> dict:
    if SESSION.exists():
        return json.loads(SESSION.read_text(encoding="utf-8"))
    return {"trackings": [], "queries": 0}


def save_profile(p: dict):
    SESSION.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def remember(profile: dict, query: str):
    profile["queries"] += 1
    for t in re.findall(r"[A-Z]{2}\d{9}[A-Z]{2}", query.upper()):
        if t not in profile["trackings"]:
            profile["trackings"].append(t)


def memory_context(profile: dict) -> str:
    if not profile["trackings"]:
        return ""
    return (f"\n\nПам'ять про клієнта: звернень — {profile['queries']}, "
            f"його відправлення: {', '.join(profile['trackings'])}. "
            "Якщо клієнт не назвав трек-номер — використовуй відомий.")


# ── критик ────────────────────────────────────────────────────
def run_with_critic(query: str) -> dict:
    profile = load_profile()
    remember(profile, query)

    system = BASE_PROMPT + memory_context(profile) + as_context(query)
    result = run_agent(system=system, tools=tools_for(4), query=query)

    verdict = ask_json(
        CRITIC,
        f"Правила:{as_context(query)}\n\nВідповідь агента:\n{result['answer']}",
        fallback={"ok": True, "remarks": "не розпарсено"},
        fast=True,
    )
    result["critic"] = verdict

    if not verdict.get("ok"):
        result["draft"] = result["answer"]
        result["answer"] = ask(
            system + "\nВрахуй зауваження критика і дай виправлену відповідь.",
            f"Звернення: {query}\nЧернетка: {result['answer']}\n"
            f"Зауваження: {verdict['remarks']}",
            max_tokens=500, fast=False,
        )

    save_profile(profile)
    return result


if __name__ == "__main__":
    if "--reset" in sys.argv:
        SESSION.unlink(missing_ok=True)
        print("Пам'ять клієнта очищено.")
        raise SystemExit

    print("── Звернення 1 (з трек-номером) ────────────────────────────")
    r = run_with_critic(USER_QUERY)
    print(f"  критик: ok={r['critic'].get('ok')}  {r['critic'].get('remarks', '')}")
    if "draft" in r:
        print(f"  чернетку виправлено після зауважень")
    print(f"  → {r['answer'][:200]}\n")

    followup = "А претензію по ній можете оформити?"     # без трек-номера!
    print(f"── Звернення 2: «{followup}» ──")
    r = run_with_critic(followup)
    tools = [t["tool"] for t in r.get("trace", [])]
    print(f"  інструменти: {' → '.join(tools) if tools else '—'}")
    print(f"  → {r['answer'][:200]}")
    print("\n  Агент знайшов трек-номер у пам'яті сесії — без перепитувань.")
