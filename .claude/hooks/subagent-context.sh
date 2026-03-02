#!/bin/bash
# Hook: SubagentStart
# Инжектирует краткий контекст проекта при запуске кастомного субагента (agent-0..16).
# Matcher: agent-.* (только наши агенты, не системные).
#
# БЛОКИРУЮЩАЯ ПРОВЕРКА: агент не может начать работу без задачи в Jira status:В работе.
# Whitelist: helper-architect (инфра-агент), --skip-issue-check в prompt.
# Graceful degradation: если Jira API недоступен — не блокируем (exit 0 с WARNING).

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
JIRA_BASE_URL="https://jira.ekf.su"
JIRA_PROJECT="EKFLAB"

# Загрузка JIRA_PAT (Infisical → env → .env)
_load_jira_pat() {
  if [ -n "${JIRA_PAT:-}" ]; then return 0; fi

  # Попробовать Infisical
  if [ -f "$PROJECT_DIR/scripts/lib/secrets.sh" ]; then
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/scripts/lib/secrets.sh"
    if _infisical_universal_auth "$PROJECT_DIR" 2>/dev/null; then
      JIRA_PAT=$(infisical secrets get JIRA_PAT --projectId="${INFISICAL_PROJECT_ID}" --env=dev --plain 2>/dev/null || true)
      if [ -n "$JIRA_PAT" ]; then export JIRA_PAT; return 0; fi
    fi
  fi

  # Попробовать .env
  if [ -f "$PROJECT_DIR/.env" ]; then
    JIRA_PAT=$(grep -E '^JIRA_PAT=' "$PROJECT_DIR/.env" | cut -d= -f2- | tr -d '"' || true)
    if [ -n "$JIRA_PAT" ]; then export JIRA_PAT; return 0; fi
  fi

  return 1
}

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

# Jira Tasks: задачи назначенные этому агенту + блокирующая проверка status:В работе
INPUT=$(cat <&0 2>/dev/null || echo "")
AGENT_NAME=$(echo "$INPUT" | jq -r '.subagent_name // empty' 2>/dev/null || true)
AGENT_PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || true)
if [ -n "$AGENT_NAME" ]; then
  # Write marker for guard hooks (agent write scope, etc.)
  echo "$AGENT_NAME" > "$PROJECT_DIR/.claude/.current-subagent"

  # Извлекаем номер/имя агента: agent-0-creator -> 0-creator, helper-architect -> orchestrator
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
    # Загрузка PAT
    if ! _load_jira_pat; then
      echo "WARNING: JIRA_PAT не найден. Проверка задач Jira пропущена."
      exit 0
    fi

    # Получаем открытые задачи для агента через Jira REST API
    JQL="project = ${JIRA_PROJECT} AND labels = \"agent:${AGENT_LABEL}\" AND statusCategory != Done"
    issues_json=$(timeout 5 curl -s -G \
      -H "Authorization: Bearer $JIRA_PAT" \
      -H "Content-Type: application/json" \
      --data-urlencode "jql=${JQL}" \
      --data-urlencode "fields=summary,status,priority,labels" \
      --data-urlencode "maxResults=15" \
      "${JIRA_BASE_URL}/rest/api/2/search" 2>/dev/null || echo "__JIRA_ERROR__")

    # Graceful degradation: Jira API недоступен — не блокируем
    if [ "$issues_json" = "__JIRA_ERROR__" ] || [ -z "$issues_json" ]; then
      echo "WARNING: Jira API недоступен или таймаут. Проверка задач пропущена."
      exit 0
    fi

    # Проверяем ошибку JQL
    jira_errors=$(echo "$issues_json" | jq -r '.errorMessages[0] // empty' 2>/dev/null || true)
    if [ -n "$jira_errors" ]; then
      echo "WARNING: Jira JQL ошибка: $jira_errors. Проверка задач пропущена."
      exit 0
    fi

    # Парсим задачи
    issues_total=$(echo "$issues_json" | jq '.total // 0' 2>/dev/null || echo "0")
    issues_in_progress=$(echo "$issues_json" | jq '[.issues[] | select(.fields.status.name == "В работе")] | length' 2>/dev/null || echo "0")
    issues_formatted=$(echo "$issues_json" | jq -r '.issues[] | "\(.key): \(.fields.summary) [\(.fields.status.name), \(.fields.priority.name)]"' 2>/dev/null || true)

    echo ""
    echo "=== Jira Tasks (ОБЯЗАТЕЛЬНО, правило 26+29) ==="

    if [ "$issues_total" -eq 0 ] 2>/dev/null; then
      # Нет задач вообще
      if [ "$SKIP_ISSUE_CHECK" = true ]; then
        echo "WARNING: Нет задач для agent:${AGENT_LABEL}. Рекомендуется создать задачу."
        echo ""
        echo "  bash scripts/jira-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '...'"
        echo "============================================="
      else
        echo "BLOCK: Нет задачи в Jira со статусом 'В работе' для agent:${AGENT_LABEL}."
        echo ""
        echo "Создай задачу через jira-tasks.sh create + start перед началом работы:"
        echo "  1. bash scripts/jira-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '...'"
        echo "  2. bash scripts/jira-tasks.sh start EKFLAB-N"
        echo ""
        echo "Составная задача (2+ шагов)? Создай epic + подзадачи (--parent EKFLAB-N, правило 29)."
        echo "============================================="
        exit 2
      fi

    elif [ "$issues_in_progress" -eq 0 ] 2>/dev/null; then
      # Есть задачи, но ни одна не в статусе "В работе"
      echo "Твои задачи:"
      echo "$issues_formatted"
      echo ""
      if [ "$SKIP_ISSUE_CHECK" = true ]; then
        echo "WARNING: Ни одна задача не имеет статус 'В работе'. Рекомендуется взять задачу:"
        echo "  bash scripts/jira-tasks.sh start EKFLAB-N"
        echo "============================================="
      else
        echo "BLOCK: Нет задачи в Jira со статусом 'В работе'. Возьми задачу перед началом работы."
        echo ""
        echo "Возьми одну из задач выше:"
        echo "  bash scripts/jira-tasks.sh start EKFLAB-N"
        echo ""
        echo "Или создай новую:"
        echo "  bash scripts/jira-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '...'"
        echo "============================================="
        exit 2
      fi

    else
      # Есть задачи в статусе "В работе" — пропускаем
      echo "Твои задачи:"
      echo "$issues_formatted"
      echo ""
      echo "ДЕЙСТВИЯ:"
      echo "  1. Работай над задачей со статусом 'В работе'"
      echo "  2. По завершении закрой: bash scripts/jira-tasks.sh done EKFLAB-N --comment 'Результат + DoD'"
      echo "  3. Составная задача? Декомпозируй: --parent EKFLAB-N (правило 29)"
      echo "============================================="
    fi
  fi
fi

exit 0
