# План работ P2+P3: Улучшения FM Review Agents

> Создан: 17.02.2026
> Источник: docs/IMPROVEMENT_ROADMAP.md (полный контекст исследования)
> Статус: АКТИВНЫЙ

---

## Порядок выполнения

```
ШАГ 1: #7 Adaptive Thinking        [~30 мин]  ← НАЧАТЬ С ЭТОГО
ШАГ 2: #6 GitHub Actions           [~1-2 часа]
ШАГ 3: Дедупликация агентов        [~2-3 часа]
ШАГ 4: #5 Langfuse                 [~4-8 часов]
ШАГ 5: #8 Agent Teams (asyncio)    [~2-4 часа]
ШАГ 6: #9 Agent SDK Phase 1        [~2-4 часа, когда SDK стабилизируется]
```

---

## ШАГ 1: Adaptive Thinking (#7) — ~30 мин

**Цель:** Оптимизировать модели для каждого агента. Экономия ~41% на pipeline.

**Что делать:**

- [ ] 1.1. Изменить model в `.claude/agents/agent-2-simulator.md`: `opus` -> `sonnet`
- [ ] 1.2. Изменить model в `.claude/agents/agent-3-defender.md`: `opus` -> `sonnet`
- [ ] 1.3. Изменить model в `.claude/agents/agent-4-qa-tester.md`: `opus` -> `sonnet`
- [ ] 1.4. Изменить model в `.claude/agents/agent-7-publisher.md`: `opus` -> `sonnet`
- [ ] 1.5. Обновить IMPROVEMENT_ROADMAP.md: #7 статус -> DONE
- [ ] 1.6. Commit + push

**Итоговая конфигурация моделей:**

| Агент | Модель | Причина |
|-------|--------|---------|
| Agent 0 (Creator) | opus | Глубокое создание ФМ |
| Agent 1 (Architect) | opus | Сложный аудит |
| Agent 2 (Simulator) | **sonnet** | Структурированные сценарии |
| Agent 3 (Defender) | **sonnet** | Таксономическая классификация |
| Agent 4 (QA Tester) | **sonnet** | Шаблонная генерация тестов |
| Agent 5 (Tech Arch) | opus | Архитектура 1С:УТ |
| Agent 6 (Presenter) | sonnet | Уже оптимизирован |
| Agent 7 (Publisher) | **sonnet** | CRUD-операции |
| Agent 8 (BPMN) | sonnet | Уже оптимизирован |

---

## ШАГ 2: GitHub Actions (#6) — ~1-2 часа

**Цель:** Автоматический PR review с проверкой против CLAUDE.md.

**Что делать:**

- [ ] 2.1. Добавить `ANTHROPIC_API_KEY` в GitHub Secrets
  - Settings -> Secrets and variables -> Actions -> New repository secret
  - Name: `ANTHROPIC_API_KEY`, Value: sk-ant-...

- [ ] 2.2. Создать `.github/workflows/claude.yml` с двумя job-ами:
  - `auto-review`: на каждый PR (paths: agents/**, scripts/**, docs/**, CLAUDE.md)
  - `interactive`: на `@claude` в комментариях

- [ ] 2.3. Настройки workflow:
  - Model: `claude-sonnet-4-6` (экономия)
  - Max turns: 10 (auto-review), 15 (interactive)
  - Timeout: 15 минут
  - Tools: inline comments + gh pr + Read

- [ ] 2.4. (Опционально) Создать `.github/CLAUDE-REVIEW.md` - сокращенную версию CLAUDE.md только для PR review (основной CLAUDE.md ~800 строк, дорого per invocation)

- [ ] 2.5. Тестирование: создать тестовый PR, проверить что ревью работает

- [ ] 2.6. Обновить IMPROVEMENT_ROADMAP.md: #6 статус -> DONE
- [ ] 2.7. Commit + push

**Оценка стоимости:** ~$20/месяц при ~5 PR/неделю (Sonnet)

---

## ШАГ 3: Дедупликация агентов — ~2-3 часа

**Цель:** Убрать ~1100 строк дублей из 9 файлов агентов.

**Что делать:**

- [ ] 3.1. Инвентаризация: список всех дублирующихся секций в каждом AGENT_*.md
  - СТРУКТУРА ПРОЕКТОВ
  - ПРАВИЛО ФОРМАТА ФМ
  - XHTML СТАНДАРТЫ
  - АВТОСОХРАНЕНИЕ
  - _summary.json
  - MCP ИНСТРУМЕНТЫ
  - ФОРМАТ ВОПРОСОВ

- [ ] 3.2. Проверить что каждая секция есть в COMMON_RULES.md (с номером правила)

- [ ] 3.3. Для каждого агента заменить дубли на:
  ```
  > См. COMMON_RULES.md, правило N — [название правила]
  ```

- [ ] 3.4. Убедиться что уникальные инструкции агентов СОХРАНЕНЫ

- [ ] 3.5. Тестирование: запустить Agent 1 /audit, проверить что работает

- [ ] 3.6. Commit + push

---

## ШАГ 4: Langfuse (#5) — ~4-8 часов

**Цель:** Self-hosted observability для мониторинга агентов.

**Предварительные требования:**
- Docker + Docker Compose на сервере
- 4 vCPU, 16 GB RAM, 100 GB storage
- Сетевой доступ к серверу для UI

**Что делать:**

- [ ] 4.1. Подготовить сервер:
  - Проверить Docker/Docker Compose
  - Определить URL для Langfuse (напр. langfuse.internal.ekf.su)

- [ ] 4.2. Создать `docker-compose.yml` для Langfuse v3:
  - 6 сервисов: web, worker, postgres, clickhouse, redis, minio
  - Сгенерировать секреты (ENCRYPTION_KEY, NEXTAUTH_SECRET, SALT)
  - Создать MinIO bucket "langfuse"

- [ ] 4.3. Запустить и проверить доступность:
  - `docker compose up -d`
  - Открыть UI, создать admin аккаунт
  - Создать API keys (pk-lf-..., sk-lf-...)

- [ ] 4.4. Создать hook скрипт `scripts/hooks/langfuse_hook.py`:
  - Парсинг транскрипта Claude Code
  - Отправка трейсов в Langfuse API
  - Группировка по session_id

- [ ] 4.5. Настроить Stop hook:
  - `.claude/settings.local.json`: env с LANGFUSE keys
  - `.claude/settings.json` (или `~/.claude/settings.json`): Stop hook

- [ ] 4.6. Тестирование:
  - Запустить агента, проверить что трейс появился в UI
  - Проверить метрики: токены, стоимость, латентность

- [ ] 4.7. (Опционально) Настроить dashboards:
  - Cost per agent
  - Pipeline total cost
  - Latency per agent

- [ ] 4.8. Обновить IMPROVEMENT_ROADMAP.md: #5 статус -> DONE
- [ ] 4.9. Commit + push

---

## ШАГ 5: Agent Teams / Parallel Pipeline (#8) — ~2-4 часа

**Цель:** Параллельный запуск Agent 1+2+4 в pipeline.

**Что делать:**

- [ ] 5.1. Рефакторинг `scripts/run_agent.py`:
  - Добавить `asyncio.create_subprocess_exec()` вместо `subprocess.run()`
  - Определить stages:
    - Stage 1 (parallel): [Agent 1, Agent 2, Agent 4]
    - Stage 2 (sequential): Agent 5
    - Stage 3 (sequential): Quality Gate
    - Stage 4 (sequential): Agent 7
    - Stage 5 (parallel): [Agent 8, Agent 6]

- [ ] 5.2. Добавить `--parallel` флаг к `--pipeline`:
  ```bash
  python3 scripts/run_agent.py --pipeline --parallel --project PROJECT_NAME
  ```
  Без `--parallel` - текущее последовательное поведение (обратная совместимость)

- [ ] 5.3. Добавить result merging:
  - Проверить _summary.json каждого агента после stage
  - При status=failed - остановить pipeline

- [ ] 5.4. Тестирование:
  - Запустить с --parallel, проверить что все 3 агента стартуют одновременно
  - Проверить что Stage 2 ждет завершения Stage 1
  - Проверить что нет конфликтов записи

- [ ] 5.5. Обновить IMPROVEMENT_ROADMAP.md: #8 статус -> DONE
- [ ] 5.6. Commit + push

---

## ШАГ 6: Agent SDK Phase 1 (#9) — ~2-4 часа

**Цель:** Заменить subprocess.run() на SDK query() в run_agent.py.

**Статус SDK:** Alpha v0.1.36. НЕ НАЧИНАТЬ пока SDK не выйдет в Beta.

**Когда начинать:** Следить за https://github.com/anthropics/claude-agent-sdk-python/releases

**Что делать (когда SDK готов):**

- [ ] 6.1. `pip install claude-agent-sdk`

- [ ] 6.2. Заменить subprocess.run() на query() в run_agent.py:
  ```python
  # Было:
  result = subprocess.run(["claude", "-p", prompt, ...])
  # Стало:
  async for msg in query(prompt=prompt, options=ClaudeAgentOptions(...)):
      ...
  ```

- [ ] 6.3. Добавить output_format с JSON Schema из schemas/agent-contracts.json:
  - Гарантированный structured output вместо best-effort _summary.json

- [ ] 6.4. Тестирование: запустить pipeline, сравнить результаты

- [ ] 6.5. Phase 2 (позже): custom @tool для Confluence, PreToolUse hooks
- [ ] 6.6. Phase 3 (позже): полная оркестрация через AgentDefinition

---

## Отслеживание прогресса

| Шаг | Задача | Статус | Дата |
|-----|--------|--------|------|
| 1 | Adaptive Thinking (#7) | DONE (Agent 2,3,4,7->sonnet, no haiku) | 17.02.2026 |
| 2 | GitHub Actions (#6) | DONE (workflow + secret) | 17.02.2026 |
| 3 | Дедупликация агентов | DONE (9 файлов, ~800 строк) | 17.02.2026 |
| 4 | Langfuse (#5) | DONE (Cloud + hook + tracer) | 17.02.2026 |
| 5 | Agent Teams (#8) | DONE (--parallel, ThreadPoolExecutor) | 17.02.2026 |
| 6 | Agent SDK (#9) | BLOCKED (ждем Beta) | — |
