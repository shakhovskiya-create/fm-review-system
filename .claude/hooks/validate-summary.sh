#!/usr/bin/env bash
# Hook: SubagentStop - validate _summary.json creation after agent completion
# Fires after custom agents (agent-0..8) complete their work.
# Checks that the agent created a _summary.json file per FC-07A protocol.
#
# Environment:
#   CLAUDE_PROJECT_DIR - project root directory
#
# Exit codes:
#   0 - agent handled issues properly (or agent is excluded from enforcement)
#   2 - BLOCK: agent didn't create or didn't close GitHub Issues

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

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
        fi
    done
done

# No recent summaries found is not an error - the agent may not have
# produced output that requires a summary (e.g., simple queries).

# GitHub Issues: BLOCKING enforcement (exit 2 = блокирует завершение агента)
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
        # Определяем repo из текущего git remote (не хардкодим)
        REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || echo "")
        if [ -z "$REPO" ]; then
            echo "WARNING: Не удалось определить GitHub repo. Пропускаю проверку Issues."
            exit 0
        fi

        # 1. Проверка: агент СОЗДАЛ или РАБОТАЛ с задачами?
        # Ищем ВСЕ issues с меткой этого агента (open + closed)
        all_issues_json=$(gh issue list --repo "$REPO" \
            --label "agent:${AGENT_LABEL}" --state all --limit 50 \
            --json number 2>/dev/null || echo "ERR")

        # Если gh недоступен — не блокируем (graceful degradation)
        if [ "$all_issues_json" = "ERR" ]; then
            echo "WARNING: Не удалось проверить GitHub Issues (gh CLI недоступен). Пропускаю."
            exit 0
        fi

        all_issues_count=$(echo "$all_issues_json" | jq 'length' 2>/dev/null || echo "0")

        if [ "$all_issues_count" -eq 0 ] 2>/dev/null; then
            echo "WARNING: Агент ${AGENT_NAME} не имеет ни одной GitHub Issue с меткой agent:${AGENT_LABEL}."
            echo "Рекомендация: создавай задачу при старте (правило 26)."
            echo "  bash scripts/gh-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '...'"
        fi

        # 2. Проверка: нет ли ЛЮБЫХ незакрытых задач у агента?
        # Ищем ВСЕ open issues (любой status:), не только in-progress
        open_issues_json=$(gh issue list --repo "$REPO" \
            --label "agent:${AGENT_LABEL}" \
            --state open --limit 20 \
            --json number,title 2>/dev/null || echo "[]")
        open_count=$(echo "$open_issues_json" | jq 'length' 2>/dev/null || echo "0")

        if [ "$open_count" -gt 0 ] 2>/dev/null; then
            echo "BLOCKED: У агента ${AGENT_NAME} есть ${open_count} незакрытых GitHub Issues:"
            echo ""
            echo "$open_issues_json" | jq -r '.[] | "  #\(.number): \(.title)"' 2>/dev/null || true
            echo ""
            echo "Закрой КАЖДУЮ через: bash scripts/gh-tasks.sh done <N> --comment 'Результат + DoD'"
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
