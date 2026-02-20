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

# Skip if Langfuse not configured (env vars injected by load-secrets.sh)
[ -z "${LANGFUSE_PUBLIC_KEY:-}" ] && exit 0

# Run tracer in background (non-blocking)
echo "$INPUT" | "$PYTHON" "$TRACER" &>/dev/null &
disown

exit 0
