#!/usr/bin/env bash
# Hook: PreToolUse -> Write, Edit
# Блокирует запись секретов (API-ключи, токены) в файлы.
# Проверяет content (Write) и new_string (Edit) на паттерны секретов.

set -euo pipefail

INPUT=$(cat)

# Извлекаем текст для проверки: content (Write) или new_string (Edit)
TEXT=$(echo "$INPUT" | jq -r '(.tool_input.content // "") + "\n" + (.tool_input.new_string // "")' 2>/dev/null || echo "")

[ -z "$TEXT" ] && exit 0

# Паттерны секретов (regex):
# sk-ant-         : Anthropic API keys
# ghp_/gho_/ghs_  : GitHub tokens
# xox[bpras]-     : Slack tokens
# AKIA             : AWS access keys
# sk-lf-/pk-lf-   : Langfuse secret/public keys
# \d{10}:AA       : Telegram bot tokens
# PRIVATE KEY      : PEM private keys
PATTERNS='(sk-ant-[A-Za-z0-9_-]{20,}'
PATTERNS+='|ghp_[A-Za-z0-9]{36,}|gho_[A-Za-z0-9]{36,}|ghs_[A-Za-z0-9]{36,}'
PATTERNS+='|xox[bpras]-[A-Za-z0-9-]{20,}'
PATTERNS+='|AKIA[A-Z0-9]{16}'
PATTERNS+='|sk-lf-[A-Za-z0-9]{20,}|pk-lf-[A-Za-z0-9]{20,}'
PATTERNS+='|[0-9]{8,10}:AA[A-Za-z0-9_-]{33,}'
PATTERNS+='|-----BEGIN (RSA |EC )?PRIVATE KEY-----)'

if echo "$TEXT" | grep -qE "$PATTERNS"; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // "unknown"' 2>/dev/null || echo "unknown")
  echo "BLOCKED: Обнаружен секрет (API-ключ/токен) в записи в файл '$FILE_PATH'. Секреты должны храниться в Infisical, не в файлах." >&2
  exit 2
fi

exit 0
