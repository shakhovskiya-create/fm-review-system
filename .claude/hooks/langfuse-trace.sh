#!/bin/bash
# Hook: Stop
# Sends Claude Code session trace to Langfuse for cost/usage tracking.
# Runs Python tracer in background to avoid blocking the hook timeout.

INPUT=$(cat)

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PYTHON="${PROJECT_DIR}/.venv/bin/python3"
TRACER="${PROJECT_DIR}/scripts/lib/langfuse_tracer.py"

# Skip if tracer missing
[ -f "$TRACER" ] || exit 0

# Load environment variables
[ -f "${PROJECT_DIR}/.env" ] && set -a && source "${PROJECT_DIR}/.env" && set +a

# Skip if Langfuse not configured
[ -z "$LANGFUSE_PUBLIC_KEY" ] && exit 0

# Run tracer in background (non-blocking)
echo "$INPUT" | "$PYTHON" "$TRACER" &>/dev/null &
disown

exit 0
