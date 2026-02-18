---
name: quality-gate
description: "Проверка готовности проекта перед публикацией в Confluence. Запускает quality_gate.sh и анализирует результаты."
allowed-tools: "Bash, Read, Grep, Glob"
---

# Quality Gate - проверка готовности

## Запуск

```bash
bash scripts/quality_gate.sh [PROJECT_NAME]
```

## Обработка результатов

- **Exit code 0** - все проверки пройдены, можно публиковать
- **Exit code 1** - CRITICAL ошибки, публикация ЗАБЛОКИРОВАНА. Показать ошибки, предложить исправить.
- **Exit code 2** - предупреждения (WARN). Можно пропустить с `--reason "обоснование"`.

## Что проверяется (9 секций)

1. Структура проекта (README, CHANGES/)
2. Функциональная модель (наличие, версия)
3. Результаты агентов (AGENT_1..7, отчеты)
4. Открытые замечания (CRITICAL=блок, HIGH=предупреждение)
5. Сайдкары _summary.json
6. Матрица трассируемости
7. Журнал аудита Confluence
8. Документация (CHANGELOG.md)
9. Confluence (URL в PROJECT_CONTEXT.md)

## После проверки

Показать пользователю результат и предложить действие через AskUserQuestion.
