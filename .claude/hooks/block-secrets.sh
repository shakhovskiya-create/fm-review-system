#!/bin/bash
# Hook: PreToolUse -> Write, Edit
# Блокирует запись секретов (API-ключи, токены) в файлы.
# Проверяет content (Write) и new_string (Edit) на паттерны секретов.

set -euo pipefail

INPUT=$(cat)

# Извлекаем текст для проверки: content (Write) или new_string (Edit)
TEXT=$(echo "$INPUT" | jq -r '(.tool_input.content // "") + "\n" + (.tool_input.new_string // "")' 2>/dev/null || echo "")

[ -z "$TEXT" ] && exit 0

# Паттерны секретов (regex)
# sk-ant- : Anthropic API keys
# ghp_/gho_/ghs_ : GitHub tokens
# xox[bpras]- : Slack tokens
# eyJ : JWT tokens (base64 JSON)
# AKIA : AWS access keys
# Явные присваивания секретов: KEY=value (не placeholder)
if echo "$TEXT" | grep -qE '(sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36,}|gho_[A-Za-z0-9]{36,}|ghs_[A-Za-z0-9]{36,}|xox[bpras]-[A-Za-z0-9-]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (RSA |EC )?PRIVATE KEY-----)'; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // "unknown"' 2>/dev/null || echo "unknown")
  echo "BLOCKED: Обнаружен секрет (API-ключ/токен) в записи в файл '$FILE_PATH'. Секреты должны храниться в Infisical, не в файлах." >&2
  exit 2
fi

exit 0
