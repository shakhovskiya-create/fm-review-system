#!/bin/bash
# PreCompact hook: сохраняет критический контекст перед компакцией.
# Вызывается автоматически перед сжатием контекстного окна.
# Вход: JSON на stdin (session_id, trigger, transcript_path).
# Выход: stdout инжектируется как system message после компакции.

set -euo pipefail

INPUT=$(cat)
TRIGGER=$(echo "$INPUT" | jq -r '.trigger // "auto"')
PROJECT_DIR=$(echo "$INPUT" | jq -r '.cwd // ""')

# Определяем активный проект
ACTIVE_PROJECT=""
for dir in "$PROJECT_DIR"/projects/PROJECT_*/; do
  [ -d "$dir" ] || continue
  ACTIVE_PROJECT=$(basename "$dir")
  break
done

# Собираем критический контекст для переноса через компакцию
echo "=== Context preserved before compaction ($TRIGGER) ==="

# 1. Активный проект и PAGE_ID
if [ -n "$ACTIVE_PROJECT" ]; then
  PROJECT_PATH="$PROJECT_DIR/projects/$ACTIVE_PROJECT"
  echo "Project: $ACTIVE_PROJECT"

  if [ -f "$PROJECT_PATH/CONFLUENCE_PAGE_ID" ]; then
    echo "PAGE_ID: $(cat "$PROJECT_PATH/CONFLUENCE_PAGE_ID")"
  fi

  # FM version из PROJECT_CONTEXT.md
  if [ -f "$PROJECT_PATH/PROJECT_CONTEXT.md" ]; then
    FM_VER=$(grep -oP 'v\d+\.\d+\.\d+' "$PROJECT_PATH/PROJECT_CONTEXT.md" 2>/dev/null | tail -1)
    [ -n "$FM_VER" ] && echo "FM version: $FM_VER"
  fi
fi

# 2. Progress file (CONTEXT.md)
if [ -f "$PROJECT_DIR/CONTEXT.md" ]; then
  echo ""
  echo "--- Progress (CONTEXT.md) ---"
  head -50 "$PROJECT_DIR/CONTEXT.md"
fi

# 3. Knowledge Graph hint
MEMORY_FILE="$PROJECT_DIR/.claude-memory/memory.jsonl"
if [ -f "$MEMORY_FILE" ]; then
  entity_count=$(grep -c '"name"' "$MEMORY_FILE" 2>/dev/null || echo 0)
  echo ""
  echo "Knowledge Graph: ${entity_count} entities (use mcp__memory__search_nodes)"
fi

echo "==========================================="
