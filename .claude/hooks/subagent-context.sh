#!/bin/bash
# Hook: SubagentStart
# Инжектирует краткий контекст проекта при запуске кастомного субагента (agent-0..8).
# Matcher: agent-.* (только наши агенты, не системные).
#
# БЛОКИРУЮЩАЯ ПРОВЕРКА: агент не может начать работу без issue в status:in-progress.
# Whitelist: helper-architect (инфра-агент), --skip-issue-check в prompt.
# Graceful degradation: если GitHub API недоступен — не блокируем (exit 0 с WARNING).

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

# GitHub Issues: задачи назначенные этому агенту + блокирующая проверка status:in-progress
INPUT=$(cat <&0 2>/dev/null || echo "")
AGENT_NAME=$(echo "$INPUT" | jq -r '.subagent_name // empty' 2>/dev/null || true)
AGENT_PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || true)
if [ -n "$AGENT_NAME" ]; then
  # Write marker for guard hooks (agent write scope, etc.)
  echo "$AGENT_NAME" > "$PROJECT_DIR/.claude/.current-subagent"

  # Извлекаем номер/имя агента: agent-0-creator -> 0-creator, helper-architect -> orchestrator
  # Supports agents 0-15 including dev agents (11-dev-1c, 12-dev-go, 13-qa-1c, 14-qa-go, 15-trainer)
  AGENT_LABEL=""
  IS_ORCHESTRATOR=false
  case "$AGENT_NAME" in
    agent-*)  AGENT_LABEL=$(echo "$AGENT_NAME" | sed 's/^agent-//') ;;
    helper-*) AGENT_LABEL="orchestrator"; IS_ORCHESTRATOR=true ;;
  esac

  # Whitelist: helper-architect пропускается без блокировки (инфра-агент)
  # --skip-issue-check в промпте отключает блокировку для любого агента
  SKIP_ISSUE_CHECK=false
  if [ "$IS_ORCHESTRATOR" = true ]; then
    SKIP_ISSUE_CHECK=true
  fi
  if echo "$AGENT_PROMPT" | grep -q -- '--skip-issue-check' 2>/dev/null; then
    SKIP_ISSUE_CHECK=true
  fi

  if [ -n "$AGENT_LABEL" ]; then
    REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || echo "")
    if [ -z "$REPO" ]; then
      echo "WARNING: Не удалось определить GitHub repo. GitHub Issues недоступны."
      exit 0
    fi

    # Получаем все открытые issues для агента (одним запросом, парсим статусы в jq)
    issues_json=$(timeout 4 gh issue list --repo "$REPO" \
      --label "agent:${AGENT_LABEL}" --state open --limit 10 \
      --json number,title,labels 2>/dev/null || echo "__GH_ERROR__")

    # Graceful degradation: GitHub API недоступен — не блокируем
    if [ "$issues_json" = "__GH_ERROR__" ] || [ -z "$issues_json" ]; then
      echo "WARNING: GitHub API недоступен или таймаут. Проверка issues пропущена."
      exit 0
    fi

    # Парсим issues: все, in-progress, и форматированный список
    issues_total=$(echo "$issues_json" | jq 'length' 2>/dev/null || echo "0")
    issues_in_progress=$(echo "$issues_json" | jq '[.[] | select(.labels[].name == "status:in-progress")] | length' 2>/dev/null || echo "0")
    issues_formatted=$(echo "$issues_json" | jq -r '.[] | "#\(.number): \(.title) [\([.labels[].name | select(startswith("status:") or startswith("priority:"))] | join(", "))]"' 2>/dev/null || true)

    echo ""
    echo "=== GitHub Issues (ОБЯЗАТЕЛЬНО, правило 26+29) ==="

    if [ "$issues_total" -eq 0 ] 2>/dev/null; then
      # Нет issues вообще
      if [ "$SKIP_ISSUE_CHECK" = true ]; then
        echo "WARNING: Нет задач для agent:${AGENT_LABEL}. Рекомендуется создать задачу."
        echo ""
        echo "  bash scripts/gh-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '...'"
        echo "============================================="
      else
        echo "BLOCK: Нет задачи в GitHub Issues с status:in-progress для agent:${AGENT_LABEL}."
        echo ""
        echo "Создай задачу через gh-tasks.sh create + start перед началом работы:"
        echo "  1. bash scripts/gh-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '...'"
        echo "  2. bash scripts/gh-tasks.sh start <N>"
        echo ""
        echo "Составная задача (2+ шагов)? Создай epic + подзадачи (--parent N, правило 29)."
        echo "============================================="
        exit 2
      fi

    elif [ "$issues_in_progress" -eq 0 ] 2>/dev/null; then
      # Есть issues, но ни одна не в status:in-progress
      echo "Твои задачи:"
      echo "$issues_formatted"
      echo ""
      if [ "$SKIP_ISSUE_CHECK" = true ]; then
        echo "WARNING: Ни одна задача не имеет status:in-progress. Рекомендуется взять задачу:"
        echo "  bash scripts/gh-tasks.sh start <N>"
        echo "============================================="
      else
        echo "BLOCK: Нет задачи в GitHub Issues с status:in-progress. Создай задачу через gh-tasks.sh create + start перед началом работы."
        echo ""
        echo "Возьми одну из задач выше:"
        echo "  bash scripts/gh-tasks.sh start <N>"
        echo ""
        echo "Или создай новую:"
        echo "  bash scripts/gh-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '...'"
        echo "============================================="
        exit 2
      fi

    else
      # Есть issues в status:in-progress — пропускаем
      echo "Твои задачи:"
      echo "$issues_formatted"
      echo ""
      echo "ДЕЙСТВИЯ:"
      echo "  1. Работай над задачей status:in-progress"
      echo "  2. По завершении закрой: bash scripts/gh-tasks.sh done <N> --comment 'Результат + DoD'"
      echo "  3. Составная задача? Декомпозируй: --parent N (правило 29)"
      echo "============================================="
    fi
  fi
fi

exit 0
