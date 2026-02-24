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
| `guard-mcp-confluence-write.sh` | PreToolUse (MCP confluence write/delete) | Блокирует прямую MCP-запись в Confluence |
| `block-secrets.sh` | PreToolUse (Write, Edit) | Блокирует запись секретов (API-ключей, токенов) в файлы |
| `validate-xhtml-style.sh` | PostToolUse (Bash) | Проверяет XHTML стили и отсутствие AI-упоминаний |
| `validate-summary.sh` | SubagentStop (agent-.*) | **BLOCKING (exit 2):** валидация _summary.json + проверка GitHub Issues (создание + закрытие) |
| `session-log.sh` | Stop | Логирует завершение сессии |
| `auto-save-context.sh` | Stop | Обновляет timestamp в PROJECT_CONTEXT.md |
| `langfuse-trace.sh` | Stop | Трейсинг сессии для Langfuse |
| `precompact-save-context.sh` | PreCompact | Сохраняет контекст + предупреждает о переполнении контекстного окна |
