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

        # 1. Проверка: агент СОЗДАЛ хотя бы одну задачу?
        # Ищем все issues с меткой этого агента (open + closed, за последний час)
        all_issues=$(gh issue list --repo "$REPO" \
            --label "agent:${AGENT_LABEL}" --state all --limit 50 \
            --json number,createdAt,state,labels \
            --jq '[.[] | select(
                (.createdAt | fromdateiso8601) > (now - 3600)
            )] | length' 2>/dev/null || echo "-1")

        # Если gh недоступен — не блокируем (graceful degradation)
        if [ "$all_issues" = "-1" ]; then
            echo "WARNING: Не удалось проверить GitHub Issues (gh CLI недоступен). Пропускаю."
            exit 0
        fi

        if [ "$all_issues" -eq 0 ] 2>/dev/null; then
            echo "BLOCKED: Агент ${AGENT_NAME} НЕ создал ни одной GitHub Issue."
            echo ""
            echo "Правило 26: каждый агент ОБЯЗАН создать задачу при старте."
            echo "Создай задачу и закрой её с DoD:"
            echo "  bash scripts/gh-tasks.sh create --title '...' --agent ${AGENT_LABEL} --sprint <N> --body '## Образ результата\n...\n## Acceptance Criteria\n- [ ] AC1'"
            echo "  bash scripts/gh-tasks.sh start <N>"
            echo "  bash scripts/gh-tasks.sh done <N> --comment '## Результат\n...\n## DoD\n- [x] Tests pass\n- [x] AC met\n- [x] Artifacts: [файлы]\n- [x] No hidden debt'"
            BLOCK=true
        fi

        # 2. Проверка: нет ли незакрытых in-progress задач?
        open_issues=$(gh issue list --repo "$REPO" \
            --label "agent:${AGENT_LABEL}" --label "status:in-progress" \
            --state open --json number --jq 'length' 2>/dev/null || echo "0")

        if [ "$open_issues" -gt 0 ] 2>/dev/null; then
            echo "BLOCKED: У агента ${AGENT_NAME} есть ${open_issues} незакрытых issues со status:in-progress."
            echo ""
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
