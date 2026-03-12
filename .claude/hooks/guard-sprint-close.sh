#!/usr/bin/env bash
# Hook: PreToolUse -> Bash
# БЛОКИРУЕТ закрытие спринта без Sprint Completion Protocol.
#
# Перехватывает:
#   - Jira sprint API: POST /rest/agile/1.0/sprint/ с state=closed
#   - jira-tasks.sh sprint-close
#
# Проверяет наличие маркер-файла .sprint-completion-done
# который создаётся ТОЛЬКО после полного прохождения протокола.
#
# Exit 2 = block.

set -euo pipefail
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")

# Skip if no command
[ -z "$COMMAND" ] && exit 0

# Detect sprint close attempts
IS_SPRINT_CLOSE=false

# Pattern 1: jira-tasks.sh sprint-close
if echo "$COMMAND" | grep -qE 'jira-tasks\.sh\s+sprint-close'; then
    IS_SPRINT_CLOSE=true
fi

# Pattern 2: Jira Agile API with state=closed
if echo "$COMMAND" | grep -qE '/rest/agile/.*sprint.*' && echo "$COMMAND" | grep -qiE '"state"\s*:\s*"closed"'; then
    IS_SPRINT_CLOSE=true
fi

# Pattern 3: curl to sprint endpoint with closed
if echo "$COMMAND" | grep -qE 'curl.*sprint.*closed'; then
    IS_SPRINT_CLOSE=true
fi

if ! $IS_SPRINT_CLOSE; then
    exit 0
fi

# Check for completion marker
MARKER_FILE="/home/dev/projects/claude-agents/fm-review-system/.sprint-completion-done"

if [ -f "$MARKER_FILE" ]; then
    # Marker exists — allow and remove it (one-time use)
    rm -f "$MARKER_FILE"
    exit 0
fi

echo "BLOCKED: Закрытие спринта без Sprint Completion Protocol." >&2
echo "" >&2
echo "Обязательные шаги ПЕРЕД закрытием:" >&2
echo "" >&2
echo "  === Первый проход — техническая проверка ===" >&2
echo "  1. go build ./... && go test ./... — 0 failures" >&2
echo "  2. gh run list --limit 1 — CI green" >&2
echo "  3. jira-tasks.sh list --sprint N — 0 open issues" >&2
echo "  4. Все артефакты спринта существуют" >&2
echo "  5. Xray: Test Plan + Test Execution (если есть тесты)" >&2
echo "" >&2
echo "  === Второй проход — моделирование ===" >&2
echo "  6. Представить реального разработчика/пользователя — сможет работать?" >&2
echo "  7. Cross-check: deliverables vs AC из issues" >&2
echo "  8. Бизнес-линза: ускоряет или замедляет продажи?" >&2
echo "" >&2
echo "  === Финализация ===" >&2
echo "  9. Обновить многоуровневую память (MEMORY.md + MCP + Graphiti + RAG)" >&2
echo "  10. Git commit + push + CI green" >&2
echo "" >&2
echo "Запустите проверку:" >&2
echo "  scripts/sprint-completion.sh --sprint N" >&2
echo "" >&2
echo "Скрипт создаст маркер ТОЛЬКО если все автоматические проверки пройдены." >&2
echo "" >&2
echo "Правило: План jaunty-wibbling-ember.md → Sprint Completion Protocol" >&2
exit 2
