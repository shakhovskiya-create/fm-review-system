#!/bin/bash
# Hook: Stop
# Логирует завершение сессии агента в logs/sessions.log

set -euo pipefail
INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S)

LOG_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}/logs"
mkdir -p "$LOG_DIR"

echo "${TIMESTAMP} | session=${SESSION_ID} | stopped" >> "$LOG_DIR/sessions.log"

exit 0
