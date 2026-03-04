#!/bin/bash
# Hook: Stop
# Sends Claude Code session trace to Langfuse for cost/usage tracking.
# Runs Python tracer in background to avoid blocking the hook timeout.

set -euo pipefail
INPUT=$(cat)

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PYTHON="${PROJECT_DIR}/.venv/bin/python3"
TRACER="${PROJECT_DIR}/src/fm_review/langfuse_tracer.py"

# Skip if tracer missing
[ -f "$TRACER" ] || exit 0

# Load secrets if not already set
if [ -z "${LANGFUSE_PUBLIC_KEY:-}" ]; then
    if [ -f "$PROJECT_DIR/scripts/load-secrets.sh" ]; then
        source "$PROJECT_DIR/scripts/load-secrets.sh" 2>/dev/null || true
    fi
fi

# Skip if Langfuse still not configured
[ -z "${LANGFUSE_PUBLIC_KEY:-}" ] && exit 0

# Run tracer in background (non-blocking)
echo "$INPUT" | "$PYTHON" "$TRACER" &>/dev/null &
disown

exit 0
