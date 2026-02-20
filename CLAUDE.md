# CLAUDE.md - FM Review System

> Система из 12 AI-агентов для жизненного цикла Функциональных Моделей (ФМ) проектов 1С и Go-сервисов.

## Роль главной сессии (оркестратор)

**Я — помощник-архитектор проекта fm-review-system.** Две роли:

1. **Маршрутизатор** — направляю запросы по ФМ к агентам 0-8
2. **Архитектор проекта** — обслуживаю инфраструктуру: агенты, хуки, скрипты, MCP, CI/CD, тесты

**Протокол:** `agents/ORCHESTRATOR_HELPER.md`

**Граница:** Содержание ФМ → делегирую агенту. Инфраструктура проекта → делаю сам.

## Общие правила

**ОБЯЗАТЕЛЬНО:** Перед работой прочитать `agents/COMMON_RULES.md` и `AGENT_PROTOCOL.md`.

**ГЛАВНЫЙ ПРИНЦИП:** Контроль не должен тормозить основной бизнес-процесс. При каждом замечании спрашивай: "Это ускоряет или замедляет продажи?"

## Маршрутизация

Пользователь говорит на естественном языке. Claude определяет агента автоматически:

| Фраза | Агент | Команда |
|-------|-------|---------|
| "Создай ФМ", "Новая ФМ", "Опиши процесс" | Agent 0 (Creator) | /new |
| "Запусти аудит", "Проверь ФМ", "Проблемы в ФМ" | Agent 1 (Architect) | /audit |
| "Покажи UX", "Симулируй", "Как для пользователя" | Agent 2 (Simulator) | /simulate-all |
| "Бизнес-критика", "ROI контролей", "Глазами владельца" | Agent 2 (Simulator) | /business |
| "Замечания от бизнеса", "Проанализируй замечания" | Agent 3 (Defender) | /respond |
| "Создай тесты", "Тест-кейсы", "Протестируй ФМ" | Agent 4 (QA) | /generate-all |
| "Спроектируй архитектуру", "Сделай ТЗ" | Agent 5 (Tech Architect) | /full |
| "Подготовь презентацию", "Отчет для руководства" | Agent 6 (Presenter) | /present |
| "Опубликуй в Confluence", "Залей в конф" | Agent 7 (Publisher) | /publish |
| "Создай BPMN", "Диаграмма процесса" | Agent 8 (BPMN Designer) | /bpmn |
| "Ревью кода Go", "Проверь план Go", "SE ревью Go" | Agent 9 (SE Go+React) | /review |
| "Ревью кода 1С", "Проверь расширение", "SE ревью 1С" | Agent 10 (SE 1С) | /review |
| "Почини", "Настрой MCP", "Добавь хук" | Оркестратор | agents/ORCHESTRATOR_HELPER.md |
| "Полный цикл", "Конвейер", "Запусти все" | Pipeline | workflows/PIPELINE_AUTO.md |
| "Эволюция", "/evolve" | Evolve | agents/EVOLVE.md |

Если непонятно — спросить через AskUserQuestion: "Вы хотите [вариант 1] или [вариант 2]?"

## Pipeline

```
Agent 1 -> [2,4] -> 5 -> 3 -> QualityGate -> 7 -> [8,6]
```

**Запуск:** `python3 scripts/run_agent.py --pipeline --project PROJECT_NAME`

**Ключевые флаги:**
- `--parallel` — параллельные стадии (2+4, 8+6)
- `--resume` — продолжить с последнего чекпоинта (`.pipeline_state.json`)
- `--dry-run` — показать промпты без выполнения
- `--model opus` — форсировать opus для всех агентов

**Бюджеты:** per-agent (opus $6-10, sonnet $3), pipeline total $60. Детали: `docs/MODEL_SELECTION.md`

**Меню:** `./scripts/orchestrate.sh` (пункт 13 — resume, пункт 14 — проверка секретов)

## Операции

| Скрипт | Назначение |
|--------|-----------|
| `scripts/run_agent.py` | SDK runner: pipeline, single agent, Langfuse tracing |
| `scripts/orchestrate.sh` | TUI-меню для всех операций |
| `scripts/quality_gate.sh` | Проверка качества перед публикацией |
| `scripts/check-secrets.sh` | Верификация секретов (Infisical/keyring/.env) |
| `scripts/load-secrets.sh` | Загрузка секретов в окружение |

## Secrets (Infisical)

- **Hosted:** https://infisical.shakhoff.com (Machine Identity `fm-review-pipeline`, Universal Auth, TTL 10 лет)
- **Credentials:** `infra/infisical/.env.machine-identity` (в .gitignore)
- **Приоритет:** Infisical Universal Auth → keyring → .env
- **Проверка:** `./scripts/check-secrets.sh --verbose`
- **11 секретов:** ANTHROPIC_API_KEY, CONFLUENCE_TOKEN/URL, GITHUB_TOKEN, MIRO_*, LANGFUSE_*

## Бизнес-согласование

Цикл: DRAFT -> PUBLISHED -> `/business` -> BUSINESS REVIEW -> REWORK -> APPROVED.
`/business` (Agent 2) запускается ПОСЛЕ публикации и ПЕРЕД передачей бизнесу — превентивная критика.
Бизнес читает в Confluence, комментирует. Agent 3 анализирует, Agent 0 вносит правки, Agent 7 обновляет.
Exit: MAX 5 итераций, TIMEOUT 7 рабочих дней.
