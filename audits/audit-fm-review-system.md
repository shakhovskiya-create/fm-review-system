# Глубокий аудит: fm-review-system

**Дата:** 2026-02-25
**Аудитор:** Claude Opus 4.6 (4 параллельных агента)
**Ветка:** `main` (коммит `e6e2938`)
**Охват:** 8 направлений, 76 файлов, 39 веб-источников
**Заменяет:** аудит 2026-02-20, реаудит 2026-02-24

---

## Сводка

| Показатель | Значение |
|-----------|----------|
| Находок всего | 59 актуальных (3C + 14H + 22M + 19L + 1I), 6 FIXED, 2 REMOVED |
| Файлов проверено | 76 |
| Веб-источников | 39 |
| Безопасность | 6.5/10 → **7.5/10** (после Sprint 1: S5, S6, S7, S14 fixed) |
| Архитектура | 7.5/10 |
| Best Practices (Claude Code) | 8.5/10 → **9.0/10** (после Sprint 1: P1, P3 fixed, P5 removed) |
| Доменная область | 8/10 (D6 removed) |
| Масштабируемость | 7/10 |
| Документация | 6.5/10 |
| **Зрелость** | **BETA → BETA+** (Sprint 1 done) |

---

## Часть 1: Безопасность

### CRITICAL-S1. Секреты в .env в открытом виде [IN PROGRESS]
**Файл:** `.env:1-17`
**Стандарт:** [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
**Риск:** Компрометация хоста = утечка всех ключей: Anthropic API, Confluence, GitHub, Langfuse, Telegram. Реальные ключи лежат в файле.
**Статус:** Infisical Universal Auth внедрён, load-secrets.sh приоритизирует Infisical. Осталось: удалить .env после полной верификации всех сервисов. Ротация токенов — не планируется.
**Рекомендация:** Удалить .env после проверки что все скрипты и MCP-серверы работают через Infisical.

### CRITICAL-S2. Credentials Machine Identity Infisical в открытом виде
**Файл:** `infra/infisical/.env.machine-identity:6-8`
**Стандарт:** [Infisical Best Practices](https://infisical.com/blog/secrets-management-best-practices)
**Риск:** CLIENT_ID + CLIENT_SECRET = "ключи от всего" для ВСЕХ секретов проекта (TTL 10 лет).
**Рекомендация:** Переместить в системный keyring. Снизить TTL с 10 лет до дней/недель.
**Статус:** Файл имеет 0600 + .gitignore. Миграция в keyring — запланирована (Спринт 2).

### CRITICAL-S3. Секреты self-hosted Infisical в открытом виде
**Файл:** `infra/infisical/.env.infisical:5-7`
**Стандарт:** [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
**Риск:** ENCRYPTION_KEY, AUTH_SECRET, POSTGRES_PASSWORD в plaintext. Утечка = расшифровка всех секретов в БД Infisical.
**Рекомендация:** Docker secrets или шифрованная ФС. Файл имеет 0600 + .gitignore, но остаётся риском.
**Статус:** Self-hosted Infisical — fallback. Основной — hosted (infisical.shakhoff.com).

### HIGH-S4. SSL-верификация отключена для Confluence API
**Файл:** `src/fm_review/confluence_utils.py:46-49`, `scripts/export_from_confluence.py:41-43`, `scripts/mcp-confluence.sh:12`
**Стандарт:** [OWASP A07](https://owasp.org/Top10/2025/)
**Риск:** MITM в корпоративной сети перехватывает токены Confluence. Есть TODO про CA-сертификат, но не исправлено.
**Рекомендация:** Установить корпоративный CA-сертификат, заменить CERT_NONE на `ctx.load_verify_locations(...)`.

### HIGH-S5. Shell-инъекция через heredoc [FIXED]
**Файл:** `scripts/confluence-restore.sh:111-118`
**Стандарт:** [OWASP Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
**Риск:** `${BACKUP_FILE}` подставляется в python3 -c строку. Одинарная кавычка в пути = выполнение кода.
**Исправлено:** Путь передаётся как `sys.argv[1]` вместо интерполяции. Коммит Sprint 1.

### HIGH-S6. GitHub Actions не привязаны к SHA-хешам [FIXED]
**Файл:** `.github/workflows/ci.yml:14-37`, `claude.yml:37-115`, `security-review.yml:24-30`
**Стандарт:** [GitHub Actions Hardening](https://www.wiz.io/blog/github-actions-security-guide) -- CVE-2025-30066 (tj-actions)
**Риск:** Теги можно перенаправить на вредоносный код. Атакующий крадёт ANTHROPIC_API_KEY.
**Исправлено:** Все actions пиннированы на SHA (checkout, setup-python, upload-artifact, claude-code-action). Коммит Sprint 1.

### HIGH-S7. MCP-пакеты без пиннинга версий (@latest) [FIXED]
**Файл:** `.mcp.json:26`
**Стандарт:** [OWASP A03 Supply Chain](https://owasp.org/Top10/2025/)
**Риск:** npx @latest автоматически тянет непроверенные версии. Скомпрометированный npm-пакет = произвольное выполнение кода.
**Исправлено:** Пиннированы: `@modelcontextprotocol/server-memory@2026.1.26`, `@playwright/mcp@0.0.68`, `agentation-mcp@1.2.0`. Коммит Sprint 1.

### MEDIUM-S8. Shell-скрипты без set -euo pipefail
**Файл:** `scripts/orchestrate.sh`, `quality_gate.sh`, `mcp-confluence.sh`, `load-secrets.sh`, `fm_version.sh`, `new_project.sh` + 6 лаунчеров агентов
**Стандарт:** [Bash Best Practices 2025](https://medium.com/@prasanna.a1.usage/best-practices-we-need-to-follow-in-bash-scripting-in-2025-cebcdf254768)
**Риск:** Скрипты продолжают работу после ошибок; неинициализированные переменные раскрываются в пустоту.
**Рекомендация:** Добавить `set -euo pipefail` во все, кроме load-secrets.sh (sourced).

### MEDIUM-S9. requirements.txt использует >= вместо == из pyproject.toml
**Файл:** `requirements.txt:4-8`, `pyproject.toml:7`
**Стандарт:** [Python Security (Snyk)](https://snyk.io/blog/python-security-best-practices-cheat-sheet/)
**Риск:** CI может установить непротестированные новые версии.
**Рекомендация:** Один источник правды: `pip install .` в CI, убрать requirements.txt.

### MEDIUM-S10. block-secrets.sh не ловит Confluence/Langfuse/Telegram токены
**Файл:** `.claude/hooks/block-secrets.sh:22`
**Стандарт:** [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
**Риск:** Агент может записать Langfuse-ключи (sk-lf-), Telegram-токены в файлы незамеченным.
**Рекомендация:** Добавить паттерны: Langfuse (sk-lf-|pk-lf-), Telegram (`\d{10}:AA[A-Za-z0-9_-]{33}`).

### MEDIUM-S11. quality_gate.sh: инъекция через sed
**Файл:** `scripts/quality_gate.sh:346-348`
**Стандарт:** [PortSwigger Command Injection](https://portswigger.net/web-security/os-command-injection)
**Риск:** --reason со специальными символами может повредить PROJECT_CONTEXT.md или JSONL-аудит.
**Рекомендация:** Использовать `jq` для JSON-экранирования вместо `sed 's/"/\\"/g'`.

### MEDIUM-S12. Telegram-бот без rate limiting
**Файл:** `scripts/tg-bot.py:115-118`
**Стандарт:** [OWASP API Security](https://owasp.org/API-Security/)
**Риск:** Утечка TELEGRAM_CHAT_ID позволяет спамить /report.
**Рекомендация:** Добавить лимит 10 отчётов/час.

### MEDIUM-S13. notify.sh строит JSON через printf+sed
**Файл:** `scripts/notify.sh:75-78`
**Стандарт:** [OWASP Injection](https://owasp.org/Top10/2025/)
**Риск:** Спецсимволы в MESSAGE ломают JSON-пейлоад.
**Рекомендация:** Использовать `jq` или `python3 -c "import json; ..."`.

### LOW-S14. security-review.yml: лишний id-token: write [FIXED]
**Файл:** `.github/workflows/security-review.yml:22`
**Исправлено:** `id-token: write` убран. Коммит Sprint 1.

### LOW-S15. cost-report.sh: данные API в python3 -c
**Файл:** `scripts/cost-report.sh:130-133`
**Рекомендация:** Валидировать числовые значения перед интерполяцией.

### LOW-S16. bandit B310 подавлен глобально
**Файл:** `pyproject.toml:26`
**Рекомендация:** Использовать per-line `# nosec B310`.

---

## Часть 2: Архитектура и код

### HIGH-A1. DRY: _get_page_id() продублирована
**Файл:** `scripts/publish_to_confluence.py:62`, `scripts/export_from_confluence.py:18`
**Стандарт:** [DRY Principle](https://realpython.com/ref/best-practices/project-layout/)
**Риск:** Баг-фикс в одной копии забудут в другой.
**Рекомендация:** Вынести в `src/fm_review/utils.py`.

### HIGH-A2. DRY: _make_ssl_context() продублирована
**Файл:** `src/fm_review/confluence_utils.py:32`, `scripts/export_from_confluence.py:38`
**Стандарт:** [DRY Principle](https://realpython.com/ref/best-practices/project-layout/)
**Рекомендация:** Импортировать из confluence_utils.py.

### HIGH-A3. run_agent.py -- 1213 строк, слишком большой
**Файл:** `scripts/run_agent.py:1-1213`
**Стандарт:** [Python Project Best Practices](https://dagster.io/blog/python-project-best-practices)
**Риск:** Высокая когнитивная нагрузка, сложно тестировать, конфликты при мёрже.
**Рекомендация:** Разбить: pipeline.py, tracer.py, injection.py, checkpoint.py, cli.py.

### HIGH-A4. publish_to_confluence.py: main() 297 строк -- God Function
**Файл:** `scripts/publish_to_confluence.py:320-616`
**Стандарт:** [Python Error Handling](https://www.kdnuggets.com/5-error-handling-patterns-in-python-beyond-try-except)
**Рекомендация:** Разделить на main_docx_import() и main_xhtml_update().

### MEDIUM-A5. Широкий except Exception в 4 местах
**Файл:** `src/fm_review/langfuse_tracer.py:301`, `scripts/run_agent.py:202`, `confluence_utils.py:142`, `tg-report.py:60`
**Стандарт:** [Python Exception Handling](https://blog.miguelgrinberg.com/post/the-ultimate-guide-to-error-handling-in-python)
**Рекомендация:** Логировать исключение в stderr перед подавлением.

### MEDIUM-A6. Проверка CONFLUENCE_TOKEN дублирована в 2 файлах
**Файл:** `src/fm_review/confluence_utils.py:431`, `scripts/publish_to_confluence.py:322`
**Рекомендация:** Использовать create_client_from_env() из confluence_utils.py.

### MEDIUM-A7. sys.path.insert(0, ...) для импортов
**Файл:** `scripts/publish_to_confluence.py:559`
**Стандарт:** [Modern Python Setup](https://albertsikkema.com/python/development/best-practices/2025/10/31/modern-python-project-setup.html)
**Рекомендация:** Использовать `pip install -e .` везде.

### MEDIUM-A8. Глобальное мутабельное состояние в export_from_confluence.py
**Файл:** `scripts/export_from_confluence.py:517-526`
**Рекомендация:** Передавать конфигурацию параметрами или через Config dataclass.

### MEDIUM-A9. Непоследовательные shebang-строки
**Файл:** 11 скриптов #!/bin/bash, 11 скриптов #!/usr/bin/env bash
**Стандарт:** [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)
**Рекомендация:** Стандартизировать на `#!/usr/bin/env bash`.

### LOW-A10. Нет type hints в функциях скриптов
**Файл:** `scripts/publish_to_confluence.py`, `scripts/export_from_confluence.py`
**Рекомендация:** Добавить type hints. Рассмотреть mypy в CI.

### LOW-A11. Только 1 файл использует logging; остальные print()
**Файл:** `scripts/tg-bot.py:24`
**Рекомендация:** Проектный logging-конфиг в `src/fm_review/logging.py`.

### LOW-A12. Захардкоженное имя репо в gh-tasks.sh
**Файл:** `scripts/gh-tasks.sh:16-18`
**Рекомендация:** Использовать `gh repo view --json nameWithOwner`. В хуках уже исправлено.

### LOW-A13. Мёртвый код: extract_findings_from_summary() -- no-op
**Файл:** `scripts/generate_findings_registry.py:38-50`
**Рекомендация:** Удалить или реализовать.

### LOW-A14. Порог покрытия 35% -- мало
**Файл:** `.github/workflows/ci.yml:27`
**Рекомендация:** Повысить до 50% -> 65%.

### LOW-A15. Нет ruff/shellcheck в CI
**Рекомендация:** Добавить ruff + ShellCheck.

### INFO-A16. JSON Schema без рантайм-валидации
**Файл:** `schemas/agent-contracts.json:1-575`
**Рекомендация:** Валидировать _summary.json в Quality Gate.

---

## Часть 3: Claude Code Best Practices

### HIGH-P1. enabledMcpjsonServers конфликтует с enableAllProjectMcpServers [FIXED]
**Файл:** `.claude/settings.json:136-140`
**Стандарт:** [Claude Code Docs](https://code.claude.com/docs/en/memory)
**Риск:** `enableAll=true` + явный список 3 из 6 серверов = конфликт. Если поведение изменится, langfuse/playwright/agentation отвалятся.
**Исправлено:** `enabledMcpjsonServers` удалён. Коммит Sprint 1.

### HIGH-P2. Только 1 из 12 агентов имеет заполненную agent-memory
**Файл:** `.claude/agent-memory/`
**Стандарт:** [Claude Code Subagents](https://www.pubnub.com/blog/best-practices-for-claude-code-sub-agents/)
**Риск:** 11 агентов переучиваются с нуля каждый запуск, хотя `memory: project` включён.
**Рекомендация:** Засидировать MEMORY.md для агентов 0, 1, 7 (page IDs, версии ФМ, уроки).

### HIGH-P3. make-no-mistakes -- skill, а должен быть rule [FIXED]
**Файл:** `.claude/skills/make-no-mistakes/SKILL.md`
**Стандарт:** [Claude Code Skills](https://code.claude.com/docs/en/skills)
**Риск:** Нет `disable-model-invocation`, может авто-загружаться с полным доступом к инструментам. Это поведенческое руководство.
**Исправлено:** Конвертировано в `.claude/rules/make-no-mistakes.md`, skill удалён. Коммит Sprint 1.

### MEDIUM-P4. COMMON_RULES.md (283 строки) дублирует .claude/rules/
**Файл:** `agents/COMMON_RULES.md`
**Стандарт:** [CLAUDE.md Guide 2026](https://serenitiesai.com/articles/claude-md-complete-guide-2026)
**Риск:** Одни и те же правила грузятся 2-3 раза, сжирая контекстное окно.
**Рекомендация:** Сократить до ~100 строк, заменить дублирование на ссылки.

### ~~MEDIUM-P5. Ни один агент не использует haiku~~ [REMOVED]
**Решение:** Принципиальная позиция — младшие модели не используются. Качество важнее стоимости.

### MEDIUM-P6. 4 rules без path-scoping грузятся всегда
**Файл:** `.claude/rules/subagents-registry.md`, `smoke-testing.md`, `project-file-map.md`, `dod.md`
**Стандарт:** [Claude Code Rules Directory](https://claudefa.st/blog/guide/mechanics/rules-directory)
**Риск:** ~200+ строк в каждой сессии вне зависимости от контекста.
**Рекомендация:** Добавить `paths:` к smoke-testing (scripts/, hooks/), dod (gh-tasks.sh).

### MEDIUM-P7. Нет guard-хука на границы записи агентов
**Файл:** `.claude/agents/` (агенты 0, 5, 8, 9, 10 имеют Write+Edit)
**Стандарт:** [Claude Code Hooks](https://code.claude.com/docs/en/hooks)
**Риск:** Агент может записать в чужую директорию (AGENT_X_*/). Границы только в промпте.
**Рекомендация:** PreToolUse хук валидирующий пути записи.

### MEDIUM-P8. Knowledge Graph минимально засижен (26 строк)
**Файл:** `.claude-memory/memory.jsonl`
**Стандарт:** [Claude Code Memory](https://code.claude.com/docs/en/memory)
**Рекомендация:** Расширить seed_memory.py до ~100-200 сущностей.

### LOW-P9. guard-mcp-confluence-write.sh блокирует ВСЕ MCP-записи включая Agent 7
**Файл:** `.claude/hooks/guard-mcp-confluence-write.sh:8-9`
**Рекомендация:** Проверять вызывающего агента, разрешать Agent 7.

### LOW-P10. Нет guard-хука для деструктивных Bash-команд
**Файл:** `.claude/settings.json:27-37`
**Рекомендация:** Блокировать `rm -rf`, `git push --force`, `git reset --hard`.

### LOW-P11. vercel-react skill не привязан к Agent 9
**Файл:** `.claude/skills/vercel-react-best-practices/SKILL.md`
**Рекомендация:** Добавить `disable-model-invocation: true` + `skills:` в agent-9.

### LOW-P12. Нет UserPromptSubmit хука
**Файл:** `.claude/settings.json`
**Рекомендация:** Рассмотреть для аудит-трейла + детекции инъекций.

---

## Часть 4: Доменная область

### HIGH-D1. Таймаут бизнес-ревью не enforced в коде
**Файл:** `CLAUDE.md`
**Стандарт:** [OMG PLM](https://www.omg.org/plm/)
**Риск:** "MAX 5 итераций, TIMEOUT 7 дней" -- только текст. Ревью может зависнуть навсегда.
**Рекомендация:** Добавить iteration_count + start_timestamp в PROJECT_CONTEXT.md; quality_gate.sh проверяет.

### MEDIUM-D2. README заявляет 9 агентов, на самом деле 12
**Файл:** `README.md:3`
**Рекомендация:** Обновить до 12 (0-10 + оркестратор).

### MEDIUM-D3. pipeline.json не содержит Agent 9 и Agent 10
**Файл:** `config/pipeline.json:13-23`
**Стандарт:** [Azure AI Agent Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
**Рекомендация:** Добавить условные записи (по context.platform).

### MEDIUM-D4. Нет структурной XHTML-валидации
**Файл:** `src/fm_review/xhtml_sanitizer.py:1-40`
**Рекомендация:** Добавить проверку well-formedness XML + whitelist элементов Confluence Storage Format.

### LOW-D5. MODEL_SELECTION.md устарел (агенты 6, 7)
**Файл:** `docs/MODEL_SELECTION.md:17-19`
**Рекомендация:** Синхронизировать с pipeline.json.

### ~~LOW-D6. BPMN-агент генерирует drawio, не стандартный BPMN 2.0 XML~~ [REMOVED]
**Решение:** Agent 8 переведён на табличный формат. drawio/BPMN XML не используются — агент не мог генерировать корректные диаграммы.

---

## Часть 5: Масштабируемость

### HIGH-X1. Нет rate limiting Confluence API для параллельных агентов
**Файл:** `src/fm_review/confluence_utils.py:59`
**Стандарт:** [Confluence API Best Practices](https://medium.com/@erdemucak/using-the-confluence-rest-api-for-automation-and-integration-d589ec02c98a)
**Риск:** Параллельные агенты вызывают каскадные 429-ошибки.
**Рекомендация:** Token bucket rate limiter. CONFLUENCE_RATE_LIMIT_RPS=5.

### MEDIUM-X2. Файловая блокировка только для одного хоста
**Файл:** `src/fm_review/confluence_utils.py:82-155`
**Рекомендация:** Задокументировать ограничение. Для мульти-хоста: optimistic locking Confluence.

### MEDIUM-X3. Нет кэша чтения страниц Confluence
**Файл:** `src/fm_review/confluence_utils.py:275-277`
**Стандарт:** [LLM Cost Optimization](https://futureagi.com/blogs/llm-cost-optimization-2025)
**Риск:** Одна страница запрашивается 9+ раз за pipeline.
**Рекомендация:** TTL-кэш в файл. Снизит API-вызовы на 60-70%.

### LOW-X4. Многопроектная параллельность не протестирована
**Файл:** `projects/`
**Рекомендация:** Создать тестовый проект, проверить конкурентные пайплайны.

### LOW-X5. MCP жёстко привязан к Confluence
**Файл:** `agents/COMMON_RULES.md:22-35`
**Рекомендация:** Низкий приоритет. Рассмотреть абстрактные имена операций в будущем.

---

## Часть 6: Документация

### HIGH-DOC1. README без инструкции по установке и архитектурной диаграммы
**Файл:** `README.md:1-129`
**Стандарт:** [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
**Рекомендация:** Добавить: Prerequisites (Python 3.11+, Claude Code CLI, gum, jq, Infisical CLI), Installation (пошагово), Architecture (Mermaid-диаграмма).

### MEDIUM-DOC2. CHANGELOG не соответствует keepachangelog
**Файл:** `docs/CHANGELOG.md:1-674`
**Стандарт:** [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
**Рекомендация:** Разделить системный и проектный. Формат: Added/Changed/Fixed/Removed.

### MEDIUM-DOC3. DECISIONS.md содержит только 3 записи
**Файл:** `DECISIONS.md:1-54`
**Стандарт:** [ADR](https://github.blog/developer-skills/documentation-done-right-a-developers-guide/)
**Рекомендация:** Добавить D-004..D-008 (выбор Claude Code SDK, Langfuse, файловые блокировки, пивот Notion->Confluence).

### MEDIUM-DOC4. Нет English README для кросс-командного использования
**Файл:** `README.md:1`
**Рекомендация:** Добавить README.en.md (описание, архитектура, getting started).

### LOW-DOC5. .env.example не содержит Telegram/Infisical переменных
**Файл:** `.env.example:1-50`
**Рекомендация:** Добавить TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, блок Infisical.

### LOW-DOC6. Нет автогенерируемой API-документации
**Файл:** `src/fm_review/`
**Рекомендация:** Добавить pdoc3 или mkdocstrings. Низкий приоритет.

---

## Часть 7: Что сделано хорошо

1. **CLAUDE.md -- 48 строк.** Ниже рекомендуемого порога 50-100. Фокус на маршрутизации и границах. [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices)

2. **12-агентная hub-and-spoke архитектура** с pipeline (1->[2,4]->5->3->QG->7->[8,6]) и параллельными стадиями. [Google Multi-Agent Design Patterns](https://www.infoq.com/news/2026/01/multi-agent-design-patterns/)

3. **Полное покрытие lifecycle хуков** -- все 7 типов (SessionStart, SubagentStart/Stop, Pre/PostToolUse, PreCompact, Stop). Мало кто использует PreCompact. [Claude Code Hooks](https://code.claude.com/docs/en/hooks)

4. **SubagentStop БЛОКИРУЮЩИЙ** для GitHub Issues (exit 2). Детерминистическое управление, а не рекомендация. [Claude Code Hooks](https://code.claude.com/docs/en/hooks)

5. **Эшелонированная безопасность** -- block-secrets.sh, guard-confluence-write.sh, guard-mcp-confluence-write.sh, XHTML-санитайзер, детекция prompt injection (15+ паттернов). [OWASP](https://owasp.org/Top10/2025/)

6. **Confluence safety stack** -- файловая блокировка + бэкап перед PUT + retry (tenacity) + JSONL audit log + rollback. [Confluence API BP](https://medium.com/@erdemucak/using-the-confluence-rest-api-for-automation-and-integration-d589ec02c98a)

7. **Infisical 3-уровневый** -- Universal Auth -> keyring -> .env fallback. [Infisical Best Practices](https://infisical.com/blog/secrets-management-best-practices)

8. **Наблюдаемость расходов** -- Langfuse per-agent трейсинг, Telegram-отчёты, месячный дашборд, алерты при 80% бюджета. [LLM Cost Optimization](https://futureagi.com/blogs/llm-cost-optimization-2025)

9. **Самоулучшение** -- `.patches/` + `/evolve` собирает паттерны ошибок и обновляет инструкции агентов.

10. **Quality Gate** с проверкой когерентности версий (PROJECT_CONTEXT vs _summary.json vs live Confluence API) + покрытие CRITICAL-находок тестами.

11. **3-уровневый CI** -- ci.yml (тесты + bandit + pip-audit), claude.yml (AI-ревью PR), security-review.yml (безопасность).

12. **Machine-readable контракты агентов** (v2.2) -- `schemas/agent-contracts.json` типизированные интерфейсы. [OMG PLM](https://www.omg.org/plm/)

13. **DoD enforcement** -- gh-tasks.sh не создаёт без --body, не закрывает без --comment. Кросс-чек артефактов.

14. **Сохранение контекста** -- SessionStart -> PreCompact -> Stop с CONTEXT.md/HANDOFF.md.

---

## Часть 8: Roadmap

### Спринт 1: CRITICAL безопасность + quick wins [DONE 2026-02-25]

| # | Задача | Статус | Файлы |
|---|--------|--------|-------|
| 1 | ~~Ротировать токены~~ | НЕ ДЕЛАЕМ | Ротация не планируется |
| 2 | MI-креды в keyring | → Спринт 2 | infra/infisical/.env.machine-identity |
| 3 | Пиннить GitHub Actions на SHA (S6) | **DONE** | .github/workflows/*.yml |
| 4 | Пиннить MCP npm-пакеты (S7) | **DONE** | .mcp.json |
| 5 | Убрать enabledMcpjsonServers (P1) | **DONE** | .claude/settings.json |
| 6 | make-no-mistakes -> rule (P3) | **DONE** | .claude/rules/make-no-mistakes.md |
| 7 | Исправить heredoc-инъекцию (S5) | **DONE** | scripts/confluence-restore.sh |
| 8 | Убрать id-token:write (S14) | **DONE** | .github/workflows/security-review.yml |

### Спринт 2: Hardening безопасности (2-3 дня)

| # | Задача | Время | Файлы |
|---|--------|-------|-------|
| 1 | Установить CA-сертификат, включить SSL | 2ч | confluence_utils.py, export_from_confluence.py, mcp-confluence.sh |
| 2 | set -euo pipefail в оставшихся скриптах | 1ч | 9 скриптов |
| 3 | Расширить паттерны block-secrets.sh | 30м | .claude/hooks/block-secrets.sh |
| 4 | JSON через jq в notify.sh, quality_gate.sh | 1ч | scripts/notify.sh, quality_gate.sh |
| 5 | Стандартизировать shebangs | 30м | 11 скриптов |
| 6 | Один источник зависимостей | 30м | requirements.txt, ci.yml |
| 7 | Guard-хук для деструктивных Bash | 1ч | .claude/hooks/, settings.json |
| 8 | Rate limit Telegram-бота | 30м | scripts/tg-bot.py |

### Спринт 3: Архитектура DRY + качество (2-3 дня)

| # | Задача | Время | Файлы |
|---|--------|-------|-------|
| 1 | Извлечь _get_page_id() + _make_ssl_context() | 1ч | src/fm_review/utils.py |
| 2 | Декомпозиция run_agent.py (1213 строк) | 4ч | scripts/run_agent/ package |
| 3 | Разбить main() publish_to_confluence.py | 2ч | scripts/publish_to_confluence.py |
| 4 | Добавить ruff + ShellCheck в CI | 1ч | pyproject.toml, ci.yml |
| 5 | Поднять coverage 35% -> 50% | 30м | ci.yml |
| 6 | Удалить мёртвый код | 15м | generate_findings_registry.py |
| 7 | Убрать глобальное состояние | 1ч | export_from_confluence.py |
| 8 | Убрать sys.path.insert | 30м | publish_to_confluence.py |

### Спринт 4: Claude Code оптимизация (1-2 дня)

| # | Задача | Время | Файлы |
|---|--------|-------|-------|
| 1 | Засидировать agent-memory для агентов 0, 1, 7 | 1ч | .claude/agent-memory/ |
| 2 | Сократить COMMON_RULES.md 283->100 строк | 2ч | agents/COMMON_RULES.md |
| 3 | Добавить path-scoping к 3 rules | 30м | .claude/rules/ |
| 4 | Привязать vercel skill к Agent 9 | 15м | .claude/skills/, .claude/agents/ |
| 5 | Guard-хук на границы записи | 2ч | .claude/hooks/, settings.json |
| 6 | Расширить Knowledge Graph | 1ч | scripts/seed_memory.py |
| 7 | Разрешить Agent 7 MCP-запись | 30м | .claude/hooks/guard-mcp-confluence-write.sh |

### Спринт 5: Домен + документация + масштаб (2-3 дня)

| # | Задача | Время | Файлы |
|---|--------|-------|-------|
| 1 | README: prerequisites + Mermaid-диаграмма | 2ч | README.md |
| 2 | Enforce таймаут бизнес-ревью | 2ч | quality_gate.sh, PROJECT_CONTEXT.md |
| 3 | Rate limiter Confluence | 2ч | confluence_utils.py |
| 4 | Кэш страниц Confluence | 2ч | src/fm_review/confluence_cache.py |
| 5 | Агенты 9/10 в pipeline | 1ч | pipeline.json, run_agent.py |
| 6 | Обновить DECISIONS.md (5 ADR) | 1ч | DECISIONS.md |
| 7 | Синхронизировать MODEL_SELECTION.md | 15м | docs/MODEL_SELECTION.md |
| 8 | README: 9->12 агентов | 5м | README.md |
| 9 | XHTML структурная валидация | 1ч | xhtml_sanitizer.py |

---

## Сводная таблица

| # | Sev | ID | Область | Описание | Файл | Стандарт |
|---|-----|-----|---------|----------|------|----------|
| 1 | C | S1 | Безопасность | .env plaintext секреты | `.env:1` | OWASP |
| 2 | C | S2 | Безопасность | Infisical MI plaintext | `.env.machine-identity:6` | Infisical |
| 3 | C | S3 | Безопасность | Infisical hosted plaintext | `.env.infisical:5` | OWASP |
| 4 | H | S4 | Безопасность | SSL отключён | `confluence_utils.py:46` | OWASP A07 |
| 5 | ~~H~~ | S5 | Безопасность | ~~Heredoc-инъекция~~ | `confluence-restore.sh:111` | **FIXED** |
| 6 | ~~H~~ | S6 | Безопасность | ~~Actions без SHA~~ | `ci.yml:14` | **FIXED** |
| 7 | ~~H~~ | S7 | Безопасность | ~~MCP @latest~~ | `.mcp.json:26` | **FIXED** |
| 8 | H | A1 | Архитектура | DRY _get_page_id | `publish_to_confluence.py:62` | DRY |
| 9 | H | A2 | Архитектура | DRY _make_ssl_context | `confluence_utils.py:32` | DRY |
| 10 | H | A3 | Архитектура | run_agent.py 1213 строк | `run_agent.py:1` | Python BP |
| 11 | H | A4 | Архитектура | main() 297 строк | `publish_to_confluence.py:320` | Python BP |
| 12 | ~~H~~ | P1 | Практики | ~~MCP конфликт серверов~~ | `settings.json:136` | **FIXED** |
| 13 | H | P2 | Практики | 1/12 agent-memory | `.claude/agent-memory/` | CC Subagents |
| 14 | ~~H~~ | P3 | Практики | ~~Skill -> Rule~~ | `make-no-mistakes/SKILL.md` | **FIXED** |
| 15 | H | D1 | Домен | Нет enforce таймаута | `CLAUDE.md` | OMG PLM |
| 16 | H | X1 | Масштаб | Нет rate limiting | `confluence_utils.py:59` | Confluence |
| 17 | H | DOC1 | Документация | README без setup | `README.md:1` | README BP |
| 18 | M | S8 | Безопасность | Нет pipefail | `orchestrate.sh:1` | Bash BP |
| 19 | M | S9 | Безопасность | >= vs == deps | `requirements.txt:4` | Python Sec |
| 20 | M | S10 | Безопасность | Мало паттернов секретов | `block-secrets.sh:22` | OWASP |
| 21 | M | S11 | Безопасность | sed-инъекция | `quality_gate.sh:346` | OWASP |
| 22 | M | S12 | Безопасность | Нет rate limit бота | `tg-bot.py:115` | OWASP API |
| 23 | M | S13 | Безопасность | JSON через printf | `notify.sh:75` | OWASP |
| 24 | M | A5 | Архитектура | Широкий except | `langfuse_tracer.py:301` | Python Exc |
| 25 | M | A6 | Архитектура | Дубль проверки токена | `confluence_utils.py:431` | DRY |
| 26 | M | A7 | Архитектура | sys.path.insert | `publish_to_confluence.py:559` | Python BP |
| 27 | M | A8 | Архитектура | Глобальное состояние | `export_from_confluence.py:517` | Python BP |
| 28 | M | A9 | Архитектура | Непоследовательные shebangs | 11 скриптов | Google Shell |
| 29 | M | P4 | Практики | Дубли COMMON_RULES | `COMMON_RULES.md` | CC Guide |
| ~~30~~ | ~~M~~ | ~~P5~~ | ~~Практики~~ | ~~Нет haiku~~ | ~~`.claude/agents/`~~ | ~~REMOVED~~ |
| 31 | M | P6 | Практики | Rules без path-scope | `.claude/rules/` | CC Rules |
| 32 | M | P7 | Практики | Нет guard записи | `.claude/agents/` | CC Hooks |
| 33 | M | P8 | Практики | KG минимален | `memory.jsonl` | CC Memory |
| 34 | M | D2 | Домен | README 9 vs 12 | `README.md:3` | README BP |
| 35 | M | D3 | Домен | Pipeline без 9,10 | `pipeline.json:13` | Azure AI |
| 36 | M | D4 | Домен | Нет XHTML валидации | `xhtml_sanitizer.py:1` | Confluence |
| 37 | M | X2 | Масштаб | Lock одного хоста | `confluence_utils.py:82` | Multi-Agent |
| 38 | M | X3 | Масштаб | Нет кэша страниц | `confluence_utils.py:275` | LLM Cost |
| 39 | M | DOC2 | Документация | CHANGELOG формат | `CHANGELOG.md:1` | keepachangelog |
| 40 | M | DOC3 | Документация | DECISIONS.md 3 записи | `DECISIONS.md:1` | ADR |
| 41 | M | DOC4 | Документация | Нет English README | `README.md:1` | OS README |
| 42-61 | L/I | * | * | 19 LOW + 1 INFO (D6 REMOVED) | (см. разделы выше) | |

### Pivot по областям

| Область | C | H | M | L | I | Всего |
|---------|---|---|---|---|---|-------|
| Безопасность | 3 | 4 | 6 | 3 | 0 | 16 |
| Архитектура | 0 | 4 | 5 | 6 | 1 | 16 |
| Практики (CC) | 0 | 3 | 5 | 4 | 0 | 12 |
| Домен | 0 | 1 | 3 | 2 | 0 | 6 |
| Масштаб | 0 | 1 | 2 | 2 | 0 | 5 |
| Документация | 0 | 1 | 3 | 2 | 0 | 6 |
| **Итого** | **3** | **14** | **24** | **19** | **1** | **61** |

---

## Источники

| # | Источник | URL | Часть |
|---|----------|-----|-------|
| 1 | OWASP Top 10 2025 | https://owasp.org/Top10/2025/ | 1 |
| 2 | OWASP Secrets Management | https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html | 1 |
| 3 | OWASP Command Injection | https://owasp.org/www-community/attacks/Command_Injection | 1 |
| 4 | OWASP API Security | https://owasp.org/API-Security/ | 1 |
| 5 | Infisical Secrets BP | https://infisical.com/blog/secrets-management-best-practices | 1 |
| 6 | Python Security (Snyk) | https://snyk.io/blog/python-security-best-practices-cheat-sheet/ | 1 |
| 7 | Python Security (Safety) | https://www.getsafety.com/blog-posts/python-security-best-practices-for-developers | 1 |
| 8 | GitHub Actions Hardening (Wiz) | https://www.wiz.io/blog/github-actions-security-guide | 1 |
| 9 | GitHub Actions Hardening (Orca) | https://orca.security/resources/blog/github-actions-hardening/ | 1 |
| 10 | Bash BP 2025 | https://medium.com/@prasanna.a1.usage/best-practices-we-need-to-follow-in-bash-scripting-in-2025-cebcdf254768 | 1, 2 |
| 11 | Google Shell Style Guide | https://google.github.io/styleguide/shellguide.html | 2 |
| 12 | Python Project Layout | https://realpython.com/ref/best-practices/project-layout/ | 2 |
| 13 | Python Project BP (Dagster) | https://dagster.io/blog/python-project-best-practices | 2 |
| 14 | Modern Python Setup | https://albertsikkema.com/python/development/best-practices/2025/10/31/modern-python-project-setup.html | 2 |
| 15 | Python Exception Handling | https://blog.miguelgrinberg.com/post/the-ultimate-guide-to-error-handling-in-python | 2 |
| 16 | Python Code Quality | https://realpython.com/python-code-quality/ | 2 |
| 17 | Multi-Agent Patterns (InfoQ) | https://www.infoq.com/news/2026/01/multi-agent-design-patterns/ | 2, 5 |
| 18 | Python Static Analysis | https://www.code-quality.io/best-python-static-code-analysis-tools | 2 |
| 19 | Claude Code Best Practices | https://code.claude.com/docs/en/best-practices | 3 |
| 20 | Claude Code Subagents | https://code.claude.com/docs/en/sub-agents | 3 |
| 21 | Claude Code Skills | https://code.claude.com/docs/en/skills | 3 |
| 22 | Claude Code Hooks | https://code.claude.com/docs/en/hooks | 3 |
| 23 | Claude Code Memory | https://code.claude.com/docs/en/memory | 3 |
| 24 | Claude Code Agent Teams | https://code.claude.com/docs/en/agent-teams | 3 |
| 25 | CLAUDE.md Guide 2026 | https://serenitiesai.com/articles/claude-md-complete-guide-2026 | 3 |
| 26 | Claude Code Rules | https://claudefa.st/blog/guide/mechanics/rules-directory | 3 |
| 27 | Claude Code Subagents BP | https://www.pubnub.com/blog/best-practices-for-claude-code-sub-agents/ | 3 |
| 28 | Claude Code Hooks Guide | https://smartscope.blog/en/generative-ai/claude/claude-code-hooks-guide/ | 3 |
| 29 | Azure AI Agent Patterns | https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns | 4, 5 |
| 30 | Confluence API BP | https://medium.com/@erdemucak/using-the-confluence-rest-api-for-automation-and-integration-d589ec02c98a | 4, 5 |
| 31 | README Best Practices | https://www.tilburgsciencehub.com/topics/collaborate-share/share-your-work/content-creation/readme-best-practices/ | 6 |
| 32 | Best-README-Template | https://github.com/othneildrew/Best-README-Template | 6 |
| 33 | Keep a Changelog | https://keepachangelog.com/en/1.1.0/ | 6 |
| 34 | OMG PLM | https://www.omg.org/plm/ | 4 |
| 35 | BPMN 2.0 ISO 19510 | http://www.omg.org/spec/BPMN/2.0/ | 4 |
| 36 | LLM Cost Optimization | https://futureagi.com/blogs/llm-cost-optimization-2025 | 5 |
| 37 | Multi-Agent (Kore.ai) | https://www.kore.ai/blog/choosing-the-right-orchestration-pattern-for-multi-agent-systems | 5 |
| 38 | Docs Done Right (GitHub) | https://github.blog/developer-skills/documentation-done-right-a-developers-guide/ | 6 |
| 39 | Tech Docs BP | https://www.wondermentapps.com/blog/technical-documentation-best-practices/ | 6 |

---

## Метрики

| Показатель | До Sprint 1 | После Sprint 1 |
|-----------|-------------|----------------|
| Файлов проверено | 76 | 76 |
| Веб-источников | 39 | 39 |
| Находок всего | 61 (3C+14H+24M+19L+1I) | 53 актуальных (6 FIXED, 2 REMOVED) |
| Безопасность | 6.5/10 | **7.5/10** |
| Архитектура | 7.5/10 | 7.5/10 |
| Best Practices | 8.5/10 | **9.0/10** |
| Домен | 8/10 | 8/10 |
| Масштабируемость | 7/10 | 7/10 |
| Документация | 6.5/10 | 6.5/10 |
| **Зрелость** | **BETA** | **BETA+** |

**Sprint 1 (2026-02-25):** S5, S6, S7, P1, P3, S14 FIXED. P5, D6 REMOVED. S1 ротация — не делается. .env удаление — в прогрессе (Infisical работает).
**До PRODUCTION:** Удалить .env, MI-креды в keyring, SSL для Confluence, set -euo pipefail, README с setup.
