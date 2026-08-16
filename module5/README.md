# Модуль 5 — Протоколи: MCP / A2A

Продовження модуля 4. **Додається:** інструменти більше не зашиті в код
агента — спершу симуляція реєстру, потім справжній MCP-сервер.
Відповідь агента не змінюється — і це головна теза: цінність не у
відповіді, а у вартості підключення наступного інструмента.

## Нове відносно модуля 4

- `modules/m05_mcp.py` — симуляція MCP-реєстру: сервери tracking / billing /
  claims реєструють свої інструменти.
- `tracking_mcp.py` — справжній MCP-сервер поверх того самого
  `domain/backend.py` (SDK 1.x = FastMCP, 2.0 = MCPServer — підтримуються
  обидва). Ключ Anthropic не потрібен: сервер — це лише бекенд.
- `test_mcp_client.py` — перевірка сервера stdio-клієнтом без Inspector.
- `agent_card.json` — A2A-візитівка TrackBot: вертикаль MCP (агент ↔
  інструменти) проти горизонталі A2A (агент ↔ агент).
- `poison_demo.py` — tool poisoning: псуємо лише description чесного
  інструмента → агент обіцяє клієнту неіснуючий бонус. Тизер модуля 6.

## Запуск

```bash
python run.py 5
python tracking_mcp.py                                   # сервер (stdio)
python test_mcp_client.py                                # клієнт до нього
npx @modelcontextprotocol/inspector python tracking_mcp.py
python poison_demo.py
```

Кульмінація заняття — той самий сервер у Claude Code:

```bash
claude mcp add ukrpost-tracking -- python tracking_mcp.py
```

## Продакшн-нотатки

- Локальний stdio — креденшли через env; remote — OAuth 2.1 + PKCE +
  resource indicators.
- Сторонні MCP-сервери = ваш agentic supply chain (OWASP ASI04):
  allowlist, пінінг версій, least privilege на кожен tool.

**Далі (модуль 6):** ми щойно самі змусили агента брехати через опис
інструмента. Тепер зробимо це по-справжньому — і навчимось захищатись.
