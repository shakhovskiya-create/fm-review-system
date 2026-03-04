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

            # Auto-update memory layers (Layer 2: MCP Memory, Layer 3: Graphiti, Layer 4: RAG)
            MEMORY_SCRIPT="$PROJECT_DIR/scripts/update-memory.sh"
            if [ -x "$MEMORY_SCRIPT" ]; then
                # Extract agent name from directory path (AGENT_12_DEV_GO → agent-12-dev-go)
                agent_dir_name=$(basename "$agent_dir")
                agent_nice_name=$(echo "$agent_dir_name" | sed 's/^AGENT_/agent-/' | tr '[:upper:]' '[:lower:]' | tr '_' '-')
                "$MEMORY_SCRIPT" --agent "$agent_nice_name" --summary "$recent" 2>/dev/null || true
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

_agent_to_label() {
    case "$1" in
        0-creator|agent-0-creator) echo "creator" ;;
        1-architect|agent-1-architect) echo "architect" ;;
        2-simulator|agent-2-simulator) echo "simulator" ;;
        5-tech-architect|agent-5-tech-architect) echo "architect" ;;
        7-publisher|agent-7-publisher) echo "publisher" ;;
        8-bpmn-designer|agent-8-bpmn-designer) echo "bpmn" ;;
        9-se-go|agent-9-se-go) echo "se-go" ;;
        10-se-1c|agent-10-se-1c) echo "se-1c" ;;
        11-dev-1c|agent-11-dev-1c) echo "dev-1c" ;;
        12-dev-go|agent-12-dev-go) echo "dev-go" ;;
        13-qa-1c|agent-13-qa-1c) echo "qa-1c" ;;
        14-qa-go|agent-14-qa-go) echo "qa-go" ;;
        15-trainer|agent-15-trainer) echo "docs" ;;
        16-release-engineer|agent-16-release-engineer) echo "release" ;;
        orchestrator|helper-architect) echo "lead" ;;
        *) echo "$1" ;;
    esac
}

if [ -n "$AGENT_NAME" ]; then
    AGENT_LABEL=""
    case "$AGENT_NAME" in
        agent-*)  AGENT_LABEL=$(_agent_to_label "$AGENT_NAME") ;;
        helper-*) AGENT_LABEL="lead" ;;
    esac

    if [ -n "$AGENT_LABEL" ]; then
        # Загрузка PAT
        if ! _load_jira_pat; then
            echo "WARNING: JIRA_PAT не найден. Пропускаю проверку задач Jira."
            exit 0
        fi

        # 1. Проверка: есть ли вообще задачи у агента?
        JQL_ALL="project = ${JIRA_PROJECT} AND labels = \"${AGENT_LABEL}\""
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
            echo "WARNING: Агент ${AGENT_NAME} не имеет ни одной задачи в Jira с меткой ${AGENT_LABEL}."
            echo "Рекомендация: создавай задачу при старте (правило 26)."
            echo "  bash scripts/jira-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '...'"
        fi

        # 2. Проверка: нет ли ОТКРЫТЫХ задач у агента?
        JQL_OPEN="project = ${JIRA_PROJECT} AND labels = \"${AGENT_LABEL}\" AND statusCategory != Done"
        open_json=$(timeout 5 curl -s -G \
            -H "Authorization: Bearer $JIRA_PAT" \
            --data-urlencode "jql=${JQL_OPEN}" \
            --data-urlencode "fields=summary,status" \
            --data-urlencode "maxResults=20" \
            "${JIRA_BASE_URL}/rest/api/2/search" 2>/dev/null || echo "[]")

        open_count=$(echo "$open_json" | jq '.total // 0' 2>/dev/null || echo "0")

        if [ "$open_count" -gt 0 ] 2>/dev/null; then
            echo "====================================================================="
            echo "BLOCKED: ${open_count} НЕЗАКРЫТЫХ ЗАДАЧ у агента ${AGENT_NAME}!"
            echo "====================================================================="
            echo ""
            echo "Задачи которые НАДО ЗАКРЫТЬ ПРЯМО СЕЙЧАС:"
            echo ""
            echo "$open_json" | jq -r '.issues[] | "  bash scripts/jira-tasks.sh done \(.key) --comment \"Результат: ...\""' 2>/dev/null || true
            echo ""
            echo "ПРАВИЛО 26a: Закрой ВСЕ задачи ПЕРЕД завершением."
            echo "Сначала установи Smart Checklist, потом закрой задачу."
            echo "Оркестратор НЕ должен закрывать за тебя — это ТВОЯ ответственность."
            echo ""
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
