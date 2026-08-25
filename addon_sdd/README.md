# addon_sdd — командний сетап Claude Code (SDD + спільна пам'ять)

Компанія-агностичний шаблон для розгортання **Claude Code як командної платформи**:
spec-driven development (OpenSpec), **спільна векторна пам'ять** на Neo4j, єдиний
конфіг у git і переносні субагенти.

Витягнуто з робочого продакшн-сетапу; усі дані конкретної компанії замінено на
плейсхолдери. Секретів усередині немає.

---

## Що це дає команді

| Можливість | Як реалізовано |
|---|---|
| **Пам'ять переживає сесії** | Рішення та конвенції осідають у спільному графі Neo4j; релевантні автоматично підмішуються в контекст |
| **Єдиний конфіг для всіх** | `shared/.claude/` (rules, агенти, команди) мержиться в `~/.claude` кожного розробника з git |
| **Spec-driven процес** | OpenSpec: proposal → implement → `validate --strict` → archive; специфікація їде з кодом в одному MR |
| **Крос-платформений онбординг** | Один скрипт для Windows / macOS / Linux, ~15 хв на розробника |
| **Секрети поза git** | `.env` + локальні налаштування; `.gitignore` блокує токени й ключі |

**Retrieval — гібридний RAG**: вектор (за змістом) + fulltext (за точними словами),
злиті через RRF, зі скоупінгом за проєктом. Це **не GraphRAG** — пошук іде по індексах,
а не обходом ребер. Neo4j обрано тому, що дає вектор + fulltext + фільтри в одному
рушії й лишає відкритим шлях до графового retrieval у майбутньому.

---

## Склад пакета

```
addon_sdd/
├── deploy/
│   ├── docker-compose.neo4j.yml   # спільний Neo4j (5-community, APOC, vector index)
│   ├── deploy.sh                  # доставка compose + застосування схеми на хост
│   ├── bootstrap.py               # онбординг розробника (Win/mac/Linux)
│   ├── bootstrap.cmd              # лаунчер для Windows (подвійний клік)
│   ├── bootstrap-dev.sh           # старий bash-варіант онбордингу (необов'язковий)
│   ├── verify_setup.sh            # перевірка: БД, модель, скіли
│   └── .env.example               # шаблон конфігу деплою (копіювати → .env)
├── memory-hooks/                  # стек пам'яті
│   ├── hooks/                     # log_event, auto_inject_memory, query, upsert,
│   │                              #   migrate, eval, bench, promote, graph_lint
│   ├── hooks-wrappers/            # repo-relative обгортки (крос-платформені)
│   ├── schema_v2.cypher           # constraint + 3 індекси (vector/fulltext/project)
│   └── pyproject.toml             # залежності; extra `[embeddings]` тягне модель
├── shared/.claude/                # командний baseline, мержиться в ~/.claude
│   ├── settings.json              # хуки + плагіни (без секретів)
│   ├── rules/team-conventions.md  # мова, гігієна секретів, правила SDD
│   ├── agents/memory-query.md     # субагент пошуку в пам'яті на вимогу
│   └── commands/                  # /openspec:proposal|apply|archive, /verify-setup
├── docs/
│   ├── SDD.md                     # spec-driven робочий процес
│   └── ONBOARDING.md              # гайд для нового розробника
└── .gitlab-ci.yml                 # скан секретів + лінт конфігу (опційно)
```

> **Не входить:** скіли та специфікації конкретних проєктів. Вони живуть у код-репо
> (`.claude/skills/`, `openspec/`), а не в цьому шаблоні.

---

## Плейсхолдери, які треба замінити

Знайдіть їх у репозиторії та проставте значення своєї компанії один раз:

| Плейсхолдер | Що означає | Приклад |
|---|---|---|
| `<NEO4J_HOST>` | Хост, де працює спільний Neo4j | `neo4j.corp.internal` |
| `<DEPLOY_USER>` | SSH-користувач для деплою на цей хост | `deployer` |
| `<GITLAB_HOST>` | Ваш Git-сервер | `git.corp.internal` |
| `<GROUP>` | Група/namespace для цього репо | `platform` |
| `<CORP_DOMAIN>` | Внутрішній домен (зона VPN) | `corp.internal` |
| `<TEAM_LANGUAGE>` | Мова доменних термінів у `team-conventions.md` | `українська` |
| `<ADDON_ROOT>` | Абсолютний шлях цього репо (в `agents/memory-query.md`) | `/opt/addon_sdd` |

```bash
# швидка перевірка, що нічого не лишилось
grep -rn "<NEO4J_HOST>\|<DEPLOY_USER>\|<GITLAB_HOST>\|<GROUP>\|<CORP_DOMAIN>\|<TEAM_LANGUAGE>\|<ADDON_ROOT>" .
```

---

## Розгортання

### Передумови

**На сервері:** Docker + Docker Compose, вільні порти `7474`/`7687`, ~2 ГБ RAM під
Neo4j (за замовчуванням heap 2 G + pagecache 1 G), мережева доступність із машин
розробників (VPN або внутрішня мережа).

**На машині розробника:** Claude Code, [`uv`](https://docs.astral.sh/uv/), git,
Python 3.11+, а на Windows — ще й **Git for Windows** (Claude Code запускає
shell-хуки через Git Bash).

### Крок 1 — покласти репо на свій Git-сервер

```bash
cd addon_sdd
git init && git add -A && git commit -m "chore: bootstrap team Claude Code setup"
git remote add origin https://<GITLAB_HOST>/<GROUP>/claude-platform.git
git push -u origin main
```

Якщо `main` захищений — запуште гілку й відкрийте MR; це нормальний шлях.

### Крок 2 — розгорнути спільний Neo4j

```bash
cp deploy/.env.example deploy/.env     # далі заповнити
$EDITOR deploy/.env                    # NEO4J_PASSWORD (сильний!), DEPLOY_HOST
chmod +x deploy/*.sh
cd deploy && ./deploy.sh
```

`deploy.sh` копіює compose-файл і схему на хост, піднімає контейнер, чекає на Bolt і
застосовує `schema_v2.cypher`. Скрипт **ідемпотентний** — безпечно запускати повторно.

Очікуваний результат — чотири індекси `ONLINE`:

```
memory_embedding    ONLINE     # VECTOR, cosine, 384 виміри (e5-small)
memory_fulltext     ONLINE     # FULLTEXT
memory_path_unique  ONLINE     # constraint унікальності
memory_project      ONLINE     # RANGE, скоупінг за проєктом
```

> **`deploy/.env` у .gitignore — ніколи не комітьте його.** Пароль Neo4j передавайте
> команді поза каналом (менеджер паролів), а не в чаті чи репозиторії.

### Крок 3 — онбординг кожного розробника

```bash
git clone https://<GITLAB_HOST>/<GROUP>/claude-platform.git
cd claude-platform
python deploy/bootstrap.py       # Windows: deploy\bootstrap.cmd (або py deploy\bootstrap.py)
```

Скрипт створює venv, завантажує embedding-модель (~120 МБ для e5-small), мержить
командний baseline у `~/.claude/settings.json`, прописує підключення до Neo4j і
перевіряє його. Пароль запитує один раз.

Далі **перезапустити Claude Code** (хуки та MCP читаються на старті) і перевірити:

```
/verify-setup
```

Усе має бути `OK`, зокрема `Vector DB reachable — 4/4 indexes ONLINE`.

### Крок 4 — під'єднати спільний конфіг до код-репозиторіїв

Baseline живе в `~/.claude` кожного розробника. Проєктні частини кладуться в самі
код-репо:

```bash
cp -r shared/.claude/{rules,agents,commands} <ваш-код-репо>/.claude/
```

Далі додайте **проєктні** rules, субагентів і `openspec/` — окремо в кожному репо; саме
там живуть архітектурні інваріанти та специфікації capability.

---

## Конфігурація

Задається через оточення (або в `~/.claude/settings.json`, секція `env`):

| Змінна | Типове значення | Призначення |
|---|---|---|
| `HOOKS_NEO4J_URI` | — | `bolt://<NEO4J_HOST>:7687` |
| `HOOKS_NEO4J_USER` | `neo4j` | користувач Neo4j |
| `HOOKS_NEO4J_PASSWORD` | — | спільний пароль команди |
| `AGENT_MEMORY_EMBED_MODEL` | `e5-small` | `e5-small` (384d) · `e5-large` (1024d) · `bge-m3` (1024d) |
| `AUTO_MEMORY_VSCORE_THRESHOLD` | залежить від моделі | поріг релевантності: `e5-small` 0.90 · `bge-m3` 0.76 · `e5-large` 0.82 |
| `AUTO_MEMORY_MAX_INJECT` | `3` | скільки пам'ятей підмішувати щонайбільше |
| `AUTO_MEMORY_EXCLUDE_PREFIXES` | `profile/` | префікси шляхів, які ніколи не інжектяться авто |

**Зміна embedding-моделі** — недеструктивна: `promote_model.py` пише вектори в
властивість та індекс, специфічні для розмірності, тож моделі співіснують і можна
відкотитися:

```bash
AGENT_MEMORY_EMBED_MODEL=bge-m3 python memory-hooks/hooks/promote_model.py
```

**Перекалібруйте поріг на своїх даних** — типові значення виміряні на невеликому
наборі й є орієнтовними:

```bash
python memory-hooks/hooks/eval_retrieval.py --thresholds 0.70 0.75 0.80 0.85 0.90
```

---

## Як рухається пам'ять

```
хук log_event    →  (:Session)-(:Event)      сира активність у графі
        ↓
дистиляція       →  (:Memory {path, content, project, embedding})
        ↓
на кожен промпт  →  гібридний пошук (вектор + fulltext, RRF, скоуп за проєктом)
        ↓
косинус ≥ поріг?    так → топ-N пам'ятей у контекст
                    ні  → тиша (контекст не витрачається)
```

Хук авто-інжекту **завжди повертає exit 0**: якщо Neo4j недоступний — тихо падає й
ніколи не блокує промпт. Для глибшого пошуку є субагент `memory-query`, що
викликається на вимогу.

**Два шляхи запису:** `upsert_memory.py` (записати факт явно) і фонова дистиляція
залогованих сесій у пам'ять. Починайте з явних upsert — граф корисний уже з першого
десятка фактів.

---

## Експлуатація

```bash
# стан усього сетапу
./deploy/verify_setup.sh

# гігієна графа: дублікати, відсутні project/embedding, застаріле, биті посилання
python memory-hooks/hooks/graph_lint.py

# додати пам'ять вручну
python memory-hooks/hooks/upsert_memory.py \
  --path project/<назва>/<slug> --content "…" --source manual

# пошук
python memory-hooks/hooks/query_memory_v2.py "ваше питання" --project <назва> --limit 5

# повторно застосувати схему / добити backfill після змін (ідемпотентно)
python memory-hooks/hooks/migrate_v2.py
```

**Бекапи:** граф — це знання команди. Поставте на хості регулярний
`neo4j-admin database dump` і зберігайте дампи поза цією машиною.

---

## Безпека

- **Секрети ніколи не в git.** `.gitignore` блокує `.env`, `**/settings.local.json`,
  `*secret*`, токени та ключі. Перевірка — `gitleaks detect` (опційна CI-задача це робить).
- **Neo4j Community має слабку автентифікацію й не має multi-DB** — тримайте хост
  **усередині мережі/VPN**, один спільний пароль, а розділення знань між командами
  забезпечуйте логічним скоупінгом `project`.
- **Ембединги рахуються локально** на кожній машині; у граф їде лише готовий вектор.
- Ротуйте пароль Neo4j (і будь-які Git-токени), якщо вони колись передавалися в чаті.

---

## Адаптація під свою компанію

1. Замініть усі плейсхолдери (таблиця вище).
2. Перепишіть `shared/.claude/rules/team-conventions.md` — мовна політика, правила щодо
   секретів, конвенції рев'ю саме вашої команди.
3. Визначте глибину SDD в `docs/SDD.md`: повний OpenSpec або лише правило «зміна
   поведінки їде разом зі своєю специфікацією».
4. Додайте **проєктних** субагентів у кожен код-репозиторій (explorer / builder /
   reviewer під ваш стек) — за зразком `shared/.claude/agents/memory-query.md`.
5. Опційно: увімкніть `.gitlab-ci.yml` (скан секретів + лінт конфігу), коли з'явиться runner.

---

## Вимоги

Neo4j 5.13+ (векторні індекси; перевірено на 5.26 Community) · Python 3.11+ · `uv` ·
Claude Code · Docker на хості · Git for Windows на Windows-машинах.
