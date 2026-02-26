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

  context="${context}Project: projects/$project_name | FM: ${fm_version:-N/A} | PAGE_ID: ${page_id:-N/A}\n"
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
  # Write marker for guard hooks (agent write scope, etc.)
  echo "$AGENT_NAME" > "$PROJECT_DIR/.claude/.current-subagent"

  # Извлекаем номер/имя агента: agent-0-creator -> 0-creator, helper-architect -> orchestrator
  AGENT_LABEL=""
  case "$AGENT_NAME" in
    agent-*)  AGENT_LABEL=$(echo "$AGENT_NAME" | sed 's/^agent-//') ;;
    helper-*) AGENT_LABEL="orchestrator" ;;
  esac
  if [ -n "$AGENT_LABEL" ]; then
    REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || echo "")
    if [ -z "$REPO" ]; then
      echo "WARNING: Не удалось определить GitHub repo. GitHub Issues недоступны."
      exit 0
    fi
    issues=$(gh issue list --repo "$REPO" \
      --label "agent:${AGENT_LABEL}" --state open --limit 10 \
      --json number,title,labels \
      --jq '.[] | "#\(.number): \(.title) [\([.labels[].name | select(startswith("status:") or startswith("priority:"))] | join(", "))]"' 2>/dev/null || true)

    echo ""
    echo "=== GitHub Issues (ОБЯЗАТЕЛЬНО, правило 26+29) ==="
    if [ -n "$issues" ]; then
      echo "Твои задачи:"
      echo "$issues"
      echo ""
      echo "ДЕЙСТВИЯ:"
      echo "  1. Возьми задачу: bash scripts/gh-tasks.sh start <N>"
      echo "  2. По завершении закрой: bash scripts/gh-tasks.sh done <N> --comment 'Результат + DoD'"
      echo "  3. Составная задача? Декомпозируй: --parent N (правило 29)"
      echo "============================================="
    else
      echo "BLOCKED: Нет задач для agent:${AGENT_LABEL}."
      echo ""
      echo "СОЗДАЙ задачу ПЕРЕД началом работы:"
      echo "  bash scripts/gh-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '...'"
      echo ""
      echo "Составная задача (2+ шагов)? Создай epic + подзадачи (--parent N, правило 29)."
      echo "============================================="
      exit 2
    fi
  fi
fi

exit 0
