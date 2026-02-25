#!/bin/bash
# Hook: PreToolUse (Write, Edit)
# Checks that agent writes only to its own directory (AGENT_X_*/).
# Allows orchestrator (helper-architect) to write anywhere.
# Allows writes outside projects/ (system files, scripts, etc.).

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MARKER="$PROJECT_DIR/.claude/.current-subagent"

# No marker = orchestrator session, allow all
[ -f "$MARKER" ] || exit 0

CURRENT_AGENT=$(cat "$MARKER" 2>/dev/null || echo "")
[ -n "$CURRENT_AGENT" ] || exit 0

# Orchestrator (helper-architect) can write anywhere
[[ "$CURRENT_AGENT" == "helper-architect" ]] && exit 0

# Read tool input from stdin
INPUT=$(cat <&0 2>/dev/null || echo "")
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .file_path // empty' 2>/dev/null || true)
[ -n "$FILE_PATH" ] || exit 0

# Only check writes to projects/PROJECT_*/AGENT_*/ paths
if [[ "$FILE_PATH" == *"/projects/PROJECT_"*"/AGENT_"* ]]; then
  # Extract AGENT_N from path: projects/PROJECT_FOO/AGENT_1_ARCHITECT/file.md -> 1
  AGENT_NUM_IN_PATH=$(echo "$FILE_PATH" | grep -oP '/AGENT_\K[0-9]+' | head -1 || true)

  # Extract agent number from current agent name: agent-1-architect -> 1
  AGENT_NUM_CURRENT=$(echo "$CURRENT_AGENT" | grep -oP '^agent-\K[0-9]+' || true)

  if [ -n "$AGENT_NUM_IN_PATH" ] && [ -n "$AGENT_NUM_CURRENT" ]; then
    if [ "$AGENT_NUM_IN_PATH" != "$AGENT_NUM_CURRENT" ]; then
      echo "BLOCKED: Agent $CURRENT_AGENT is writing to AGENT_${AGENT_NUM_IN_PATH}_* directory. Agents can only write to their own directory." >&2
      exit 2
    fi
  fi
fi

exit 0
