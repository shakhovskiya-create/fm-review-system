# Архитектурный аудит v4: fm-review-system

**Дата:** 2026-02-20
**Аудитор:** Claude Opus 4.6 (автоматический глубокий аудит)
**Скоуп:** Архитектура, безопасность, агенты, best practices, 1С-возможности, multi-platform
**Стек:** Python 3.11 / Claude Code SDK / Confluence MCP / Miro MCP / Langfuse / Infisical

---

## Executive Summary

Система fm-review-system — зрелый прототип (BETA), покрывающий полный жизненный цикл ФМ. 10 агентов, 9 hooks, 6 skills, Knowledge Graph + Episodic Memory + Agent Memory.

**Текущий уровень зрелости: PROTOTYPE → BETA**
- Бизнес-логика: **9/10** — глубокая проработка процессов
- Техническая инфраструктура: **7/10** — работает, но есть уязвимости
- Безопасность: **5/10** — критические проблемы с eval, SSL, secrets
- 1С-выход: **7/10** — ТЗ промышленного качества, пробелы в инфраструктуре 1С
- Multi-platform: **3/10** — Agent 5 жёстко привязан к 1С

**Найдено:** 6 CRITICAL, 12 HIGH, 10 MEDIUM, 4 LOW

---

## Часть 1: Безопасность

### CRITICAL

#### S-C1. `eval` на выводе Infisical CLI
**Файл:** `scripts/load-secrets.sh:36,46`
```bash
eval "$(infisical export --format=dotenv-export 2>/dev/null)"
```
**Риск:** Если Infisical CLI скомпрометирован или заменён malicious-бинарником, `eval` выполнит произвольный код.
**Рекомендация:** Парсить построчно:
```bash
while IFS= read -r line; do
    [[ "$line" =~ ^export\ ([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] && export "${BASH_REMATCH[1]}=${BASH_REMATCH[2]}"
done < <(infisical export --format=dotenv-export 2>/dev/null)
```

#### S-C2. Shell-to-Python path injection в validate-summary.sh
**Файл:** `.claude/hooks/validate-summary.sh:35`
```python
with open('$recent') as f:
```
**Риск:** Переменная `$recent` подставляется из shell в Python-строку. Файл с кавычкой в имени (`x'_summary.json`) сломает Python-строку.
**Рекомендация:** Передать как аргумент: `python3 -c "... sys.argv[1] ..." "$recent"`

#### S-C3. Live secrets в plaintext файлах на диске
**Файлы:** `.env`, `scripts/.env.local`, `infra/infisical/.env.infisical`, `infra/infisical/.env.machine-identity`
**Риск:** Хотя файлы в .gitignore, любой процесс/агент/hook может их прочитать. ANTHROPIC_API_KEY, GITHUB_TOKEN, Machine Identity credentials — всё в plaintext.
**Рекомендация:**
1. `chmod 600` на все .env файлы
2. Ротировать все токены после аудита
3. Перенести Machine Identity credentials в system keyring

### HIGH

#### S-H1. SSL verification глобально отключена в 5 файлах
**Файлы:** `publish_to_confluence.py:42`, `confluence_utils.py:30`, `export_from_confluence.py:34`, `check_confluence_macros.py:53`, `mcp-confluence.sh:11`
```python
ssl._create_default_https_context = ssl._create_unverified_context
```
**Риск:** Отключается SSL для ВСЕХ HTTPS-соединений в процессе (не только Confluence). MITM-атака на Anthropic API / Langfuse / GitHub.
**Рекомендация:** Использовать per-request context или установить CA-сертификат Confluence.

#### S-H2. 7 из 9 hooks без `set -u` и `pipefail`
**Файлы:** `guard-confluence-write.sh`, `session-log.sh`, `validate-xhtml-style.sh`, `subagent-context.sh`, `auto-save-context.sh`, `inject-project-context.sh`, `langfuse-trace.sh`
**Риск:** Undefined-переменные раскрываются в пустую строку → неожиданные пути, пропущенные ошибки в пайпах.
**Рекомендация:** Добавить `set -euo pipefail` во все hooks.

#### S-H3. langfuse-trace.sh напрямую `source` .env с секретами
**Файл:** `.claude/hooks/langfuse-trace.sh:16`
```bash
[ -f "${PROJECT_DIR}/.env" ] && set -a && source "${PROJECT_DIR}/.env" && set +a
```
**Риск:** Hook загружает все секреты в среду. Тест `test_hooks_dont_read_env_files` НЕ ловит это (ищет `"source .env"`, а здесь `source "${PROJECT_DIR}/.env"`).
**Рекомендация:** Удалить source, полагаться на переменные среды от load-secrets.sh. Исправить тест: `re.search(r'source\s+.*\.env', content)`.

#### S-H4. CI interactive job с `contents: write` на comment-trigger
**Файл:** `.github/workflows/claude.yml:96`
**Риск:** Любой комментатор `@claude` на PR может инструктировать Claude записать в репозиторий.
**Рекомендация:** Добавить проверку `github.event.comment.author_association in ['MEMBER', 'OWNER']`.

#### S-H5. `acceptEdits` в автономном pipeline
**Файл:** `scripts/run_agent.py:339`
**Риск:** Каждый агент может модифицировать любой файл без подтверждения. Сбойный агент может перезаписать .env, hooks, CI-конфиги.
**Рекомендация:** Ограничить `cwd` агента папкой конкретного проекта.

### MEDIUM

#### S-M1. Hardcoded fallback PAGE_ID 83951683
**Файлы:** `publish_to_confluence.py:77`, `export_from_confluence.py:29`, `check_confluence_macros.py:62,80`
**Рекомендация:** Убрать fallback, падать с ошибкой если PAGE_ID не найден.

#### S-M2. check_confluence_macros.py читает из plaintext .env.local
**Файл:** `scripts/check_confluence_macros.py:12-29`
**Рекомендация:** Мигрировать на `os.environ.get()`.

#### S-M3. langfuse-trace.sh без `set -e`
**Рекомендация:** Добавить `set -euo pipefail`, заменить `&>/dev/null` на логфайл.

#### S-M4. Bare `except:` ловит SystemExit и KeyboardInterrupt
**Файлы:** `confluence_utils.py:117,124,189`, `publish_to_confluence.py:117`
**Рекомендация:** Заменить на `except Exception:`.

#### S-M5. Audit log directory не в .gitignore
**Файл:** `scripts/.audit_log/`
**Рекомендация:** Добавить в .gitignore.

---

## Часть 2: Архитектура и протоколы агентов

### CRITICAL

#### A-C1. Agent 3 — недокументированная классификация замечаний
**Файл:** `agents/AGENT_3_DEFENDER.md`
Agent 3 (Defender) классифицирует замечания (принять/отклонить/доработать/переформулировать), но схема принятия решений не формализована. Результат зависит от "настроения" LLM, а не от правил.
**Рекомендация:** Добавить формализованную таблицу критериев классификации с примерами для каждой категории.

#### A-C2. Agent 2 — timing режима /business не определён
**Файл:** `agents/AGENT_2_ROLE_SIMULATOR.md`
В pipeline Agent 2 вызывается в режиме `/simulate-all`, но режим `/business` (бизнес-критика от лица собственника/ФД/директора) используется "отдельно, перед бизнес-согласованием" (CLAUDE.md). Нет чёткого trigger-point.
**Рекомендация:** Формализовать: `/business` автоматически вызывается перед PUBLISHED → BUSINESS REVIEW.

#### A-C3. Нет трассируемости findings между агентами
Агенты 1, 2, 4 генерируют findings независимо. Agent 5 ссылается на findingId, но нет центрального реестра findings с деduplикацией.
**Рекомендация:** Создать `PROJECT_*/FINDINGS_REGISTRY.json` — единый реестр findings из всех агентов с dedup-ключами.

### HIGH

#### A-H1. Agent 7 — MCP vs REST fallback не определён
**Файл:** `agents/AGENT_7_PUBLISHER.md`
Agent 7 может использовать MCP (mcp-atlassian) и REST API (confluence_utils.py). Нет чёткого приоритета при отказе одного из каналов.
**Рекомендация:** Документировать: MCP (primary) → REST API (fallback).

#### A-H2. guard-confluence-write.sh обходится через MCP
**Файл:** `.claude/hooks/guard-confluence-write.sh`
Hook блокирует `curl PUT` к Confluence, но MCP-сервер mcp-atlassian пишет напрямую через свой API-клиент без прохождения через hooks.
**Рекомендация:** Расширить guard на MCP-вызовы: PreToolUse для `mcp__confluence__confluence_update_page`.

#### A-H3. Version coherence не валидируется
Файл `CONFLUENCE_PAGE_ID` указывает на страницу, но нет проверки что локальная версия ФМ (в файлах) совпадает с версией в Confluence.
**Рекомендация:** Добавить проверку версии в quality_gate.sh.

#### A-H4. Quality Gate слишком permissive
**Файл:** `scripts/quality_gate.sh`
Код возврата 2 (WARN) позволяет обойти gate с `--reason`. Нет логирования обходов.
**Рекомендация:** Логировать все `--reason` обходы в audit trail.

#### A-H5. XHTML injection risk при публикации
**Файл:** `scripts/publish_to_confluence.py`
Контент генерируется агентами и вставляется в XHTML без санитизации. XSS через Confluence-макросы.
**Рекомендация:** Добавить XHTML-санитайзер перед публикацией.

#### A-H6. Нет cross-agent integration tests
Тесты покрывают отдельные модули, но нет end-to-end тестов потока Agent 0 → ... → Agent 7.
**Рекомендация:** Создать `tests/test_pipeline_integration.py` с mock-агентами.

#### A-H7. Audit log dead code
**Файл:** `src/fm_review/confluence_utils.py:387-399`
Audit log пишется, но нигде не читается — ни в тестах, ни в мониторинге.
**Рекомендация:** Добавить отчёт или quality gate проверку по audit log.

---

## Часть 3: Best Practices (Claude Code 2026)

### Что соответствует

| Practice | Статус | Детали |
|----------|--------|--------|
| CLAUDE.md < 150 строк | **47 строк** | Идеально |
| Rules с path-scoping | **8 rules** | Используются paths: frontmatter |
| Skills для повторяемых операций | **6 skills** | 3 с disable-model-invocation |
| Subagents с memory: project | **10/10** | Все агенты |
| Knowledge Graph MCP | Включен | 12 entities, 14 relations |
| Episodic Memory | Включен глобально | Plugin в ~/.claude/settings.json |
| Hooks lifecycle | **9 hooks** | SessionStart/Stop, Pre/PostToolUse, SubagentStart/Stop |
| Secrets management | Infisical | Self-hosted + Universal Auth |
| CI/CD integration | GitHub Actions | claude.yml + security-review.yml |
| Observability | Langfuse | Self-hosted v3 + hook трейсинг |

### Чего не хватает (best practices 2026)

| Practice | Статус | Рекомендация |
|----------|--------|--------------|
| Agent Teams/Swarms | Не используется | Экспериментальная фича Claude Code — рассмотреть для pipeline |
| Infisical MCP Server | Не интегрирован | Официальный `@infisical/mcp` — нативный доступ к секретам из Claude Code |
| Prompt injection protection | Частичная | Нет системной защиты от injection через Confluence-контент |
| Structured output validation | Частичная | `_summary.json` валидируется, но не через JSON Schema |
| Cost/token tracking | Только Langfuse | Нет бюджетов/лимитов на агентов |
| Rollback mechanism | Нет | При ошибке pipeline нет автоматического отката |

---

## Часть 4: 1С-возможности (FM → ТЗ → Разработка)

### Оценка цепочки

| Этап | Агент | Оценка | Комментарий |
|------|-------|--------|-------------|
| Бизнес-требования | Agent 0 | **9/10** | Глубокое интервью, антипаттерны, тестируемые требования |
| Аудит бизнес-логики | Agent 1 | **9/10** | 10-категорийный чеклист, 1С-фокус |
| UX-проверка | Agent 2 | **8/10** | Симуляция ролей, бизнес-критика |
| Тест-кейсы | Agent 4 | **8/10** | 65+ тест-кейсов, traceability matrix |
| Архитектура + ТЗ | Agent 5 | **7/10** | Полно по бизнес-логике, пробелы в инфраструктуре 1С |

### Что Agent 5 покрывает хорошо
- Справочники с полной структурой реквизитов и типами данных 1С
- Документы с проведением (до/при/после), статусными моделями, блокировками
- Регистры накопления и сведений (измерения, ресурсы, реквизиты)
- 16 фоновых заданий с расписанием, retry, мониторингом
- 5 интеграций с JSON-контрактами (ELMA, WMS, EDI, HR, ЦБ РФ)
- RBAC-матрица с RLS
- Оценка трудоёмкости (2293 часа, 77 объектов)

### Пробелы (1С-специфика)

| # | Пробел | Критичность | Описание |
|---|--------|-------------|----------|
| 1 | Точки расширения типовой | P0 | Какие модули &Перед/&После/&Вместо, какие формы расширяются |
| 2 | Общие модули | P1 | Нет описания экспортных процедур, контекста вызова (сервер/клиент) |
| 3 | Подсистемы | P1 | Объекты расширения не включены в командный интерфейс |
| 4 | Функциональные опции | P1 | Механизм вкл/выкл функциональности |
| 5 | HTTP-сервисы | P1 | Для приёма webhook от ELMA/WMS — не специфицированы как объекты |
| 6 | Управляемые формы | P1 | Нет элементов формы, условной видимости, обработчиков |
| 7 | Печатные формы | P2 | Макеты, области, параметры вывода |
| 8 | Обработчики обновления ИБ | P2 | Начальное заполнение при установке расширения |
| 9 | Миграция данных | P2 | Загрузка существующих ЛС, исторические данные |
| 10 | Планы обмена | P2 | Обмен 1С:УТ <-> 1С:Бухгалтерия |
| 11 | Определяемые типы, константы | P3 | Инфраструктурные мелочи |
| 12 | Тестирование на 1С | P3 | Привязка к Vanessa Automation / xUnitFor1C |

### Вердикт
**ТЗ уровня "senior-разработчик может реализовать" — да (7/10).**
**"Junior может реализовать без вопросов" — нет (4/10).**

Главный пробел — инфраструктурные объекты 1С (подсистемы, общие модули, точки расширения типовой). Добавление пунктов 1-5 в протокол Agent 5 закроет ~80% разрыва.

---

## Часть 5: Multi-Platform (Go/microservices)

### Архитектурная оценка

| Компонент | Готовность к Go | Усилие |
|-----------|-----------------|--------|
| ФМ (бизнес-модель) | **80%** — бизнес-логика абстрактна | Низкое |
| Agent 0 (Creator) | **90%** — шаблон platform-agnostic | 1 вопрос заменить |
| Agent 1 (Auditor) | **70%** — секция /1c жёстко привязана | Создать /platform |
| Agent 2-4, 6-8 | **95%** — работают на уровне бизнес-логики | Минимальное |
| Agent 5 (Tech Architect) | **5%** — полностью 1С-специфичный | Переписать шаблоны |
| JSON-контракты | **60%** — поле `objects1C` | Рефакторинг схем |

### DDD-паттерны в ФМ (уже подразумеваются)

| Паттерн | Статус | Пример из FM-LS-PROFIT |
|---------|--------|------------------------|
| **Aggregates** | Подразумевается | ЛокальнаяСмета (root), ЗаказКлиента (root) |
| **Value Objects** | Подразумевается | Отклонение (п.п.), Рентабельность (%), Приоритет (P1/P2) |
| **Domain Events** | Частично | "Заказ на согласовании", "SLA превышен" |
| **Event Sourcing** | Частично | ЖурналАудитаЛС = event log (неудаляемый, 5 лет) |
| **CQRS** | Подразумевается | Write: документы, Read: кеш-регистры для отчётов |
| **Saga** | Описан явно | 4-уровневый маршрут согласования с компенсациями |

### Стратегия multi-platform

**Рекомендация: Уровень 2 — абстрактный промежуточный слой (3-5 дней)**

Разделить Agent 5 на два этапа:
1. **Domain Architect** (platform-agnostic): Aggregates, State machines, Business rules, Integration contracts
2. **Platform Mapper** (1С / Go / Python): Маппинг domain model → конкретный стек

Маппинг-таблица:

| 1С-концепция | Go/microservices |
|---|---|
| Справочники | Reference data service (CRUD API + DB) |
| Документы | Domain aggregates (DDD) |
| Регистры накопления | Event store / materialized views |
| Регистры сведений | Configuration/State services |
| ОбработкаПроведения | Command handlers |
| Подписки на события | Event bus (Kafka/NATS) |
| Фоновые задания | Cron jobs / async workers |
| Расширение конфигурации | Отдельный микросервис |
| Формы (UI) | API-контракты (OpenAPI) |
| RLS | Policy engine (OPA/Casbin) |
| ELMA BPM | Temporal.io / workflow engine |

### Что уже готово для Go
- REST API контракты с ELMA — полные JSON-схемы
- REST API контракты с WMS — полные JSON-схемы
- Webhook/Polling механизмы описаны
- MQ упоминается как альтернатива REST

### Чего не хватает для Go
- Event bus (Kafka/NATS) для inter-service коммуникации
- Service discovery
- API gateway
- gRPC контракты
- Health check / readiness проbes
- Circuit breaker (есть только retry 3x)

---

## Часть 6: Сводная таблица всех findings

### По приоритету

| # | Severity | ID | Область | Описание | Файл |
|---|----------|-----|---------|----------|------|
| 1 | CRITICAL | S-C1 | Security | `eval` на выводе Infisical CLI | `load-secrets.sh:36,46` |
| 2 | CRITICAL | S-C2 | Security | Shell-to-Python path injection | `validate-summary.sh:35` |
| 3 | CRITICAL | S-C3 | Security | Live secrets в plaintext на диске | `.env`, `.env.local`, `.env.*` |
| 4 | CRITICAL | A-C1 | Protocol | Agent 3 недокументированная классификация | `AGENT_3_DEFENDER.md` |
| 5 | CRITICAL | A-C2 | Protocol | Agent 2 /business timing не определён | `AGENT_2_ROLE_SIMULATOR.md` |
| 6 | CRITICAL | A-C3 | Data Flow | Нет трассируемости findings между агентами | Архитектурный пробел |
| 7 | HIGH | S-H1 | Security | SSL глобально отключена в 5 файлах | `confluence_utils.py`, etc. |
| 8 | HIGH | S-H2 | Security | 7/9 hooks без `set -u`/`pipefail` | `.claude/hooks/*.sh` |
| 9 | HIGH | S-H3 | Security | Hook sources .env с секретами | `langfuse-trace.sh:16` |
| 10 | HIGH | S-H4 | Security | CI `contents: write` на comment-trigger | `claude.yml:96` |
| 11 | HIGH | S-H5 | Security | `acceptEdits` в autonomous pipeline | `run_agent.py:339` |
| 12 | HIGH | A-H1 | Protocol | Agent 7 MCP vs REST fallback | `AGENT_7_PUBLISHER.md` |
| 13 | HIGH | A-H2 | Security | guard-confluence-write обходится MCP | `guard-confluence-write.sh` |
| 14 | HIGH | A-H3 | Data Flow | Version coherence не валидируется | Архитектурный пробел |
| 15 | HIGH | A-H4 | QA | Quality Gate слишком permissive | `quality_gate.sh` |
| 16 | HIGH | A-H5 | Security | XHTML injection при публикации | `publish_to_confluence.py` |
| 17 | HIGH | A-H6 | QA | Нет cross-agent integration tests | Тестовый пробел |
| 18 | HIGH | A-H7 | Ops | Audit log dead code | `confluence_utils.py:387` |
| 19 | MEDIUM | S-M1 | Reliability | Hardcoded fallback PAGE_ID | `publish_to_confluence.py:77` |
| 20 | MEDIUM | S-M2 | Security | .env.local в check_confluence_macros | `check_confluence_macros.py:12` |
| 21 | MEDIUM | S-M3 | Reliability | langfuse-trace без set -e | `langfuse-trace.sh` |
| 22 | MEDIUM | S-M4 | Reliability | Bare `except:` | `confluence_utils.py:117` |
| 23 | MEDIUM | S-M5 | Ops | Audit log не в .gitignore | `scripts/.audit_log/` |
| 24 | MEDIUM | 1C-1 | 1С | Нет точек расширения типовой | `AGENT_5_TECH_ARCHITECT.md` |
| 25 | MEDIUM | 1C-2 | 1С | Нет общих модулей | `AGENT_5_TECH_ARCHITECT.md` |
| 26 | MEDIUM | 1C-3 | 1С | Нет подсистем/функциональных опций | `AGENT_5_TECH_ARCHITECT.md` |
| 27 | MEDIUM | 1C-4 | 1С | Нет HTTP-сервисов для webhook | `AGENT_5_TECH_ARCHITECT.md` |
| 28 | MEDIUM | 1C-5 | 1С | Нет управляемых форм (wireframes) | `AGENT_5_TECH_ARCHITECT.md` |
| 29 | LOW | S-L1 | Ops | Audit log directory не gitignored | `confluence_utils.py:47` |
| 30 | LOW | S-L2 | Reliability | Security test false negative | `test_security.py:143` |
| 31 | LOW | S-L3 | Security | Unnecessary `id-token: write` в CI | `.github/workflows/*.yml` |
| 32 | LOW | S-L4 | Reliability | `os.execve` с full env | `export_from_confluence.py:44` |

### По области

| Область | CRITICAL | HIGH | MEDIUM | LOW | Всего |
|---------|----------|------|--------|-----|-------|
| Security | 3 | 6 | 2 | 2 | 13 |
| Protocol | 2 | 1 | 0 | 0 | 3 |
| Data Flow | 1 | 1 | 0 | 0 | 2 |
| QA | 0 | 2 | 0 | 0 | 2 |
| Ops | 0 | 1 | 2 | 0 | 3 |
| Reliability | 0 | 0 | 2 | 2 | 4 |
| 1С | 0 | 0 | 5 | 0 | 5 |
| **Итого** | **6** | **12** | **10** | **4** | **32** |

---

## Часть 7: Позитивные практики

1. **CLAUDE.md 47 строк** — эталон для Claude Code проектов
2. **Rules с path-scoping** — 8 rules, контекст загружается только когда нужен
3. **3 типа памяти** — Knowledge Graph + Episodic + Agent Memory — полное покрытие
4. **Infisical self-hosted** — секреты не в облаке, Machine Identity для CI
5. **Quality Gate** перед публикацией — формализованный чекпоинт
6. **Confluence lock + backup + retry** — защита от race conditions и потери данных
7. **Audit logging** — JSONL-трейл всех Confluence-операций
8. **Langfuse observability** — self-hosted трейсинг каждой сессии
9. **JSON Schema контракты** — agent-contracts.json v2.1 для валидации выхода агентов
10. **Traceability** — findingId → tests → ФМ-секция → ТЗ-объект

---

## Часть 8: Roadmap рекомендаций

### Sprint 1: Безопасность (1-2 дня)

| # | Действие | Усилие |
|---|----------|--------|
| 1 | Заменить `eval` на построчный парсинг в load-secrets.sh | 30 мин |
| 2 | Исправить path injection в validate-summary.sh | 15 мин |
| 3 | `chmod 600` на все .env файлы | 5 мин |
| 4 | `set -euo pipefail` во все hooks | 30 мин |
| 5 | Убрать `source .env` из langfuse-trace.sh | 15 мин |
| 6 | Исправить security test (regex вместо substring) | 15 мин |
| 7 | Добавить author_association check в claude.yml | 15 мин |
| 8 | Заменить bare `except:` на `except Exception:` | 15 мин |

### Sprint 2: Архитектура (2-3 дня)

| # | Действие | Усилие |
|---|----------|--------|
| 1 | Формализовать Agent 3 classification schema | 2 часа |
| 2 | Определить trigger для Agent 2 /business | 1 час |
| 3 | Создать FINDINGS_REGISTRY.json формат + генератор | 4 часа |
| 4 | Добавить MCP guard в PreToolUse hook | 2 часа |
| 5 | Добавить version coherence check в quality_gate.sh | 2 часа |
| 6 | Логировать QG overrides в audit trail | 1 час |
| 7 | Per-request SSL context вместо глобального отключения | 2 часа |
| 8 | XHTML-санитайзер для publish_to_confluence.py | 3 часа |

### Sprint 3: 1С-возможности (3-5 дней)

| # | Действие | Усилие |
|---|----------|--------|
| 1 | Добавить "Точки расширения типовой" в протокол Agent 5 | 4 часа |
| 2 | Добавить "Инфраструктурные объекты" в протокол Agent 5 | 4 часа |
| 3 | Добавить "Миграция и развёртывание" в протокол Agent 5 | 2 часа |
| 4 | Шаблон печатных форм | 2 часа |
| 5 | Псевдокод запросов для сложных алгоритмов | 3 часа |
| 6 | Wireframes форм (ASCII) | 3 часа |

### Sprint 4: Multi-Platform (5-7 дней)

| # | Действие | Усилие |
|---|----------|--------|
| 1 | Добавить выбор платформы в интервью Agent 0 и Agent 5 | 2 часа |
| 2 | Создать Domain Architect шаблон (platform-agnostic) | 8 часов |
| 3 | Создать Go Platform Mapper | 8 часов |
| 4 | Рефакторинг agent-contracts.json (objects1C → domainObjects) | 4 часа |
| 5 | Cross-agent integration tests | 8 часов |

### Sprint 5: Operations (опционально)

| # | Действие | Усилие |
|---|----------|--------|
| 1 | Интеграция Infisical MCP Server | 2 часа |
| 2 | Rollback mechanism для pipeline | 8 часов |
| 3 | Cost/token бюджеты по агентам | 4 часа |
| 4 | Prompt injection protection (system-level) | 8 часов |

---

## Метрики системы

| Метрика | Значение |
|---------|----------|
| CLAUDE.md | 47 строк |
| Rules | 8 файлов |
| Skills | 6 (3 + 3 operational) |
| Agents | 10 (9 ФМ + 1 оркестратор) |
| Hooks | 9 events |
| Memory | KG (12 entities) + Episodic + Agent |
| Secrets | Infisical (11 secrets, 3-level fallback) |
| Tests | 386 passed, 9 skipped |
| CI | 3 workflows (claude, security, CI) |
| Findings total | 32 (6C + 12H + 10M + 4L) |
| 1С-ready score | 7/10 |
| Multi-platform score | 3/10 |
| Security score | 5/10 |
| Overall maturity | BETA |
