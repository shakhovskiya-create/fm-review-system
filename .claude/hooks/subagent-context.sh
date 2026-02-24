#!/bin/bash
# Hook: SubagentStart
# Инжектирует краткий контекст проекта при запуске кастомного субагента (agent-0..8).
# Matcher: agent-.* (только наши агенты, не системные).

set -euo pipefail

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
    fm_version=$(grep -oP 'Версия ФМ:\s*\K[0-9]+\.[0-9]+\.[0-9]+' "$project_dir/PROJECT_CONTEXT.md" 2>/dev/null | head -1 || true)
  fi

  context="${context}Project: $project_name | FM: ${fm_version:-N/A} | PAGE_ID: ${page_id:-N/A}\n"
done

if [ -n "$context" ]; then
  echo "$context"
fi

# Knowledge Graph: подсказка субагентам
MEMORY_FILE="$PROJECT_DIR/.claude-memory/memory.jsonl"
if [ -f "$MEMORY_FILE" ]; then
  echo "Knowledge Graph available: use mcp__memory__search_nodes to find entities, decisions, findings."
fi

# GitHub Issues: задачи назначенные этому агенту
INPUT=$(cat <&0 2>/dev/null || echo "")
AGENT_NAME=$(echo "$INPUT" | jq -r '.subagent_name // empty' 2>/dev/null || true)
if [ -n "$AGENT_NAME" ]; then
  # Извлекаем номер/имя агента: agent-0-creator -> 0-creator, helper-architect -> orchestrator
  AGENT_LABEL=""
  case "$AGENT_NAME" in
    agent-*)  AGENT_LABEL=$(echo "$AGENT_NAME" | sed 's/^agent-//') ;;
    helper-*) AGENT_LABEL="orchestrator" ;;
  esac
  if [ -n "$AGENT_LABEL" ]; then
    issues=$(gh issue list --repo shakhovskiya-create/fm-review-system \
      --label "agent:${AGENT_LABEL}" --state open --limit 10 \
      --json number,title,labels \
      --jq '.[] | "#\(.number): \(.title) [\([.labels[].name | select(startswith("status:") or startswith("priority:"))] | join(", "))]"' 2>/dev/null || true)
    if [ -n "$issues" ]; then
      echo ""
      echo "GitHub Issues (назначены тебе):"
      echo "$issues"
    fi
  fi
fi

exit 0
