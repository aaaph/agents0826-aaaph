"""
МОДУЛЬ 8 — Хмарний продакшн

Додаємо: керований runtime, ідентичність агента, масштабування.

ГОЛОВНА ДУМКА МОДУЛЯ: логіка агента не змінюється.
Змінюється спосіб запуску й те, від чийого імені агент діє.
Тому цей файл лише обгортає модуль 6 — і це навмисно.
"""

if __name__ == "__main__":            # прямий запуск: корінь модуля у sys.path
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from modules import m06_security
from config import BASE_PROMPT

TITLE = "Хмарний продакшн"
ADDS  = "керований runtime, ідентичність агента, масштаб"
FILES = ["modules/m08_cloud.py"]

# Відповідність шарів керованим сервісам
CLOUD_MAPPING = {
    "Ядро + фреймворк":  ("AgentCore Runtime",        "Agent Engine Runtime"),
    "Шар знань":         ("Bedrock Knowledge Bases",  "Vertex AI Search"),
    "Інструменти / MCP": ("AgentCore Gateway",        "MCP на Cloud Run"),
    "Памʼять і сесії":   ("AgentCore Memory",         "Sessions + Memory Bank"),
    "Спостережуваність": ("CloudWatch + OTEL",        "Cloud Trace + OTEL"),
    "Оцінка якості":     ("AgentCore Evaluations",    "ADK eval framework"),
    "Ідентичність":      ("AgentCore Identity",       "IAM Agent Identity"),
}

DEPLOYMENT = {
    "runtime":  "managed",
    "identity": "agent-scoped, least privilege",
    "scaling":  "auto",
    "network":  "VPC / private endpoints",
}


def run(query: str) -> dict:
    # Та сама логіка, що й на модулі 6 — свідомо без змін.
    result = m06_security.run(query)
    result["deployment"] = DEPLOYMENT
    result["cloud_mapping"] = {k: {"aws": a, "gcp": g} for k, (a, g) in CLOUD_MAPPING.items()}
    result["note"] = "логіка не змінилась — змінився спосіб запуску"
    return result


if __name__ == "__main__":
    # те саме, що `python run.py 8`, лише без підсумкових метрик і вартості
    from config import USER_QUERY

    print(f"[{TITLE}] додає: {ADDS}\n")
    _r = run(USER_QUERY)
    _tools = [t["tool"] for t in _r.get("trace", [])]
    if _tools:
        print("інструменти:", " → ".join(_tools))
    print("\n" + _r["answer"])
    print("\nПовний прогін з метриками і вартістю:  python run.py 8")
