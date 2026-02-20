---
paths:
  - "projects/**/CHANGES/**"
  - "projects/**/AGENT_*/**"
---

# Правила /apply и артефактов агентов

## Процесс /apply
1. Показать план изменений (Где - Было - Станет)
2. Получить подтверждение через AskUserQuestion
3. Интегрировать изменения СРАЗУ в основной текст (НЕ в отдельный раздел)
4. ЗАПРЕЩЕНО: создавать "ДОПОЛНЕНИЯ И УТОЧНЕНИЯ", добавлять в конец отдельным блоком

## CHANGES.md (обязательно при каждом /apply)
Файл: `PROJECT_[NAME]/CHANGES/FM-[NAME]-v[X.Y.Z]-CHANGES.md`
1. Заголовок с датой, агентом, задачей
2. Таблица изменений (ID, Где, Было, Стало, Причина)
3. Не примененные изменения (LOW) с причинами
4. Результат верификации

## JSON-сайдкар (_summary.json)
Обязательные поля: agent, command, timestamp (ISO 8601), fmVersion (X.Y.Z), project, status.
Схема: `schemas/agent-contracts.json`.

Структура `counts` по типу агента:
- Agent 1/2/4/5: `{"critical": N, "high": N, "medium": N, "low": N, "total": N}`
- Agent 3: `{"total": N, "accepted": N, "rejected": N, "backlog": N}`
- Agent 6: `{"presentations": N, "summaries": N, "total": N}`
- Agent 7: `{"pages_updated": N, "version_number": N}`
- Agent 8: `{"diagrams": N, "processes": N, "uploaded": N}`

## Автосохранение
После каждой команды обновлять `PROJECT_[NAME]/PROJECT_CONTEXT.md`.
НЕ спрашивать "сохранить?" - СОХРАНЯТЬ ВСЕГДА.
