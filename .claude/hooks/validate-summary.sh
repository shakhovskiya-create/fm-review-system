#!/usr/bin/env bash
# Hook: SubagentStop - validate _summary.json creation after agent completion
# Fires after custom agents (agent-0..8) complete their work.
# Checks that the agent created a _summary.json file per FC-07A protocol.
#
# Environment:
#   CLAUDE_PROJECT_DIR - project root directory
#
# Exit codes:
#   0 - always (warning only, does not block)

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

# GitHub Issues: напоминание обновить issues + DoD enforcement
INPUT=$(cat <&0 2>/dev/null || echo "")
AGENT_NAME=$(echo "$INPUT" | jq -r '.subagent_name // empty' 2>/dev/null || true)
if [ -n "$AGENT_NAME" ]; then
    AGENT_LABEL=""
    case "$AGENT_NAME" in
        agent-*)  AGENT_LABEL=$(echo "$AGENT_NAME" | sed 's/^agent-//') ;;
        helper-*) AGENT_LABEL="orchestrator" ;;
    esac
    if [ -n "$AGENT_LABEL" ]; then
        open_issues=$(gh issue list --repo shakhovskiya-create/fm-review-system \
            --label "agent:${AGENT_LABEL}" --label "status:in-progress" \
            --state open --json number --jq 'length' 2>/dev/null || echo "0")
        if [ "$open_issues" -gt 0 ] 2>/dev/null; then
            echo "WARNING: У агента ${AGENT_NAME} есть ${open_issues} незакрытых issues со status:in-progress."
            echo "Закрой через: bash scripts/gh-tasks.sh done <N> --comment 'Результат + DoD'"
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
        fi
    fi
fi

exit 0
