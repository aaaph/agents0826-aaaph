"""
М2 × М7 — Ragas: як агент відпрацьовує з РІЗНИМИ RAG.

Один датасет (6 питань з еталонами), три конфігурації агента:

  lexical        — static RAG, лексичний retriever (domain/knowledge.py)
  vector         — static RAG, ембединги (knowledge_vec.py)
  agentic-vector — retrieval як інструмент search_kb поверх векторного

Кожна конфігурація проганяється через агента, Ragas міряє:
  faithfulness      — чи відповідь спирається на видані правила
  answer_relevancy  — чи відповідає на питання (потребує ембедингів)
  context_recall    — чи retriever взагалі дістав потрібне правило
                      (ГОЛОВНА метрика порівняння retriever'ів)

Суддя Ragas — Anthropic (дешева модель з каскаду, OpenAI-ключ не потрібен);
ембединги — локальна multilingual-e5-small, як у knowledge_vec.
Вартість/час: 6 питань × 3 конфігурації × (агент + 3 метрики) — кілька хвилин.

    pip install "ragas~=0.2" datasets "langchain-anthropic~=0.3" sentence-transformers
    python ragas_compare.py
    python ragas_compare.py lexical vector   # тільки вибрані
"""

import sys
import pathlib
import warnings

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

try:
    from datasets import Dataset
    from ragas import evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.run_config import RunConfig
    from ragas.metrics import answer_relevancy, context_recall, faithfulness
    from langchain_anthropic import ChatAnthropic
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError as e:
    raise SystemExit(f"Бракує пакета ({e.name}):\n"
                     "  pip install -r requirements.txt")

from config import BASE_PROMPT, MODEL_FAST
from core.agent import run_agent
from domain import backend
from domain import knowledge as lex
from domain.backend import tools_for
import knowledge_vec as vec

# ── датасет: половина питань — «зручні», половина — перефрази-синоніми,
#    на яких лексичний retriever промахується ─────────────────────────
CASES = [
    {"question": "Посилка EE123456789UA не прийшла вже два тижні. "
                 "Я хочу повернути гроші за доставку.",
     "ground_truth": "За правилом 4.2 при простроченні від 5 днів повертається "
                     "вартість доставки — 120 грн. Вартість вкладення не повертається."},
    {"question": "Де зараз посилка EE123456789UA і скільки ще чекати?",
     "ground_truth": "Відправлення в дорозі, останнє сканування — сортувальний центр "
                     "Київ 12.07.2026. Заявлений строк 5 днів уже перевищено."},
    {"question": "Скільки чекати виплату після повернення?",
     "ground_truth": "За правилом 4.5 повернення здійснюється на той самий спосіб "
                     "оплати протягом 14 банківських днів."},
    # перефрази: «загубили» ≠ «втрачено», «відшкодування» ≠ «повернення»
    {"question": "Кур'єр загубив мій пакунок EE222333444UA, що мені виплатять?",
     "ground_truth": "Відправлення в розшуку. За правилом 7.3 після завершення розшуку "
                     "виплачується компенсація в межах оголошеної цінності 5000 грн, "
                     "а також повертається вартість доставки за правилом 4.2."},
    {"question": "Мою бандероль EE222333444UA загубили, хочу відшкодування "
                 "вартості товару всередині.",
     "ground_truth": "За правилом 7.3 компенсація за втрачене вкладення виплачується "
                     "в межах оголошеної цінності 5000 грн після завершення розшуку."},
    {"question": "Чи можу я отримати відшкодування за запізнілу доставку EE123456789UA?",
     "ground_truth": "Так, за правилом 4.2 прострочення від 5 днів дає право на "
                     "повернення вартості доставки 120 грн."},
]

EMPTY = "(база знань нічого не повернула)"


def _tool_facts(result: dict) -> list[str]:
    """Виводи інструментів — теж контекст, який бачив агент.

    Пастка оцінки агентних RAG: якщо давати Ragas лише правила з БЗ,
    faithfulness провалюється на фактах з бекенду (статус, дні, суми) —
    вони «не підтверджені контекстом», хоча агент їх не вигадав.
    """
    import json as _json
    return [f"Дані бекенду ({t['tool']}): "
            f"{_json.dumps(t['output'], ensure_ascii=False)}"
            for t in result.get("trace", []) if t["tool"] != "search_kb"]


# ── три конфігурації RAG ──────────────────────────────────────
def run_lexical(question: str) -> tuple[str, list]:
    contexts = lex.retrieve(question, 3)
    result = run_agent(system=BASE_PROMPT + lex.as_context(question),
                       tools=tools_for(2), query=question)
    return result["answer"], contexts + _tool_facts(result)


def run_vector(question: str) -> tuple[str, list]:
    contexts = vec.retrieve(question, 3)
    result = run_agent(system=BASE_PROMPT + vec.as_context(question),
                       tools=tools_for(2), query=question)
    return result["answer"], contexts + _tool_facts(result)


SEARCH_KB_SCHEMA = {
    "name": "search_kb",
    "description": "Шукає правила й тарифи в базі знань поштового оператора. "
                   "Викликай перед будь-яким твердженням про правила чи суми.",
    "input_schema": {"type": "object",
                     "properties": {"query": {"type": "string"}},
                     "required": ["query"]},
}


def run_agentic_vector(question: str) -> tuple[str, list]:
    backend.IMPL["search_kb"] = lambda query: {"rules": vec.retrieve(query, 3)}
    result = run_agent(
        system=BASE_PROMPT + " Правила бери ТІЛЬКИ з search_kb — не вигадуй.",
        tools=tools_for(2) + [SEARCH_KB_SCHEMA], query=question)
    contexts = [r for t in result["trace"] if t["tool"] == "search_kb"
                for r in t["output"].get("rules", [])]
    return result["answer"], contexts + _tool_facts(result)


VARIANTS = {
    "lexical": run_lexical,
    "vector": run_vector,
    "agentic-vector": run_agentic_vector,
}


# ── прогін і оцінка ───────────────────────────────────────────
def collect(runner) -> Dataset:
    rows = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    for case in CASES:
        answer, contexts = runner(case["question"])
        rows["question"].append(case["question"])
        rows["answer"].append(answer)
        rows["contexts"].append(list(dict.fromkeys(contexts)) or [EMPTY])
        rows["ground_truth"].append(case["ground_truth"])
        print(f"    · {case['question'][:55]}…  ({len(contexts)} правил у контексті)")
    return Dataset.from_dict(rows)


if __name__ == "__main__":
    wanted = [v for v in sys.argv[1:] if v in VARIANTS] or list(VARIANTS)

    # суддя — дешева модель з нашого ж каскаду; ембединги — локальні
    judge = LangchainLLMWrapper(ChatAnthropic(model=MODEL_FAST, temperature=0))
    emb = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-small"))
    metrics = [faithfulness, answer_relevancy, context_recall]
    run_cfg = RunConfig(max_workers=4)

    results = {}
    for name in wanted:
        print(f"\n=== Конфігурація: {name} ===")
        ds = collect(VARIANTS[name])
        print("  Ragas оцінює…")
        results[name] = evaluate(ds, metrics=metrics, llm=judge, embeddings=emb,
                                 run_config=run_cfg, show_progress=False).to_pandas()

    print("\n" + "═" * 66)
    print(f"{'конфігурація':<16} {'faithful.':>10} {'relevancy':>10} {'ctx_recall':>11}")
    for name, df in results.items():
        print(f"{name:<16} {df['faithfulness'].mean():>10.2f} "
              f"{df['answer_relevancy'].mean():>10.2f} "
              f"{df['context_recall'].mean():>11.2f}")

    print("\ncontext_recall по питаннях (де саме програє лексика):")
    print("  " + "".join(f"{n:>16}" for n in results))
    for i, case in enumerate(CASES):
        cells = "".join(f"{df['context_recall'][i]:>16.2f}" for df in results.values())
        print(f"  {cells}   {case['question'][:45]}…")

    print("\nЯк читати (типова картина живого прогону):")
    print("· на «зручних» питаннях конфігурації йдуть врівень; на перефразах")
    print("  context_recall лексики нижчий — retriever не дістав потрібне правило;")
    print("· agentic зазвичай виграє faithfulness: агент, що САМ шукав правила,")
    print("  частіше на них і спирається;")
    print("· розрив менший, ніж очікуєш: інструменти дублюють правила в полі rule —")
    print("  дублювання джерел маскує слабкий retriever (згадайте це на М7).")
    print("Пастка, яку ми вже з'їли: якщо давати Ragas лише правила з БЗ,")
    print("faithfulness падає до ~0.2 на фактах з бекенду — tool-виводи теж контекст.")
