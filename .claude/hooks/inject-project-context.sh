#!/bin/bash
# Hook: SessionStart
# Инжектирует краткий контекст активных проектов при старте/возобновлении сессии.
# Выводит в stdout: имя проекта, версия ФМ, PAGE_ID.

set -e

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
    fm_version=$(grep -oP 'Версия ФМ:\s*\K[0-9]+\.[0-9]+\.[0-9]+' "$project_dir/PROJECT_CONTEXT.md" 2>/dev/null | head -1)
  fi

  echo "- $project_name | FM: ${fm_version:-N/A} | PAGE_ID: ${page_id:-N/A}"
done

echo "========================================="

exit 0
