# Xray Test Linking — Обязательный процесс

## Когда применяется

После КАЖДОГО создания/прогона тестов (Agent 14, или вручную).

## Правило 3 уровней привязки

Каждый Test issue привязывается к **ВСЕМ** релевантным requirements:

1. **Конкретная задача** — код которую тестирует (EKFLAB-37 PostgreSQL repos, EKFLAB-38 Kafka consumers)
2. **Зонтичная тест-задача** — если есть (EKFLAB-152 "Тесты: инфраструктурные адаптеры")
3. **Epic** — родительский Epic задачи-requirement

## Направление ссылки (КРИТИЧНО!)

```
requirement = outwardIssue
test = inwardIssue
```

Обратное направление = Requirement Status остаётся UNCOVERED.

## Обязательная проверка ПОСЛЕ привязки

```bash
# JQL: все "Готово" задачи текущего спринта — проверить что НЕТ UNCOVERED
project=EKFLAB AND status=10001 AND labels=product:profitability AND issuetype not in (11100,11101,11102,11103,11104,11105)
```

Поле `customfield_11521` (Requirement Status) должно быть OK для ВСЕХ задач спринта типа "код" (entities, adapters, use cases, etc.).

## Что НЕ нужно привязывать

- Процессные задачи: ревью (Agent 9), верификация спринта, миграция задач
- Задачи-исправления: наследуют coverage через основной requirement
- Мета-задачи: Sprint verification, migration

## Автоматизация

```bash
scripts/jira-tasks.sh xray-register --test-plan ... --exec ... --tests '...' --reqs '...' --sprint N
```

Скрипт автоматически: добавляет в спринт, labels, Test Plan, ссылки "Tests", Test Execution, PASS, закрывает.
