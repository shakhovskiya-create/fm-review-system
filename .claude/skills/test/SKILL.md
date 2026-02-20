---
name: test
description: "Запуск тестов проекта. /test [фильтр] — pytest с опциональной фильтрацией по -k."
disable-model-invocation: true
allowed-tools: Bash
---

# /test — запуск тестов

Запустить тесты проекта fm-review-system.

## Без аргументов

```bash
cd /home/dev/projects/claude-agents/fm-review-system && pytest tests/ -v --tb=short
```

## С аргументами (фильтр)

```bash
cd /home/dev/projects/claude-agents/fm-review-system && pytest tests/ -v --tb=short -k "$ARGUMENTS"
```

Показать результат пользователю. При ошибках — предложить исправление.
