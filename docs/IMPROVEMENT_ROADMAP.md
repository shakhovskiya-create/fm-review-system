# Roadmap улучшений системы FM Review Agents

> Результаты исследования (февраль 2026). Актуализируется по мере выполнения.
> Последнее обновление: 17.02.2026 (полный ресерч P2+P3)

---

## Приоритетная матрица

| # | Технология | Зрелость | Effort | Приоритет | Статус |
|---|-----------|---------|--------|-----------|--------|
| 1 | mcp-atlassian (MCP-сервер Confluence) | Production | Low | P0 | DONE |
| 2 | Hooks (расширение PostToolUse валидации) | Production | Low | P0 | DONE |
| 3 | Confluence Agent Skill (mastering-confluence) | Beta | Low | P1 | SKIP (Cloud-only) |
| 4 | Episodic Memory (obra/episodic-memory) | Beta | Low | P1 | DONE |
| 5 | Langfuse (observability, self-hosted) | Production v3.153 | Medium | P2 | TODO |
| 6 | GitHub Actions (anthropics/claude-code-action) | Production v1.0.53 | Low | P2 | DONE |
| 7 | Adaptive Thinking/Effort (разные уровни по агентам) | Production | Low | P2 | DONE (частично) |
| 8 | Agent Teams (параллельная работа агентов) | Experimental | High | P3 | TODO |
| 9 | Agent SDK (Python, замена run_agent.py) | Alpha v0.1.36 | High | P3 | TODO |

---

## P0 - ВЫПОЛНЕНО (17.02.2026)

### 1. mcp-atlassian
- Установлен: `pip install mcp-atlassian`
- Настроен: `.mcp.json` (confluence URL, PAT, SSL)
- 11 MCP-инструментов доступны всем агентам
- Протоколы агентов обновлены (COMMON_RULES.md + все AGENT_*.md)
- Коммит: bb00614

### 2. Hooks
- `validate-xhtml-style.sh` (PostToolUse) - проверка XHTML стилей и AI-упоминаний
- `auto-save-context.sh` (Stop) - обновление timestamp в PROJECT_CONTEXT.md
- Коммит: 6fd61e6

---

## P1 - ВЫПОЛНЕНО (17.02.2026)

### 3. Confluence Agent Skill
- ПРОПУЩЕН: mastering-confluence-agent-skill поддерживает ТОЛЬКО Confluence Cloud
- Наш сервер (https://confluence.ekf.su) - on-premise Confluence Server
- Используем mcp-atlassian вместо этого

### 4. Episodic Memory
- Установлен как плагин Claude Code (`/plugin install episodic-memory@superpowers-marketplace`)
- Семантическая память между сессиями
- Локальные эмбеддинги (Transformers.js), SQLite + sqlite-vec
- Коммит: 0a7f336

---

## P2 - ДЕТАЛЬНЫЙ КОНТЕКСТ ИССЛЕДОВАНИЯ

### 5. Langfuse (observability)

**Текущая версия:** v3.153.0 (12.02.2026), Python SDK v3.14.1

**Архитектура v3 (6 компонентов):**

| Компонент | Назначение | Минимум RAM |
|-----------|-----------|-------------|
| Langfuse Web | UI + API сервер | 4 GB |
| Langfuse Worker | Асинхронная обработка событий | 4 GB |
| PostgreSQL 12+ | Транзакционная БД | 2 GB |
| ClickHouse | OLAP для трейсов/метрик | 4 GB |
| Redis/Valkey | Кеш + очередь | 1 GB |
| MinIO (S3) | Хранилище событий | 10 GB+ |

**Итого:** ~4 vCPU, 16 GB RAM, 100 GB storage

**Интеграция с Claude Code (3 подхода):**

1. **Stop Hook (рекомендуется)** - официальный подход
   - Hook в `~/.claude/settings.json` вызывает Python-скрипт после каждого ответа
   - Скрипт парсит транскрипт и отправляет трейсы в Langfuse
   - Opt-in per project: `TRACE_TO_LANGFUSE=true` в `.claude/settings.local.json`
   - Работает с `claude -p` (наш run_agent.py)

2. **claude-langfuse-monitor (npm)** - zero-instrumentation
   - `npm install -g claude-langfuse-monitor`
   - Мониторит `~/.claude/projects/**/*.jsonl` в реальном времени
   - Можно установить как системный сервис (LaunchAgent)

3. **doneyli/claude-code-langfuse-template** - community шаблон
   - Docker Compose + hook скрипты
   - Stateful parsing, инкрементальная обработка
   - Локальная очередь при недоступности Langfuse

**Метрики которые можно отслеживать:**
- Токены и стоимость per agent/session/pipeline
- Латентность per agent и per tool call
- Количество tool calls per agent
- Ошибки и отказы
- Общая стоимость pipeline run
- Автоматический расчет стоимости для Claude моделей (встроенный)

**Альтернативы:**

| Платформа | Self-hosted | Claude Code | Преимущество |
|-----------|------------|-------------|-------------|
| **Langfuse** | Да (OSS) | Stop Hook (офиц.) | Бесплатно, self-hosted |
| **LangSmith** | Нет (cloud) | Stop Hook (офиц.) | LangChain экосистема |
| **Helicone** | Да (Rust) | Proxy (ANTHROPIC_BASE_URL) | Gateway/балансировка |
| **Arize Phoenix** | Да (OSS) | OpenTelemetry | ML мониторинг |

**Решение:** Langfuse self-hosted + Stop Hook. Соответствует on-premise стратегии (как Confluence).

**Риски:**
- v3 значительно сложнее v2 (ClickHouse + Redis + MinIO)
- v2 больше не получает security updates
- Требует Docker инфраструктуру (сервер с 16 GB RAM)

---

### 6. GitHub Actions (claude-code-action)

**Текущая версия:** v1.0.53 (16.02.2026), 5.7k stars, MIT license

**Возможности:**
- Автоматический PR review (на каждый PR)
- Интерактивный ассистент (`@claude` в комментариях PR/issues)
- Code implementation (создание коммитов, push в ветки)
- Анализ CI/CD логов (с правами `actions: read`)
- Inline comments на конкретные строки кода
- Structured JSON outputs (`--json-schema`)
- Progress tracking с visual checkboxes

**CLAUDE.md поддержка:** Да! Автоматически читает CLAUDE.md из корня репозитория.

**MCP поддержка:** Да. Через `--mcp-config` можно подключить mcp-atlassian.

**Два режима работы (два job-а в одном workflow):**

1. **auto-review** - триггер: `pull_request` (opened, synchronize)
   - Автоматически ревьюит каждый PR
   - Промпт с FM-специфичным чеклистом
   - Model: Sonnet (дешевле, ~$0.50-2.00 за PR)

2. **interactive** - триггер: `@claude` в комментариях
   - Отвечает на вопросы по коду
   - Может вносить изменения и пушить коммиты
   - Model: Sonnet (до 15 turns)

**Конфигурация для нашей системы:**

```yaml
# .github/workflows/claude.yml
name: Claude Code
on:
  pull_request:
    types: [opened, synchronize, ready_for_review]
    paths: [agents/**, scripts/**, docs/**, CLAUDE.md]
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
```

**Контроль стоимости:**
- `--max-turns 10` (лимит итераций)
- `--model claude-sonnet-4-5-20250929` (дешевле Opus)
- `paths:` фильтр (только релевантные файлы)
- `timeout-minutes: 15` (лимит времени)
- Оценка: ~$20/месяц при ~5 PR/неделю

**Ограничения:**
- Не может approve PR (security restriction)
- Не может merge/rebase
- Один comment (обновляет, не создает новые)
- CLAUDE.md ~800 строк - увеличивает стоимость. Рассмотреть `.github/CLAUDE-REVIEW.md`

**Аутентификация:** `ANTHROPIC_API_KEY` в GitHub Secrets

---

### 7. Adaptive Thinking/Effort

**Текущее состояние агентов:**

| Агент | Текущая модель | Рекомендация | Обоснование |
|-------|---------------|-------------|-------------|
| Agent 0 (Creator) | opus | **opus** | Создание ФМ - глубокое понимание бизнес-процессов |
| Agent 1 (Architect) | opus | **opus** | Аудит - самая аналитически сложная задача |
| Agent 2 (Simulator) | opus | opus (пока) | Оставлен - требует глубокого анализа |
| Agent 3 (Defender) | opus | opus (пока) | Оставлен - построение аргументов |
| Agent 4 (QA Tester) | opus | **sonnet** DONE | Шаблонная генерация тестов |
| Agent 5 (Tech Arch) | opus | opus | Проектирование архитектуры 1С:УТ |
| Agent 6 (Presenter) | sonnet | sonnet | Уже оптимизирован |
| Agent 7 (Publisher) | opus | **sonnet** DONE | CRUD операции с Confluence |
| Agent 8 (BPMN) | sonnet | **sonnet** | Уже оптимизирован |

**Стоимость моделей (за 1M токенов):**

| Модель | Input | Output | Множитель vs Haiku |
|--------|-------|--------|-------------------|
| Haiku 4.5 | $1 | $5 | 1x |
| Sonnet 4.5 | $3 | $15 | 3x |
| Opus 4.6 | $5 | $25 | 5x |

**Экономия при оптимизации:**

| Конфигурация | Стоимость pipeline | Экономия |
|-------------|-------------------|----------|
| Текущая (7 Opus + 2 Sonnet) | ~$6.15 | Baseline |
| Рекомендуемая (3 Opus + 4 Sonnet + 1 Haiku) | ~$3.60 | **~41%** |

**Изменения (4 файла):**
- Agent 2: `model: opus` -> `model: sonnet`
- Agent 3: `model: opus` -> `model: sonnet`
- Agent 4: `model: opus` -> `model: sonnet`
- Agent 7: `model: opus` -> `model: haiku`

**Effort Level (дополнительно):**
- Opus 4.6 поддерживает adaptive thinking (автоматически решает глубину)
- Уровни: `max` | `high` (default) | `medium` | `low`
- Настройка: `CLAUDE_CODE_EFFORT_LEVEL=medium` в env
- Пока нет per-agent настройки effort (только session-level)
- Auto model selection (запрос #16620) - ещё НЕ реализован

**Риски при downgrade:**

| Агент | Риск | Митигация |
|-------|------|-----------|
| Agent 2 (opus->sonnet) | Низкий | Мониторить глубину сценариев |
| Agent 3 (opus->sonnet) | Низкий | Мониторить качество аргументов |
| Agent 4 (opus->sonnet) | Низкий | Мониторить покрытие edge cases |
| Agent 7 (opus->haiku) | Очень низкий | При ошибках XHTML - попробовать sonnet |

---

## P3 - ДЕТАЛЬНЫЙ КОНТЕКСТ ИССЛЕДОВАНИЯ

### 8. Agent Teams (параллельная работа)

**Три механизма параллелизации:**

**A) Subagents (Task tool) - Production ready:**
- До 10 параллельных subagents
- DAG зависимости (blockedBy)
- Background/foreground режимы
- Ограничения: нет вложенных subagents, MCP не работает в background

**B) Agent Teams - Experimental:**
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- Полностью независимые Claude Code сессии
- Shared task list + inter-agent messaging
- Разделение: lead (координатор) + teammates (работники)
- Ограничения: нет resumption, один team per session

**C) Asyncio в run_agent.py - Custom dev:**
- Заменить `subprocess.run()` на `asyncio.create_subprocess_exec()`
- Stages: `[1,2,4]` -> `[5]` -> `[QG]` -> `[7]` -> `[8,6]`
- Оценка: 2-4 часа разработки

**Оптимальная схема pipeline:**

```
PARALLEL STAGE 1:  [Agent 1] [Agent 2] [Agent 4]   (~10 min вместо ~30)
        |
        v (wait all)
SEQUENTIAL:        Agent 5 (читает результаты 1+2+4)
        |
        v
SEQUENTIAL:        Quality Gate
        |
        v
SEQUENTIAL:        Agent 7 (publish)
        |
        v
PARALLEL STAGE 2:  [Agent 8] [Agent 6]   (независимые)
```

**Ожидаемое ускорение:** ~40% (с ~50 мин до ~30 мин)

**Конфликты при параллельной работе:**
- Agents 1+2+4 все READ-ONLY (читают ФМ, пишут в свои директории) - конфликтов нет
- Только Agent 7 пишет в Confluence - по дизайну sequential
- Локальные записи в разные папки (AGENT_1_*/, AGENT_2_*/, AGENT_4_*/) - конфликтов нет
- `confluence_utils.py` уже имеет file locking - защита есть

**Рекомендация:** Начать с варианта C (asyncio в run_agent.py) - самый быстрый и контролируемый.

---

### 9. Agent SDK (Python)

**Текущий статус:** Alpha v0.1.36 (13.02.2026). Активная разработка, API может меняться.

**Ключевые возможности:**

| Фича | Поддержка | Детали |
|------|----------|--------|
| Tool use | Полная | Built-in: Read, Write, Edit, Bash, Glob, Grep |
| Custom tools | Полная | `@tool` декоратор + in-process MCP |
| Structured output | Полная | `output_format` с JSON Schema (гарантия на уровне генерации) |
| MCP серверы | Полная | stdio, SSE, HTTP, in-process |
| Sessions/Memory | Полная | `ClaudeSDKClient` для multi-turn |
| Hooks | Полная | Pre/PostToolUse, Stop |
| Subagents | Полная | `AgentDefinition` с model/tools per agent |
| Budget control | Полная | `max_budget_usd`, `max_turns` |
| CLAUDE.md | Частичная | Нужен `setting_sources=["project"]` |

**Сравнение с текущим подходом (run_agent.py + claude -p):**

| Аспект | Текущий (subprocess) | Agent SDK |
|--------|---------------------|-----------|
| Запуск | `subprocess.run(["claude", "-p", ...])` | `async for msg in query(...)` |
| Structured output | _summary.json (best-effort) | JSON Schema (гарантированный) |
| Error handling | Parse exit code + stderr | Python exceptions |
| Cost tracking | Parse JSON stdout | `message.total_cost_usd` |
| Custom tools | Нет | `@tool` декоратор |
| Multi-turn | Невозможно с `-p` | Session persistence |

**Что УЛУЧШИТСЯ при миграции:**
1. Гарантированный structured output (вместо _summary.json best-effort)
2. In-process custom tools для Confluence (вместо bash wrappers)
3. PreToolUse hooks для governance (аудит записей в Confluence)
4. Надежный cost tracking ($X.XX per agent)
5. Budget control (max_budget_usd per agent)

**Что ПОТЕРЯЕМ / Риски:**
1. Alpha - API может ломаться между релизами
2. Async/await сложность vs простой subprocess.run()
3. Текущая система работает и проверена (audit logs, backups, locks)
4. Bash экосистема (orchestrate.sh, quality_gate.sh) придется переносить

**Рекомендация поэтапной миграции:**

| Фаза | Что | Когда |
|------|-----|-------|
| Phase 1 | Заменить subprocess.run() на query() в run_agent.py | Сейчас (low risk) |
| Phase 2 | Добавить output_format + custom @tool | Когда SDK в Beta |
| Phase 3 | Полная оркестрация через AgentDefinition | Когда SDK Stable |

**Альтернативы:**

| Фреймворк | Для нас | Причина |
|-----------|---------|---------|
| **Claude Agent SDK** | Лучший выбор | 100% Claude, MCP, CLAUDE.md, JSON Schema |
| LangChain/LangGraph | Нет | Heavy abstraction, не Claude-optimized |
| CrewAI | Нет | Не Claude-native, нет MCP |
| AutoGen (MS) | Нет | Microsoft ecosystem |

---

## Дополнительно: Дедупликация агентов

**Не из исследования, но выявлено при обновлении:**
- 9 файлов агентов содержат ~1100 строк дублей (22% от объема)
- Дубли: СТРУКТУРА ПРОЕКТОВ, ПРАВИЛО ФОРМАТА, XHTML, АВТОСОХРАНЕНИЕ, _summary.json
- Все уже есть в COMMON_RULES.md, но повторяются в каждом агенте
- Рефакторинг: заменить дубли на ссылки "см. COMMON_RULES.md правило N"
- Приоритет: после P2 #7, перед P3

---

## Рекомендуемый порядок реализации

```
ПРИОРИТЕТ 1 (быстро, Low effort):
  #7 Adaptive Thinking    → 30 мин, 4 файла, экономия ~41% на pipeline
  #6 GitHub Actions        → 1-2 часа, 1 файл workflow + secret

ПРИОРИТЕТ 2 (средний effort):
  Дедупликация агентов     → 2-3 часа, 9 файлов
  #5 Langfuse              → 4-8 часов, Docker + hook скрипт

ПРИОРИТЕТ 3 (высокий effort, будущее):
  #8 Agent Teams (asyncio) → 2-4 часа, рефакторинг run_agent.py
  #9 Agent SDK Phase 1     → 2-4 часа, замена subprocess на query()
  #9 Agent SDK Phase 2-3   → ждать стабильного SDK
```
