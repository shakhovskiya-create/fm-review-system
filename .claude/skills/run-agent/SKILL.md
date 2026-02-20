---
name: run-agent
description: "Запуск конкретного агента. /run-agent AGENT_NUM PROJECT_NAME [COMMAND]"
disable-model-invocation: true
allowed-tools: Bash, Read
---

# /run-agent — запуск агента

Запустить конкретного агента для проекта.

## Использование

Аргументы: `AGENT_NUM PROJECT_NAME [COMMAND]`

```bash
cd /home/dev/projects/claude-agents/fm-review-system && python3 scripts/run_agent.py --agent $0 --project $1 --command "$2"
```

Примеры:
- `/run-agent 1 PROJECT_SHPMNT_PROFIT /audit`
- `/run-agent 2 PROJECT_SHPMNT_PROFIT /simulate-all`
- `/run-agent 5 PROJECT_SHPMNT_PROFIT /full`

Если аргументы не указаны — показать таблицу агентов и доступных проектов.
