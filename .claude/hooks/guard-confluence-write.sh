#!/bin/bash
# Hook: PreToolUse -> Bash
# Проверяет что перед записью в Confluence (publish_to_confluence.py) вызван Quality Gate.
# Блокирует прямые curl PUT к Confluence API без скрипта.

set -euo pipefail
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")

# Пропускаем если нет команды или jq не установлен
[ -z "$COMMAND" ] && exit 0

# Блокируем прямой curl PUT к Confluence (должен использоваться скрипт)
if echo "$COMMAND" | grep -qiE 'curl.*-X\s*PUT.*confluence'; then
  echo "BLOCKED: Прямой curl PUT к Confluence запрещен. Используйте scripts/publish_to_confluence.py или src/fm_review/confluence_utils.py" >&2
  "${CLAUDE_PROJECT_DIR:-$(pwd)}/scripts/notify.sh" --level ERROR --event "confluence_write_blocked" --message "Direct curl PUT to Confluence blocked by guard hook" 2>/dev/null || true
  exit 2
fi

exit 0
