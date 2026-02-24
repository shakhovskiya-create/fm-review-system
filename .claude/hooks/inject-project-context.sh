#!/bin/bash
# Hook: SessionStart
# Инжектирует краткий контекст активных проектов при старте/возобновлении сессии.
# Выводит в stdout: имя проекта, версия ФМ, PAGE_ID.
# Также подсказывает про Knowledge Graph (server-memory MCP).

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

echo "=== FM Review System: Active Projects ==="

for project_dir in "$PROJECT_DIR"/projects/PROJECT_*/; do
  [ -d "$project_dir" ] || continue

  project_name=$(basename "$project_dir")

  # PAGE_ID
  page_id=""
  if [ -f "$project_dir/CONFLUENCE_PAGE_ID" ]; then
    page_id=$(cat "$project_dir/CONFLUENCE_PAGE_ID" | tr -d '[:space:]')
  fi

  # FM version from PROJECT_CONTEXT.md
  fm_version=""
  if [ -f "$project_dir/PROJECT_CONTEXT.md" ]; then
    fm_version=$(grep -oP 'Версия ФМ:\s*\K[0-9]+\.[0-9]+\.[0-9]+' "$project_dir/PROJECT_CONTEXT.md" 2>/dev/null | head -1 || true)
  fi

  echo "- projects/$project_name | FM: ${fm_version:-N/A} | PAGE_ID: ${page_id:-N/A}"
done

# Knowledge Graph: auto-seed if empty (LOW-P4)
MEMORY_FILE="$PROJECT_DIR/.claude-memory/memory.jsonl"
if [ ! -f "$MEMORY_FILE" ] || [ ! -s "$MEMORY_FILE" ]; then
  if [ -f "$PROJECT_DIR/scripts/seed_memory.py" ]; then
    python3 "$PROJECT_DIR/scripts/seed_memory.py" 2>/dev/null || true
  fi
fi
if [ -f "$MEMORY_FILE" ]; then
  entity_count=$(grep -c '"name"' "$MEMORY_FILE" 2>/dev/null || echo 0)
  echo "- Knowledge Graph: ${entity_count} entities (use mcp__memory__search_nodes)"
fi

# Progress file hint
CONTEXT_FILE="$PROJECT_DIR/CONTEXT.md"
if [ -f "$CONTEXT_FILE" ]; then
  echo "- Progress: CONTEXT.md exists (read for session continuity)"
fi

# Определяем repo динамически
REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || echo "")

if [ -n "$REPO" ]; then
  # GitHub Issues: открытые задачи оркестратора
  issues=$(gh issue list --repo "$REPO" \
    --label "agent:orchestrator" --state open --limit 10 \
    --json number,title,labels \
    --jq '.[] | "  #\(.number): \(.title) [\([.labels[].name | select(startswith("status:") or startswith("sprint:"))] | join(", "))]"' 2>/dev/null || true)
  if [ -n "$issues" ]; then
    echo "- GitHub Issues (orchestrator):"
    echo "$issues"
  fi

  # Sprint summary
  sprint_info=$(gh issue list --repo "$REPO" \
    --state open --limit 100 --json labels \
    --jq '[.[].labels[].name | select(startswith("sprint:"))] | group_by(.) | map({sprint: .[0], count: length}) | .[] | "\(.sprint): \(.count) open"' 2>/dev/null || true)
  if [ -n "$sprint_info" ]; then
    echo "- Sprints: $sprint_info"
  fi
fi

echo "========================================="

exit 0
