#!/usr/bin/env bash
# Hook: PreToolUse -> Bash
# Блокирует деструктивные команды: rm -rf, git push --force, git reset --hard,
# git clean -f, git branch -D на protected ветках.
# Проверяет только команды на позиции выполнения (начало строки, после && ; || |),
# игнорирует упоминания в строковых аргументах/heredoc.
# Exit 2 = block.

set -euo pipefail
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")

# Skip if no command
[ -z "$COMMAND" ] && exit 0

# CMD_POS = command position anchor: start of line or after shell separator
CMD_POS='(^|&&|\|\||;|\|)\s*'

# --- rm -rf / (or rm -rf ~, rm -rf $HOME, etc.) ---
# Block rm -rf targeting root, home, or broad paths (only at command position)
if echo "$COMMAND" | grep -qE "${CMD_POS}rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|--recursive\s+--force|-[a-zA-Z]*f[a-zA-Z]*r)\s+(/\s|/\$|/home|/etc|/usr|/var|\\\$HOME|~|\.\.)"; then
  echo "BLOCKED: rm -rf на системные/корневые директории запрещён." >&2
  exit 2
fi

# --- git push --force (or -f) to main/master ---
if echo "$COMMAND" | grep -qE "${CMD_POS}git\s+push\s+.*(-f|--force|--force-with-lease).*\s+(main|master)(\s|$)"; then
  echo "BLOCKED: git push --force на main/master запрещён." >&2
  exit 2
fi

# --- git reset --hard ---
if echo "$COMMAND" | grep -qE "${CMD_POS}git\s+reset\s+--hard"; then
  echo "BLOCKED: git reset --hard запрещён. Используйте git stash или git checkout <file>." >&2
  exit 2
fi

# --- git clean -f (without dry-run) ---
if echo "$COMMAND" | grep -qE "${CMD_POS}git\s+clean\s+.*-[a-zA-Z]*f" && ! echo "$COMMAND" | grep -qE "${CMD_POS}git\s+clean\s+.*(-n|--dry-run)"; then
  echo "BLOCKED: git clean -f запрещён без --dry-run. Используйте git clean -n для предпросмотра." >&2
  exit 2
fi

# --- git branch -D on main/master ---
if echo "$COMMAND" | grep -qE "${CMD_POS}git\s+branch\s+-D\s+(main|master)(\s|$)"; then
  echo "BLOCKED: git branch -D main/master запрещён." >&2
  exit 2
fi

# --- git checkout . / git restore . (discard all changes) ---
if echo "$COMMAND" | grep -qE "${CMD_POS}git\s+(checkout|restore)\s+\.\s*$"; then
  echo "BLOCKED: Сброс всех изменений (git checkout ./restore .) запрещён. Используйте git stash." >&2
  exit 2
fi

exit 0
