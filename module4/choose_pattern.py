"""
М4 — вибір коректного патерну архітектури під вашу задачу.

Два режими:

    python choose_pattern.py                     # майстер: 6 питань, без ключа
    python choose_pattern.py "опис задачі"       # LLM класифікує опис
    python choose_pattern.py "опис задачі" --demo  # + одразу запустити демо

Логіка та сама, що на слайді «Вибір правильної системи», і чесна:
найчастіша правильна відповідь — «вам не потрібен MAS». Правило 2026:
починайте з одного агента; мультиагентність — коли є чіткі межі
відповідальності, які існували в бізнесі й до всякого AI.
"""

import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

PATTERNS = {
    "single": {
        "назва": "Один агент (без MAS)",
        "коли": "немає незалежних підзадач і чітких меж відповідальності",
        "ціна": "найдешевше і найпростіше дебажити — тому це дефолт",
        "демо": "python run_create_agent.py",
    },
    "sequential": {
        "назва": "Послідовний (конвеєр)",
        "коли": "етапи строго один за одним, вивід попереднього = вхід наступного",
        "ціна": "латентність = сума етапів; помилка на початку псує все далі",
        "демо": "python run_langgraph.py        # VERIFY → DECIDE → CONFIRM",
    },
    "parallel": {
        "назва": "Паралельний + Агрегатор",
        "коли": "незалежні частини відомі наперед і їх склад не змінюється",
        "ціна": "N паралельних викликів замість одного; потрібен reducer",
        "демо": "python patterns_langgraph.py parallel",
    },
    "fanout": {
        "назва": "Orchestrator–Worker (Send)",
        "коли": "підзадачі стають відомі лише після аналізу самої задачі",
        "ціна": "≈15× токенів у великих системах (досвід Anthropic Research)",
        "демо": "python patterns_langgraph.py fanout",
    },
    "supervisor": {
        "назва": "Маршрутизатор (Supervisor)",
        "коли": "запити різних типів, кожен тип обробляє свій спеціаліст",
        "ціна": "+1 дешевий виклик на класифікацію; помилка роутера = не той спеціаліст",
        "демо": "python patterns_langgraph.py supervisor",
    },
    "loop": {
        "назва": "Петля (Evaluator–Optimizer)",
        "коли": "є обʼєктивний критерій якості, який можна перевірити",
        "ціна": "×N обертів; без ліміту — нескінченний цикл за ваші гроші",
        "демо": "python patterns_langgraph.py loop",
    },
    "network": {
        "назва": "Мережа",
        "коли": "агенти мусять передавати керування непередбачувано",
        "ціна": "маршрути не видно в коді графа — майже неможливо дебажити. "
                "У проді останній засіб: спершу спробуйте supervisor",
        "демо": "python patterns_langgraph.py network",
    },
}
ADDONS = {
    "hitl":  "незворотні дії → пауза перед дією: interrupt_before + підтвердження людини",
    "store": "памʼять між запусками (профіль клієнта, що вже зроблено) → Store "
             "(python patterns_langgraph.py store)",
}


def show(pattern: str, addons: list[str], why: str = "") -> None:
    p = PATTERNS[pattern]
    print(f"\n╭─ Рекомендація: {p['назва']}")
    if why:
        print(f"│  чому: {why}")
    print(f"│  коли доречно: {p['коли']}")
    print(f"│  ціна: {p['ціна']}")
    for a in addons:
        print(f"│  + {ADDONS[a]}")
    print(f"╰─ подивитись наживо: {p['демо']}")
    if pattern != "single":
        print("   (Правило 2026: якщо вагаєтесь — почніть з одного агента "
              "і розділяйте, лише коли межі стануть очевидні)")


# ── режим 1: детермінований майстер, працює офлайн ────────────
def wizard() -> tuple[str, list[str]]:
    def yes(q: str) -> bool:
        return input(f"  {q} [y/n] ").strip().lower().startswith(("y", "т", "1"))

    print("Шість питань про вашу задачу:\n")
    typed    = yes("Запити бувають РІЗНИХ типів, і кожен тип обробляється по-своєму?")
    parts    = yes("Чи можна розбити задачу на частини, незалежні одна від одної?")
    dynamic  = parts and yes("Ці частини видно лише ПІСЛЯ аналізу задачі (не наперед)?")
    stages   = not parts and yes("Чи є строгі етапи: вивід одного — вхід наступного?")
    quality  = yes("Чи є обʼєктивний критерій «добре/погано» для перевірки результату?")
    hitl     = yes("Чи є дії, які не можна відкотити (гроші, листи, видалення)?")
    memory   = yes("Чи треба памʼятати клієнта між окремими розмовами?")

    # порядок = пріоритет; перший збіг перемагає, решта — компонується всередині
    if typed:
        pattern = "supervisor"
    elif parts:
        pattern = "fanout" if dynamic else "parallel"
    elif stages:
        pattern = "sequential"
    elif quality:
        pattern = "loop"
    else:
        pattern = "single"                      # Правило 2026 — найчастіша відповідь

    addons = [a for a, on in (("hitl", hitl), ("store", memory)) if on]
    if quality and pattern not in ("loop", "single"):
        print("\n  · критерій якості є → всередині воркера доречна петля критика")
    print("\n  · мережу майстер не рекомендує ніколи: якщо здалося, що вона "
          "потрібна,\n    швидше за все бракує роутера або чітких меж (див. слайд "
          "«Патерни в проді»)")
    return pattern, addons


# ── режим 2: LLM класифікує вільний опис задачі ───────────────
RUBRIC = (
    "Ти — архітектор агентних систем. Обери ОДИН патерн під задачу:\n"
    "single — немає незалежних підзадач чи типів запитів (ДЕФОЛТ, якщо сумніваєшся)\n"
    "sequential — строгі етапи, вивід одного = вхід наступного\n"
    "parallel — незалежні частини, відомі наперед\n"
    "fanout — підзадачі стають відомі лише під час виконання\n"
    "supervisor — різні типи запитів, кожен тип — свій спеціаліст\n"
    "loop — є обʼєктивний критерій якості для перевірки\n"
    "network — не обирай: замість нього supervisor\n"
    "Додатки (0..2): hitl — є незворотні дії; store — памʼять клієнта між розмовами.\n"
    "Формат відповіді, рівно три рядки:\n"
    "PATTERN: <імʼя>\nADDONS: <через кому або ->\nWHY: <одне речення українською>"
)


def classify(task: str) -> tuple[str, list[str], str]:
    from core.agent import ask
    raw = ask(RUBRIC, f"Задача: {task}", max_tokens=150)
    pattern, addons, why = "single", [], ""
    for line in raw.splitlines():
        up = line.upper()
        if up.startswith("PATTERN:"):
            name = line.split(":", 1)[1].strip().lower()
            pattern = name if name in PATTERNS else "single"
        elif up.startswith("ADDONS:"):
            addons = [a.strip().lower() for a in line.split(":", 1)[1].split(",")
                      if a.strip().lower() in ADDONS]
        elif up.startswith("WHY:"):
            why = line.split(":", 1)[1].strip()
    if pattern == "network":                    # модель усе ж обрала — виправляємо
        pattern, why = "supervisor", why + " (network замінено: його не дебажити)"
    return pattern, addons, why


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--demo"]
    if args:
        pattern, addons, why = classify(" ".join(args))
        show(pattern, addons, why)
    else:
        pattern, addons = wizard()
        show(pattern, addons)

    if "--demo" in sys.argv:
        cmd = PATTERNS[pattern]["демо"].split("#")[0].split()
        print(f"\nЗапускаю: {' '.join(cmd)}\n")
        subprocess.run([sys.executable] + cmd[1:], check=False)
