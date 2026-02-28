#!/usr/bin/env bash
# Hook: PreToolUse -> Bash
# Блокирует авто-закрытие GitHub Issues через commit message.
# GitHub автоматически закрывает issues при push, если коммит содержит
# "Closes #N", "Fixes #N", "Resolves #N" — это обходит gh-tasks.sh done
# и DoD checklist.
#
# Разрешено: "Refs #N", "Part of #N", "Related to #N", "See #N"
# Exit 2 = block.

set -euo pipefail
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")

# Skip if no command
[ -z "$COMMAND" ] && exit 0

# Only check git commit commands
if ! echo "$COMMAND" | grep -qE '(^|&&|\|\||;|\|)\s*git\s+commit'; then
    exit 0
fi

# Extract the commit message from -m "..." or heredoc
# Pattern: Closes/Close/Closed/Fix/Fixes/Fixed/Resolve/Resolves/Resolved #N
# Case-insensitive check across the full command (message is inline)
if echo "$COMMAND" | grep -qiE '(close[sd]?|fix(e[sd])?|resolve[sd]?)\s+#[0-9]+'; then
    echo "BLOCKED: Коммит содержит 'Closes/Fixes/Resolves #N' — GitHub автозакроет issue без DoD." >&2
    echo "" >&2
    echo "Используйте 'Refs #N' в commit message, затем закройте через:" >&2
    echo "  scripts/gh-tasks.sh done <N> --comment \"...DoD...\"" >&2
    echo "" >&2
    echo "Это гарантирует DoD checklist и artifact cross-check." >&2
    exit 2
fi

exit 0
