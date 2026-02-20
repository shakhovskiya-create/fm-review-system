---
name: run-pipeline
description: "Запуск полного конвейера агентов для проекта. /run-pipeline PROJECT_NAME"
disable-model-invocation: true
allowed-tools: Bash, Read
---

# /run-pipeline — запуск конвейера

Запустить полный pipeline агентов для указанного проекта.

## Использование

```bash
cd /home/dev/projects/claude-agents/fm-review-system && python3 scripts/run_agent.py --pipeline --project $ARGUMENTS
```

Перед запуском прочитать `workflows/PIPELINE_AUTO.md` для контекста.

Если аргумент не указан — показать список доступных проектов из `projects/`.
