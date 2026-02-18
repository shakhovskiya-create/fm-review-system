#!/bin/bash
# Hook: SubagentStart
# Инжектирует краткий контекст проекта при запуске кастомного субагента (agent-0..8).
# Matcher: agent-.* (только наши агенты, не системные).

set -e

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Собираем контекст активных проектов
context=""
for project_dir in "$PROJECT_DIR"/projects/PROJECT_*/; do
  [ -d "$project_dir" ] || continue

  project_name=$(basename "$project_dir")

  page_id=""
  if [ -f "$project_dir/CONFLUENCE_PAGE_ID" ]; then
    page_id=$(cat "$project_dir/CONFLUENCE_PAGE_ID" | tr -d '[:space:]')
  fi

  fm_version=""
  if [ -f "$project_dir/PROJECT_CONTEXT.md" ]; then
    fm_version=$(grep -oP 'Версия ФМ:\s*\K[0-9]+\.[0-9]+\.[0-9]+' "$project_dir/PROJECT_CONTEXT.md" 2>/dev/null | head -1)
  fi

  context="${context}Project: $project_name | FM: ${fm_version:-N/A} | PAGE_ID: ${page_id:-N/A}\n"
done

if [ -n "$context" ]; then
  echo "$context"
fi

exit 0
