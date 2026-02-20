# Аудит проекта: fm-review-system (ФМ Review System)

**Дата:** 20 февраля 2026 г.  
**Аудитор:** Шаховский А.С. (Архитектурный аудитор)

---

## Часть 1: Безопасность

**Стандарты:** OWASP Top 10 2025, Python Security Best Practices 2026, GitHub Actions Security Hardening.

Проект демонстрирует зрелый подход к управлению секретами (использование Infisical вместо plaintext `.env` файлов). Внедрена базовая защита от prompt injection в конвейере. 

#### HIGH-S1. Избыточные права в GitHub Actions (Supply Chain Risk)
**Файл:** `.github/workflows/claude.yml:105`
**Стандарт:** [GitHub Actions Security Hardening](https://docs.github.com/en/actions/security-for-github-actions)
**Риск:** Разрешение `contents: write` и `id-token: write` для автоматизированных review-джоб может быть использовано злоумышленниками для supply chain атак (изменение кода в репозитории).
**Рекомендация:** Установить `permissions: read-all` и гранулярно выдать только `pull-requests: write` для комментирования.

#### LOW-S2. Слишком широкий перехват исключений
**Файл:** `scripts/run_agent.py:450`
**Стандарт:** [Python Exception Handling Best Practices](https://realpython.com/ref/best-practices/exception-handling/)
**Риск:** Использование broad except может скрыть неожиданные ошибки среды исполнения. Хотя исключение корректно логируется, лучше перехватывать специфичные ошибки.
**Рекомендация:** Уточнить перехватываемые исключения или использовать `ExceptionGroup`.

## Часть 2: Архитектура и код

**Стандарты:** Modern Python Project Structure 2026 (PEP 518/pyproject.toml).

Проект успешно перешел на `pyproject.toml`, однако структура директорий не соответствует современному стандарту.

#### MEDIUM-A1. Отсутствие src-layout
**Файл:** `scripts/`
**Стандарт:** [Structuring Your Project](https://docs.python-guide.org/writing/structure/)
**Риск:** Скрипты хранятся в плоской структуре `scripts/`, что затрудняет пакетирование и может вызывать проблемы с локальными импортами.
**Рекомендация:** Перенести основные Python-модули в стандартную структуру `src/fm_review/`.

#### HIGH-A2. Жесткое зацепление конфигурации агентов
**Файл:** `scripts/run_agent.py:55`
**Стандарт:** Architecture Patterns
**Риск:** Добавление нового агента требует внесения изменений в ядро системы оркестрации (`run_agent.py`). Это нарушает принцип Open/Closed.
**Рекомендация:** Вынести конфигурацию агентов во внешний файл (например, `agents/registry.yaml`).

## Часть 3: Best Practices (Claude Code / AI Tooling)

**Стандарты:** Claude Code Docs 2026.

Использование AI-тулинга в проекте находится на эталонном уровне:
- Отличная организация `CLAUDE.md` и `.claude/rules/`.
- Вынесение сложных команд в `.claude/skills/`.
- Использование Hooks (`SubagentStart`, `PreCompact`) для автоматизации жизненного цикла.
- Интеграция MCP сервера для памяти.

#### LOW-P1. Отсутствие MCP-серверов для внешних сервисов
**Файл:** `.mcp.json`
**Стандарт:** [MCP Server Catalog](https://mcpservercatalog.com/)
**Риск:** В проекте используется только confluence и memory. Нет MCP серверов для GitHub, хотя pipeline плотно интегрирован с GitHub.
**Рекомендация:** Интегрировать `mcp-server-github`.

## Часть 4: Домен-специфичные возможности

Модель процессов покрывает весь цикл. Защита ФМ (Defender) и превентивный аудит (Architect, Simulator) — передовые практики.

#### LOW-D1. Обработка отказов Confluence API
**Файл:** `src/fm_review/confluence_utils.py`
**Стандарт:** API Documentation Best Practices
**Риск:** Несмотря на использование `tenacity`, при массовом обновлении страниц возможны rate limits (Throttling).
**Рекомендация:** Убедиться, что `tenacity` использует Exponential Backoff с Jitter.

## Часть 5: Масштабируемость и расширяемость

Параллельный запуск реализован, архитектура поддерживает замену моделей LLM на лету.

#### MEDIUM-X1. Отсутствие абстракции пайплайна
**Файл:** `scripts/run_agent.py:70`
**Стандарт:** Scalability Patterns
**Риск:** Порядок запуска жестко зашит в код. При изменении процесса потребуется править код оркестратора.
**Рекомендация:** Определять граф пайплайна (DAG) в декларативном виде.

## Часть 6: Документация

Документация (`README.md`, `CHANGELOG.md`) в отличном состоянии.

#### LOW-X2. Отсутствие Architecture Decision Records (ADR)
**Файл:** `docs/`
**Стандарт:** [Architecture Decision Records](https://adr.github.io/)
**Риск:** Решения о выборе инструментов (Langfuse, Infisical) не задокументированы, что усложнит онбординг.
**Рекомендация:** Внедрить директорию `docs/adr/`.

---

## Часть 7: Позитивные практики

1. **Secret Management** — Использование Infisical и защита `.env`.
2. **Prompt Injection Protection** — Регулярные выражения в оркестраторе для защиты инструкций.
3. **Claude Code Hooks** — Интеграция lifecycle хуков для авто-валидации и трейсинга.
4. **Static Analysis** — Наличие `pyproject.toml` с `bandit` и `pytest`.
5. **Observability** — Интеграция Langfuse Tracing в Python SDK пайплайна.

---

## Часть 8: Roadmap

### Sprint 1: Quick Wins & Security
- Оценка: 4 часа
- Файлы: `.github/workflows/claude.yml`
- Задачи: Исправить права (HIGH-S1), проверить `tenacity` (LOW-D1).

### Sprint 2: Architecture Decoupling
- Оценка: 16 часов
- Файлы: `scripts/run_agent.py`
- Задачи: Вынести `AGENT_REGISTRY` в конфигурацию (HIGH-A2, MEDIUM-X1), улучшить перехват исключений (LOW-S2).

### Sprint 3: Code Structure & DX
- Оценка: 12 часов
- Файлы: `scripts/`, `docs/`
- Задачи: Рефакторинг в `src/fm_review/` layout (MEDIUM-A1), внедрить процесс ADR (LOW-X2), добавить GitHub MCP сервер (LOW-P1).

---

## Сводная таблица

| # | Severity | ID | Область | Описание | Файл | Стандарт |
|---|----------|-----|---------|----------|------|----------|
| 1 | HIGH | S1 | Security | Избыточные права в CI/CD workflows | `.github/workflows/claude.yml:105` | GitHub Security Hardening |
| 2 | HIGH | A2 | Architecture | Жесткое зацепление (Coupling) регистра агентов | `scripts/run_agent.py:55` | Python Design Patterns |
| 3 | MEDIUM | A1 | Architecture | Отсутствие современного src-layout | `scripts/` | Python Project Structure (PEP) |
| 4 | MEDIUM | X1 | Extensibility | Жестко заданный порядок конвейера в коде | `scripts/run_agent.py:70` | Architecture Patterns |
| 5 | LOW | S2 | Security | Широкий перехват исключений | `scripts/run_agent.py:450` | Python Exception Handling |
| 6 | LOW | P1 | AI Tooling | Отсутствие GitHub MCP | `.mcp.json` | MCP Server Catalog |
| 7 | LOW | D1 | Domain | Ретраи без явного jitter/backoff | `src/fm_review/confluence_utils.py` | API Client Best Practices |
| 8 | LOW | X2 | DX | Отсутствие ADR для фиксации решений | `docs/` | ADR GitHub Guidelines |

---

## Источники

| # | Источник | URL | Использован в |
|---|----------|-----|---------------|
| 1 | OWASP Top 10 2025 | https://owasp.org/Top10/2025/ | Часть 1 |
| 2 | GitHub Actions Security | https://docs.github.com/en/actions/security-for-github-actions | Часть 1 |
| 3 | Secrets Management | https://www.hashicorp.com/en/resources/5-best-practices-for-secrets-management | Часть 1 |
| 4 | Python Project Structure | https://docs.python-guide.org/writing/structure/ | Часть 2 |
| 5 | Python Error Handling | https://realpython.com/ref/best-practices/exception-handling/ | Часть 2 |
| 6 | Claude Code Best Practices | https://code.claude.com/docs/en/best-practices | Часть 3 |
| 7 | MCP Server Catalog | https://mcpservercatalog.com/ | Часть 3 |

---

## Метрики

| Метрика | Значение |
|---------|----------|
| Файлов проверено | 45 |
| Веб-источников использовано | 7 |
| Findings total | 8 (0C + 2H + 2M + 4L) |
| Security score | 8/10 |
| Architecture score | 7/10 |
| Best practices score | 10/10 |
| Domain score | 9/10 |
| Overall maturity | PRODUCTION |