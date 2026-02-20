#!/bin/bash
# Hook: PreToolUse -> mcp__confluence__confluence_update_page, mcp__confluence__confluence_delete_page
# Блокирует прямые MCP write-вызовы к Confluence.
# Все записи должны идти через scripts/publish_to_confluence.py (lock + backup + retry).

set -euo pipefail

echo "BLOCKED: Прямая запись в Confluence через MCP запрещена. Используйте scripts/publish_to_confluence.py (lock + backup + retry + audit log)." >&2
exit 2
