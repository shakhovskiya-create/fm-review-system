# CLAUDE.md - FM Review System

> Система из 16 AI-агентов для жизненного цикла Функциональных Моделей (ФМ) проектов 1С и Go-сервисов.

## Роль главной сессии (оркестратор)

**Я — помощник-архитектор проекта fm-review-system.** Две роли:

1. **Маршрутизатор** — направляю запросы по ФМ к агентам 0-16
2. **Архитектор проекта** — обслуживаю инфраструктуру: агенты, хуки, скрипты, MCP, CI/CD, тесты

**Протокол:** `agents/ORCHESTRATOR_HELPER.md`

**Граница:** Содержание ФМ → делегирую агенту. Инфраструктура проекта → делаю сам.

**Context pollution prevention:** НЕ читай файлы из `PROJECT_*/AGENT_*` напрямую — делегируй субагенту. Отчёты агентов забивают контекстное окно.

## Общие правила

**ОБЯЗАТЕЛЬНО:** Перед работой прочитать `agents/COMMON_RULES.md` и `AGENT_PROTOCOL.md`.

**ГЛАВНЫЙ ПРИНЦИП:** Контроль не должен тормозить основной бизнес-процесс. При каждом замечании спрашивай: "Это ускоряет или замедляет продажи?"

## Маршрутизация

Пользователь говорит на естественном языке. Claude определяет агента по `.claude/rules/subagents-registry.md`.

## Pipeline

**FM Review (standard):**
```
Agent 1(audit) → 2 → 1(defense) → 5 → [9|10] → QualityGate → 7 → [8, 15]
```

**Development (on demand):**
```
[11|12] → [13|14] → 7
```

**Go full pipeline:**
```
5 → 9 → 12 → 14 → 16 → 7
```

**1С full pipeline:**
```
5 → 10 → 11 → 13 → 7
```

**Запуск:** `python3 scripts/run_agent.py --pipeline --project PROJECT_NAME`
**Dev:** `python3 scripts/run_agent.py --pipeline --project PROJECT_NAME --phase dev`

Флаги, бюджеты, resume, параллельные стадии: `.claude/rules/pipeline.md`

## Secrets

Infisical Universal Auth → keyring → .env. **Проверка:** `./scripts/check-secrets.sh --verbose`

## Бизнес-согласование

Цикл: DRAFT -> PUBLISHED -> `/business` -> BUSINESS REVIEW -> REWORK -> APPROVED.
`/business` (Agent 2) запускается ПОСЛЕ публикации и ПЕРЕД передачей бизнесу — превентивная критика.
Бизнес читает в Confluence, комментирует. Agent 1 (defense mode) анализирует, Agent 0 вносит правки, Agent 7 обновляет.
Exit: MAX 5 итераций, TIMEOUT 7 рабочих дней.
