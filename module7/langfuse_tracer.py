"""
М7 — Tracer із m06 + експорт у Langfuse.

У коді m06 чесний коментар: «на продакшні тут OTEL-експортер».
Ось він: той самий збирач спанів, але кожен крок летить у Langfuse.
Без ключів Langfuse працює як звичайний Tracer і просто підказує, чого бракує.

    export LANGFUSE_PUBLIC_KEY=pk-... LANGFUSE_SECRET_KEY=sk-...
    python langfuse_tracer.py
"""

import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from modules import m06_security as m06

try:
    from langfuse import Langfuse
    _langfuse = Langfuse() if os.getenv("LANGFUSE_PUBLIC_KEY") else None
except ImportError:
    _langfuse = None


class LangfuseTracer(m06.Tracer):
    """Ті самі спани — плюс експорт назовні. Інтерфейс не змінився."""

    def __init__(self):
        super().__init__()
        self._trace = (_langfuse.trace(name="agentpro-run") if _langfuse else None)

    def __call__(self, step: dict):
        super().__call__(step)
        if self._trace:
            self._trace.span(
                name=step["tool"],
                input=step.get("input"),
                output=step.get("output"),
                level="ERROR" if "error" in step.get("output", {}) else "DEFAULT",
            )

    def summary(self) -> dict:
        s = super().summary()
        s["exported_to"] = "langfuse" if self._trace else "нікуди (немає ключів або пакета)"
        if _langfuse:
            _langfuse.flush()
        return s


if __name__ == "__main__":
    if _langfuse is None:
        print("Langfuse не активний: pip install langfuse + LANGFUSE_PUBLIC_KEY/SECRET_KEY.")
        print("Демо все одно працює — спани лишаться локальними.\n")

    from config import USER_QUERY

    # Підміняємо клас — m06.run() навіть не дізнається, що трейси тепер їдуть у хмару
    m06.Tracer = LangfuseTracer
    result = m06.run(USER_QUERY)
    t = result["tracing"]
    print(f"спанів: {t['spans']}  збоїв: {t['failed']}  експорт: {t['exported_to']}")
    for span in t["timeline"]:
        print(f"  {span['at_ms']:>6} ms  {span['tool']}  {'ok' if span['ok'] else 'FAIL'}")
