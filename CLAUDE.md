# CLAUDE.md - FM Review System

> Система из 9 AI-агентов для жизненного цикла Функциональных Моделей (ФМ) проектов 1С.
> Этот файл читается Claude Code автоматически.

## Общие правила для всех агентов

**ОБЯЗАТЕЛЬНО:** Перед работой прочитать `agents/COMMON_RULES.md` - общие правила (AskUserQuestion, Confluence, форматирование, версионность, верификация).

**ОБЯЗАТЕЛЬНО:** Перед работой прочитать `AGENT_PROTOCOL.md` - протокол старта/завершения сессии (логи, HANDOFF, WORKPLAN).

**ГЛАВНЫЙ ПРИНЦИП:** Контроль не должен тормозить основной бизнес-процесс. При каждом замечании спрашивай: "Это ускоряет или замедляет продажи?"

---

## Маршрутизация

Пользователь говорит на естественном языке. Claude определяет агента автоматически:

| Фраза | Агент | Команда |
|-------|-------|---------|
| "Создай ФМ", "Новая ФМ", "Опиши процесс" | Agent 0 (Creator) | /new |
| "Запусти аудит", "Проверь ФМ", "Проблемы в ФМ" | Agent 1 (Architect) | /audit |
| "Покажи UX", "Симулируй", "Как для пользователя" | Agent 2 (Simulator) | /simulate-all |
| "Замечания от бизнеса", "Проанализируй замечания" | Agent 3 (Defender) | /respond |
| "Создай тесты", "Тест-кейсы", "Протестируй ФМ" | Agent 4 (QA) | /generate-all |
| "Спроектируй архитектуру", "Сделай ТЗ" | Agent 5 (Tech Architect) | /full |
| "Подготовь презентацию", "Отчет для руководства" | Agent 6 (Presenter) | /present |
| "Опубликуй в Confluence", "Залей в конф" | Agent 7 (Publisher) | /publish |
| "Создай BPMN", "Диаграмма процесса" | Agent 8 (BPMN Designer) | /bpmn |
| "Полный цикл", "Конвейер", "Запусти все" | Pipeline | workflows/PIPELINE_AUTO.md |
| "Эволюция", "/evolve" | Evolve | agents/EVOLVE.md |

Если непонятно - спросить через AskUserQuestion: "Вы хотите [вариант 1] или [вариант 2]?"

## Subagents (Claude Code)

9 агентов зарегистрированы как Claude Code subagents в `.claude/agents/`:

| Subagent | Модель | Протокол |
|----------|--------|----------|
| `agent-0-creator` | opus | `agents/AGENT_0_CREATOR.md` |
| `agent-1-architect` | opus | `agents/AGENT_1_ARCHITECT.md` |
| `agent-2-simulator` | opus | `agents/AGENT_2_ROLE_SIMULATOR.md` |
| `agent-3-defender` | opus | `agents/AGENT_3_DEFENDER.md` |
| `agent-4-qa-tester` | sonnet | `agents/AGENT_4_QA_TESTER.md` |
| `agent-5-tech-architect` | opus | `agents/AGENT_5_TECH_ARCHITECT.md` |
| `agent-6-presenter` | sonnet | `agents/AGENT_6_PRESENTER.md` |
| `agent-7-publisher` | sonnet | `agents/AGENT_7_PUBLISHER.md` |
| `agent-8-bpmn-designer` | sonnet | `agents/AGENT_8_BPMN_DESIGNER.md` |

Каждый subagent при запуске читает свой протокол из `agents/` и `agents/COMMON_RULES.md`.

---

## Файлы системы

**Subagents:** `.claude/agents/agent-0-creator.md` ... `.claude/agents/agent-8-bpmn-designer.md`

**Протоколы агентов:** `agents/AGENT_0_CREATOR.md` ... `agents/AGENT_8_BPMN_DESIGNER.md`

**Общие правила:** `agents/COMMON_RULES.md`

**Confluence:**
- `docs/CONFLUENCE_TEMPLATE.md` - шаблон XHTML
- `docs/ARCHIVE/CONFLUENCE_REQUIREMENTS-2026-02-05.md` - исторический лог требований (архив)
- `scripts/publish_to_confluence.py` - обновление Confluence (v3.0, lock+backup+retry)
- `scripts/lib/confluence_utils.py` - API клиент

**Документация:** `docs/PROMPTS.md` (промпты), `docs/CHANGELOG.md`, `docs/CONTRACT_CONFLUENCE_FM.md`, `docs/LEAD_AUDITOR_FULL_AUDIT.md`, `docs/FC_IMPLEMENTATION_REPORT.md`

**Артефакты Lead Architect (НЕ затирать!):** `docs/FINDINGS_LEDGER.md` (реестр находок), `docs/ARCHITECT_WORKPLAN.md`

**Self-Improvement:** `.patches/` (паттерны ошибок), `agents/EVOLVE.md` (/evolve)

**Governance:** `AGENT_PROTOCOL.md`, `HANDOFF.md`, `DECISIONS.md`, `logs/`

**Скрипты:** `scripts/orchestrate.sh` (главное меню), `scripts/run_agent.py` (автономный запуск через Claude Code SDK + Langfuse), `scripts/quality_gate.sh`, `scripts/fm_version.sh`, `scripts/new_project.sh`, `scripts/export_from_confluence.py`

**Observability:** `scripts/lib/langfuse_tracer.py` (Stop hook трейсер), `infra/langfuse/` (self-hosted Langfuse v3)

**Memory (контекст между сессиями):**
- **Knowledge Graph** (`@modelcontextprotocol/server-memory`): MCP-сервер для хранения сущностей, связей и фактов. Данные: `.claude-memory/memory.jsonl`. Seed: `scripts/seed_memory.py`. Инструменты: `mcp__memory__search_nodes`, `mcp__memory__create_entities`, `mcp__memory__add_observations`, `mcp__memory__create_relations`.
- **Episodic Memory** (`episodic-memory@superpowers-marketplace`): семантический поиск по прошлым сессиям Claude Code. Настройка: глобально в `~/.claude/settings.json` (работает во всех проектах). Хранение: `~/.config/superpowers/conversation-archive/`. Доступна только в главной сессии (не субагентам).
- **Agent Memory** (`memory: project` в subagent frontmatter): персональная память каждого субагента (`.claude/agent-memory/<name>/MEMORY.md`).

**Skills:** `.claude/skills/evolve/` (/evolve), `.claude/skills/quality-gate/` (предзагрузка Agent 7), `.claude/skills/fm-audit/` (чеклист аудита, предзагрузка Agent 1)

**Progress file:** `CONTEXT.md` - инкрементальный лог для длительных сессий (читается SessionStart/PreCompact hooks)

**Model Selection:** `docs/MODEL_SELECTION.md` - обоснование выбора моделей (opus/sonnet) по агентам

**CI/CD:** `.github/workflows/claude.yml` (PR review + @claude), `.github/workflows/security-review.yml` (security scan)

**Схемы:** `schemas/agent-contracts.json` (v2.1)

---

## Проекты

Каждая ФМ = отдельный проект в `projects/PROJECT_[NAME]/`:

```
PROJECT_[NAME]/
  README.md, CONFLUENCE_PAGE_ID, PROJECT_CONTEXT.md, WORKPLAN.md
  CHANGES/FM-*-CHANGES.md
  AGENT_1_ARCHITECT/ ... AGENT_5_TECH_ARCHITECT/
  REPORTS/
```

| Проект | ФМ | Статус |
|--------|----|--------|
| PROJECT_SHPMNT_PROFIT | FM-LS-PROFIT v1.0.3 | Готов к разработке |

---

## Pipeline (конвейер)

```
Agent 0 (Create) -> Agent 1 (Audit) -> Agent 2 (Simulator) -> Agent 4 (QA) -> Agent 5 (Tech Arch)
  -> Agent 3 (Defender) -> Quality Gate -> Agent 7 (Publish) -> Agent 8 (BPMN) -> Agent 6 (Presenter)
```

> Agent 3 анализирует findings агентов 1, 2, 4, 5 перед Quality Gate.
> Agent 2 в конвейере = /simulate-all. Режим /business - отдельно, перед бизнес-согласованием.

**Запуск:**
- В чате: "Запусти полный цикл ФМ FM-LS-PROFIT" (читает workflows/PIPELINE_AUTO.md)
- Скрипт: `python3 scripts/run_agent.py --pipeline --project PROJECT_SHPMNT_PROFIT` (или `--parallel`)
- Меню: `./scripts/orchestrate.sh`

**Правила пайплайна:**
- Quality Gate ОБЯЗАТЕЛЕН перед Agent 7: `./scripts/quality_gate.sh PROJECT_NAME`
- Коды: 0=OK, 1=CRITICAL (блокирует), 2=WARN (пропуск с --reason)
- Каждый агент читает результаты предыдущих из PROJECT_*/AGENT_*/
- Каждый агент создает _summary.json (схема: schemas/agent-contracts.json)

---

## Кросс-агентный поток

**При старте:** читает PROJECT_CONTEXT.md, сканирует AGENT_*/, читает ФМ из Confluence.

**При завершении:** сохраняет результат в AGENT_X_*/, создает _summary.json, обновляет PROJECT_CONTEXT.md, WORKPLAN.md.

| Агент | Читает от | Что использует |
|-------|-----------|----------------|
| Agent 1 | - | Чистый анализ ФМ |
| Agent 2 | Agent 1 | Замечания для фокуса симуляции |
| Agent 3 | Agent 1, 2 | Замечания для ответов |
| Agent 4 | Agent 1, 2 | Замечания и UX для тест-кейсов |
| Agent 5 | Agent 1, 2, 4 | Полная картина для архитектуры |
| Agent 6 | Все | Синтез для презентации |
| Agent 7 | Confluence | Управление контентом |

---

## Confluence API

- URL: https://confluence.ekf.su
- Auth: Bearer token (PAT)
- API: /rest/api/content/{PAGE_ID}?expand=body.storage,version
- Формат: XHTML storage
- Безопасность: lock + backup + retry (lib/confluence_utils.py)
- **MCP-сервер:** `mcp-atlassian` (`.mcp.json`) - нативный доступ из Claude Code (11 инструментов: search, get/update/create page, comments, labels)

## Hooks (автоматизация)

Настроены в `.claude/settings.json`, скрипты в `.claude/hooks/`:

| Хук | Тип | Назначение |
|-----|-----|-----------|
| `inject-project-context.sh` | SessionStart | Инжектирует контекст активных проектов |
| `subagent-context.sh` | SubagentStart (agent-.*) | Инжектирует контекст в субагенты |
| `guard-confluence-write.sh` | PreToolUse (Bash) | Блокирует прямой curl PUT к Confluence |
| `validate-xhtml-style.sh` | PostToolUse (Bash) | Проверяет XHTML стили и отсутствие AI-упоминаний |
| `validate-summary.sh` | SubagentStop (agent-.*) | Валидация _summary.json после завершения агента |
| `session-log.sh` | Stop | Логирует завершение сессии |
| `auto-save-context.sh` | Stop | Обновляет timestamp в PROJECT_CONTEXT.md |
| `langfuse-trace.sh` | Stop | Трейсинг сессии для Langfuse |
| `precompact-save-context.sh` | PreCompact | Сохраняет контекст проекта перед компакцией |

## Бизнес-согласование

Цикл: DRAFT -> PUBLISHED -> BUSINESS REVIEW -> REWORK -> APPROVED.
Бизнес читает в Confluence, оставляет комментарии. Agent 3 анализирует, Agent 0 вносит правки, Agent 7 обновляет.
Exit: MAX 5 итераций, TIMEOUT 7 рабочих дней.

## 1С-фокус (для Agent 1)

При анализе бизнес-правил проверять: последовательность, состояния/переходы, проведение (до/при/после), блокировки, права доступа, идемпотентность, откат/сторно, интеграции, фоновые задания, аудит.

## Антипаттерны

Искать: "требуется согласование" вместо автоправила, цепочки согласований >2 уровней, ручные проверки автоматизируемого, контроль только на UI, отсутствие дефолтов.

---

## Типы документов в Confluence

| Тип | Префикс | Агент |
|-----|---------|-------|
| Функциональная модель | FM- | Agent 0/1 -> Agent 7 |
| Техзадание | TS- | Agent 5 |
| Архитектура | ARC- | Agent 5 |
| Тест-план | TC- | Agent 4 |
| Отчет | RPT- | Agent 6 |
