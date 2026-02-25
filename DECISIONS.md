# Журнал решений (ADR-lite)

> Append-only. Каждое значимое решение при аудите ФМ фиксируется здесь.
> Формат: проблема → варианты → выбор → последствия.

---

## D-001: Структура проектов вместо плоского списка ФМ

**Дата:** 27.01.2026
**Автор:** Lead Auditor
**Контекст:** При масштабировании системы на несколько ФМ одновременно плоская структура файлов создает путаницу.

**Варианты:**
1. Все ФМ в корне `/` с префиксами
2. Папка `projects/` с отдельной директорией на каждый проект

**Выбор:** Вариант 2 - `projects/PROJECT_NAME/` с PROJECT_CONTEXT.md, WORKPLAN.md, CHANGELOG.md внутри.

**Последствия:** Каждый проект изолирован. Агенты получают контекст из конкретной папки проекта. CLAUDE.md роутит по имени проекта.

---

## D-002: Self-improvement через .patches/ вместо правки агентов напрямую

**Дата:** 13.02.2026
**Автор:** Lead Auditor
**Контекст:** Агенты повторяют одни и те же ошибки при аудите разных ФМ.

**Варианты:**
1. Править промпты агентов вручную после каждой ошибки
2. Накапливать паттерны в `.patches/`, агенты читают перед работой, `/evolve` периодически обновляет промпты

**Выбор:** Вариант 2 - append-only `.patches/` + EVOLVE.md.

**Последствия:** Знания накапливаются без потери контекста. Промпты обновляются контролируемо через /evolve с подтверждением пользователя.

---

## D-003: Confluence как целевая платформа публикации

**Дата:** 28.01.2026
**Автор:** Lead Auditor
**Контекст:** Результаты аудита нужно доставлять бизнес-пользователям.

**Варианты:**
1. PDF отчеты
2. Confluence страницы с интерактивной навигацией
3. Notion

**Выбор:** Вариант 2 - Confluence (корпоративный стандарт EKF).

**Последствия:** Agent 7 (Publisher) реализует публикацию через Confluence API. Формат описан в docs/CONFLUENCE_TEMPLATE.md.

---

## D-004: Claude Code SDK для автономного запуска агентов

**Дата:** 14.02.2026
**Автор:** Lead Auditor
**Контекст:** Агенты запускались через shell-скрипты с ручным копированием промптов. Нет бюджетов, нет наблюдаемости, нет автоматического resume.

**Варианты:**
1. Bash-скрипты + `claude --print` (текущее)
2. Claude Code SDK (Python async) + Langfuse трейсинг
3. REST API напрямую (anthropic SDK)

**Выбор:** Вариант 2 - `scripts/run_agent.py` с Claude Code SDK.

**Последствия:** Per-agent бюджеты (`budget_usd`), таймауты, Langfuse-спаны на каждый агент, `--pipeline`/`--parallel`/`--resume` режимы. SDK управляет жизненным циклом сессий, передаёт `system_prompt` из протоколов агентов. Зависимость: `claude-code-sdk>=0.1`.

---

## D-005: Langfuse для observability пайплайна

**Дата:** 16.02.2026
**Автор:** Lead Auditor
**Контекст:** Нет видимости расхода токенов, длительности агентов, причин сбоев. Мониторинг — ручной `grep` по логам.

**Варианты:**
1. Prometheus + custom metrics
2. Langfuse (self-hosted v3, LLM-native observability)
3. Без observability (логи в файлах)

**Выбор:** Вариант 2 - Langfuse self-hosted (`infra/langfuse/`).

**Последствия:** Каждый pipeline run = Langfuse trace, каждый агент = generation span. Stop-хук `langfuse_tracer.py` завершает спан при окончании субагента. Cost breakdown по агентам через `scripts/cost-report.sh` и Telegram-бот (`scripts/tg-bot.py`). MCP-сервер Langfuse даёт агентам доступ к своим трейсам.

---

## D-006: File-based locks для Confluence операций

**Дата:** 10.02.2026
**Автор:** Lead Auditor
**Контекст:** Несколько агентов могут одновременно обновлять одну Confluence-страницу (race condition → потеря данных).

**Варианты:**
1. Confluence optimistic locking (version number only)
2. File-based `fcntl.flock()` + backup перед PUT
3. Распределённый lock (Redis/etcd)

**Выбор:** Вариант 2 - `ConfluenceLock` в `src/fm_review/confluence_utils.py`.

**Последствия:** Mutex через `fcntl.flock()` (LOCK_EX), таймаут 60с, auto-cleanup. Backup текущей версии перед каждым PUT — rollback при ошибке. Audit log каждой записи (FC-12B). Достаточно для single-host, не подходит для кластера (но у нас один хост).

---

## D-007: Infisical вместо plaintext .env

**Дата:** 20.02.2026
**Автор:** Lead Auditor
**Контекст:** 7+ production ключей (Confluence, GitHub, Langfuse, Anthropic) хранились в .env. Риск утечки при коммите.

**Варианты:**
1. `.env` + `.gitignore` (текущее)
2. Infisical (hosted, Universal Auth)
3. HashiCorp Vault
4. keyring (OS-level)

**Выбор:** Вариант 2 - Infisical hosted (`infisical.shakhoff.com`), Machine Identity `fm-review-pipeline`, Universal Auth (TTL 10 лет).

**Последствия:** Цепочка: Infisical → keyring → .env (graceful degradation). `scripts/load-secrets.sh` загружает секреты, `scripts/check-secrets.sh --verbose` верифицирует. MCP-серверы запускаются через wrapper-скрипты (`mcp-confluence.sh`, `mcp-github.sh`) с подгрузкой из Infisical. `.env` удалён из репозитория.

---

## D-008: Conditional pipeline stages для SE-агентов

**Дата:** 25.02.2026
**Автор:** Lead Auditor
**Контекст:** Агенты 9 (SE Go) и 10 (SE 1C) нужны только для проектов соответствующей платформы. Включение обоих в каждый pipeline — расход бюджета впустую.

**Варианты:**
1. Всегда включать оба, пропуск по условию в промпте
2. `CONDITIONAL_STAGES` в pipeline.json с автодетектом платформы
3. Ручной выбор через `--agents` флаг

**Выбор:** Вариант 2 - `CONDITIONAL_STAGES` с ключами `after` и `platform`.

**Последствия:** `_detect_platform()` читает PROJECT_CONTEXT.md, определяет "1c" или "go". `_inject_conditional()` вставляет агента после указанной стадии. Pipeline бюджет увеличен с $60 до $70 для покрытия одного conditional агента. Оба агента зарегистрированы в `AGENT_REGISTRY` (доступны через `--agent 9/10`).
