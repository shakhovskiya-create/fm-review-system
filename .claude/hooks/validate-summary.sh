#!/usr/bin/env bash
# Hook: SubagentStop - validate _summary.json creation after agent completion
# Fires after custom agents (agent-0..16) complete their work.
# Checks that the agent created a _summary.json file per FC-07A protocol.
# Also queues summary for Graphiti ingestion via queue-graphiti-episode.sh.
#
# Environment:
#   CLAUDE_PROJECT_DIR - project root directory
#
# Exit codes:
#   0 - agent handled issues properly (or agent is excluded from enforcement)
#   2 - BLOCK: agent didn't create or didn't close Jira tasks

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
JIRA_BASE_URL="https://jira.ekf.su"
JIRA_PROJECT="EKFLAB"

# Загрузка JIRA_PAT (Infisical → env → .env)
_load_jira_pat() {
  if [ -n "${JIRA_PAT:-}" ]; then return 0; fi

  if [ -f "$PROJECT_DIR/scripts/lib/secrets.sh" ]; then
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/scripts/lib/secrets.sh"
    if _infisical_universal_auth "$PROJECT_DIR" 2>/dev/null; then
      JIRA_PAT=$(infisical secrets get JIRA_PAT --projectId="${INFISICAL_PROJECT_ID}" --env=dev --plain 2>/dev/null || true)
      if [ -n "$JIRA_PAT" ]; then export JIRA_PAT; return 0; fi
    fi
  fi

  if [ -f "$PROJECT_DIR/.env" ]; then
    JIRA_PAT=$(grep -E '^JIRA_PAT=' "$PROJECT_DIR/.env" | cut -d= -f2- | tr -d '"' || true)
    if [ -n "$JIRA_PAT" ]; then export JIRA_PAT; return 0; fi
  fi

  return 1
}

# Find active project directories
found_warning=false

for project_dir in "$PROJECT_DIR"/projects/PROJECT_*/; do
    [ -d "$project_dir" ] || continue

    # Check each AGENT_* directory for recent _summary.json
    for agent_dir in "$project_dir"AGENT_*/; do
        [ -d "$agent_dir" ] || continue

        # Look for _summary.json files modified in the last 10 minutes
        recent=$(find "$agent_dir" -maxdepth 1 -name "*_summary.json" -mmin -10 2>/dev/null | head -1)

        if [ -n "$recent" ]; then
            # Validate JSON structure (minimal check)
            if command -v python3 &>/dev/null; then
                valid=$(python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    required = ['agent', 'command', 'timestamp', 'status']
    missing = [k for k in required if k not in data]
    if missing:
        print(f'WARN: Missing fields in _summary.json: {missing}')
        sys.exit(1)
    print('OK')
except Exception as e:
    print(f'WARN: Invalid _summary.json: {e}')
    sys.exit(1)
" "$recent" 2>&1)
                if [ $? -ne 0 ]; then
                    echo "$valid"
                    found_warning=true
                fi
            fi

            # Queue summary for Graphiti ingestion (non-blocking)
            QUEUE_SCRIPT="$PROJECT_DIR/scripts/queue-graphiti-episode.sh"
            if [ -x "$QUEUE_SCRIPT" ]; then
                "$QUEUE_SCRIPT" "$recent" 2>/dev/null || true
            fi
        fi
    done
done

# No recent summaries found is not an error - the agent may not have
# produced output that requires a summary (e.g., simple queries).

# Jira Tasks: BLOCKING enforcement (exit 2 = блокирует завершение агента)
INPUT=$(cat <&0 2>/dev/null || echo "")
AGENT_NAME=$(echo "$INPUT" | jq -r '.subagent_name // empty' 2>/dev/null || true)
BLOCK=false

if [ -n "$AGENT_NAME" ]; then
    AGENT_LABEL=""
    case "$AGENT_NAME" in
        agent-*)  AGENT_LABEL=$(echo "$AGENT_NAME" | sed 's/^agent-//') ;;
        helper-*) AGENT_LABEL="orchestrator" ;;
    esac

    if [ -n "$AGENT_LABEL" ]; then
        # Загрузка PAT
        if ! _load_jira_pat; then
            echo "WARNING: JIRA_PAT не найден. Пропускаю проверку задач Jira."
            exit 0
        fi

        # 1. Проверка: есть ли вообще задачи у агента?
        JQL_ALL="project = ${JIRA_PROJECT} AND labels = \"agent:${AGENT_LABEL}\""
        all_json=$(timeout 5 curl -s -G \
            -H "Authorization: Bearer $JIRA_PAT" \
            --data-urlencode "jql=${JQL_ALL}" \
            --data-urlencode "fields=summary" \
            --data-urlencode "maxResults=1" \
            "${JIRA_BASE_URL}/rest/api/2/search" 2>/dev/null || echo "__ERR__")

        # Graceful degradation
        if [ "$all_json" = "__ERR__" ] || [ -z "$all_json" ]; then
            echo "WARNING: Jira API недоступен. Пропускаю проверку задач."
            exit 0
        fi

        all_count=$(echo "$all_json" | jq '.total // 0' 2>/dev/null || echo "0")

        if [ "$all_count" -eq 0 ] 2>/dev/null; then
            echo "WARNING: Агент ${AGENT_NAME} не имеет ни одной задачи в Jira с меткой agent:${AGENT_LABEL}."
            echo "Рекомендация: создавай задачу при старте (правило 26)."
            echo "  bash scripts/jira-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '...'"
        fi

        # 2. Проверка: нет ли ОТКРЫТЫХ задач у агента?
        JQL_OPEN="project = ${JIRA_PROJECT} AND labels = \"agent:${AGENT_LABEL}\" AND statusCategory != Done"
        open_json=$(timeout 5 curl -s -G \
            -H "Authorization: Bearer $JIRA_PAT" \
            --data-urlencode "jql=${JQL_OPEN}" \
            --data-urlencode "fields=summary,status" \
            --data-urlencode "maxResults=20" \
            "${JIRA_BASE_URL}/rest/api/2/search" 2>/dev/null || echo "[]")

        open_count=$(echo "$open_json" | jq '.total // 0' 2>/dev/null || echo "0")

        if [ "$open_count" -gt 0 ] 2>/dev/null; then
            echo "BLOCKED: У агента ${AGENT_NAME} есть ${open_count} незакрытых задач в Jira:"
            echo ""
            echo "$open_json" | jq -r '.issues[] | "  \(.key): \(.fields.summary)"' 2>/dev/null || true
            echo ""
            echo "Закрой КАЖДУЮ через: bash scripts/jira-tasks.sh done EKFLAB-N --comment 'Результат + DoD'"
            echo ""
            echo "ОБЯЗАТЕЛЬНЫЙ формат --comment (DoD, правило 27):"
            echo "  ## Результат"
            echo "  [Что сделано]"
            echo "  ## Было -> Стало"
            echo "  - [Изменение]"
            echo "  ## DoD"
            echo "  - [x] Tests pass"
            echo "  - [x] No regression"
            echo "  - [x] AC met"
            echo "  - [x] Artifacts: [файлы]"
            echo "  - [x] Docs updated (N/A)"
            echo "  - [x] No hidden debt"
            BLOCK=true
        fi
    fi
fi

if [ "$BLOCK" = true ]; then
    echo ""
    echo "Хук SubagentStop заблокировал завершение. Выполни действия выше и повтори."
    exit 2
fi

exit 0
