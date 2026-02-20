---
paths:
  - ".claude/hooks/**"
  - ".claude/settings.json"
---

# Hooks (автоматизация)

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
