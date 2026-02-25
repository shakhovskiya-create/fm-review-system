#!/bin/bash
# Hook: PreToolUse -> mcp__confluence__confluence_update_page, mcp__confluence__confluence_delete_page
# Blocks direct MCP write calls to Confluence EXCEPT from Agent 7 (Publisher).
# All other agents must use scripts/publish_to_confluence.py (lock + backup + retry).

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MARKER="$PROJECT_DIR/.claude/.current-subagent"

# Check if current agent is Agent 7 (publisher)
if [ -f "$MARKER" ]; then
  CURRENT_AGENT=$(cat "$MARKER" 2>/dev/null || echo "")
  if [[ "$CURRENT_AGENT" == "agent-7-publisher" ]]; then
    exit 0  # Agent 7 is allowed to write directly
  fi
fi

echo "BLOCKED: Прямая запись в Confluence через MCP запрещена. Используйте scripts/publish_to_confluence.py (lock + backup + retry + audit log). Только Agent 7 (Publisher) может использовать MCP напрямую." >&2
exit 2
