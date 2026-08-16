# Модуль 3 — Фреймворки і Agent SDK

Продовження модуля 2. **Додається:** явні стани + чекпоінт — спершу руками,
потім те саме на LangGraph і langchain 1.x `create_agent`.

Право діяти ще НЕ з'явилось: `CAPABILITIES[3]` дає статус і перевірку
права (read-only). Претензія вперше буде оформлена на модулі 4 — і це
свідомо: фреймворк — про структуру, не про повноваження.

## Нове відносно модуля 2

- `modules/m03_framework.py` — стани VERIFY → DECIDE → CONFIRM + чекпоінт
  у `out/checkpoint.json`. Все — 50 рядків: фреймворк це не магія.
- `run_langgraph.py` — ті самі стани як вузли графа, checkpointer з
  коробки, `--pause` = interrupt після DECIDE + resume (готовий HITL).
- `run_create_agent.py` — фішки langchain 1.x: `create_agent`, `@tool`
  (type hints = схема, docstring = опис), middleware. Наш MAX_TURNS з М1
  виявляється штатним `ModelCallLimitMiddleware`.

## Запуск

```bash
pip install -r requirements.txt
python run.py 3                     # стани + чекпоінт руками
python run_langgraph.py --pause     # LangGraph: interrupt + resume
python run_create_agent.py          # create_agent + middleware
```

Живе демо відновлення: `Ctrl+C` посеред `run.py 3` → перезапуск з
`resume=True` у коді → продовжує з CONFIRM, а не з «Доброго дня».

## Нюанси заняття

- Чекпоінт зберігає стан, але не ідемпотентність — тема повернеться на М8.
- Фреймворк додає шари в стектрейс: дебаг вимагає трейсів (аргумент до М7).
- Deprecated-мінне поле LangChain: AgentExecutor / LLMChain /
  ConversationBufferMemory ще живі у старих туторіалах — не вчіть мертві API.

Лабораторна (з колоди): перенести свого агента з модуля 1 на другий стек.

**Далі (модуль 4):** три заняття поспіль ми відмовляємо клієнту.
Час дати агенту право діяти.
