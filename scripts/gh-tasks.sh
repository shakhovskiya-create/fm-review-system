#!/bin/bash
# gh-tasks.sh — управление задачами через GitHub Issues
# Используется оркестратором и агентами для persistent task tracking.
#
# Usage:
#   gh-tasks.sh create --title "..." --agent 1-architect --sprint 13 --body "..." [--priority high] [--type infra]
#   gh-tasks.sh start <issue_number>          # status:planned -> status:in-progress
#   gh-tasks.sh done <issue_number> --comment "..."      # close issue (comment REQUIRED)
#   gh-tasks.sh block <issue_number> --reason "..."      # status:blocked
#   gh-tasks.sh list [--agent X] [--sprint N] [--status S]
#   gh-tasks.sh my-tasks --agent X            # open tasks for agent
#   gh-tasks.sh sprint [N]                    # sprint dashboard

set -euo pipefail

REPO="shakhovskiya-create/fm-review-system"
PROJECT_OWNER="shakhovskiya-create"
PROJECT_NUM=1

# Синхронизация статуса в GitHub Project Kanban
_sync_project_status() {
    local issue_url="$1" target_status="$2"
    # Находим item ID в проекте
    local item_id
    item_id=$(gh project item-list "$PROJECT_NUM" --owner "$PROJECT_OWNER" --format json \
        --jq ".items[] | select(.content.number == ${issue_url}) | .id" 2>/dev/null || true)
    [ -z "$item_id" ] && return 0

    # Находим Status field ID и option ID
    local field_id option_id
    field_id=$(gh project field-list "$PROJECT_NUM" --owner "$PROJECT_OWNER" --format json \
        --jq '.fields[] | select(.name == "Status") | .id' 2>/dev/null || true)
    [ -z "$field_id" ] && return 0

    option_id=$(gh project field-list "$PROJECT_NUM" --owner "$PROJECT_OWNER" --format json \
        --jq ".fields[] | select(.name == \"Status\") | .options[] | select(.name == \"$target_status\") | .id" 2>/dev/null || true)
    [ -z "$option_id" ] && return 0

    gh project item-edit --project-id "$(gh project list --owner "$PROJECT_OWNER" --format json --jq ".projects[] | select(.number == $PROJECT_NUM) | .id")" \
        --id "$item_id" --field-id "$field_id" --single-select-option-id "$option_id" 2>/dev/null || true
}

_usage() {
    echo "Usage: gh-tasks.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  create   --title '...' --agent <name> --sprint <N> --body '...' [--priority P] [--type T]"
    echo "  start    <issue_number>"
    echo "  done     <issue_number> --comment '...'   (REQUIRED: DoD + результат)"
    echo "  block    <issue_number> --reason '...'"
    echo "  list     [--agent X] [--sprint N] [--status S]"
    echo "  my-tasks --agent <name>"
    echo "  sprint   [N]"
    exit 1
}

_remove_status_labels() {
    local issue="$1"
    for s in planned in-progress blocked; do
        gh issue edit "$issue" --repo "$REPO" --remove-label "status:$s" 2>/dev/null || true
    done
}

cmd_create() {
    local title="" agent="" sprint="" priority="medium" type="infra" body=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title)   title="$2"; shift 2 ;;
            --agent)   agent="$2"; shift 2 ;;
            --sprint)  sprint="$2"; shift 2 ;;
            --priority) priority="$2"; shift 2 ;;
            --type)    type="$2"; shift 2 ;;
            --body)    body="$2"; shift 2 ;;
            *) echo "Unknown option: $1"; exit 1 ;;
        esac
    done

    [[ -z "$title" ]] && { echo "ERROR: --title required"; exit 1; }
    [[ -z "$agent" ]] && { echo "ERROR: --agent required"; exit 1; }
    [[ -z "$sprint" ]] && { echo "ERROR: --sprint required"; exit 1; }
    [[ -z "$body" ]] && { echo "ERROR: --body required (образ результата + Acceptance Criteria)"; echo "Template: '## Образ результата\n...\n## Acceptance Criteria\n- [ ] AC1'"; exit 1; }

    local labels="agent:${agent},sprint:${sprint},priority:${priority},type:${type},status:planned"

    local args=(--repo "$REPO" --title "$title" --label "$labels")
    args+=(--body "$body")

    local url
    url=$(gh issue create "${args[@]}")
    echo "$url"

    # Добавляем в Project board
    gh project item-add "$PROJECT_NUM" --owner "$PROJECT_OWNER" --url "$url" 2>/dev/null || true
}

cmd_start() {
    local issue="${1:?ERROR: issue number required}"
    _remove_status_labels "$issue"
    gh issue edit "$issue" --repo "$REPO" --add-label "status:in-progress"
    _sync_project_status "$issue" "In Progress"
    echo "Issue #${issue}: status:in-progress"
}

cmd_done() {
    local issue="${1:?ERROR: issue number required}"
    shift
    local comment=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --comment) comment="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    [[ -z "$comment" ]] && { echo "ERROR: --comment required (DoD checklist + результат)"; echo "Template: '## Результат\n...\n## DoD\n- [x] Tests pass\n- [x] AC met\n- [x] Artifacts: ...\n- [x] No hidden debt'"; exit 1; }

    # Cross-check: warn about changed files not mentioned in comment
    _validate_artifacts "$comment"

    _remove_status_labels "$issue"
    gh issue comment "$issue" --repo "$REPO" --body "$comment"
    gh issue close "$issue" --repo "$REPO"
    _sync_project_status "$issue" "Done"
    echo "Issue #${issue}: closed"
}

# Validate that recently changed files are mentioned in the closing comment.
# Compares git diff with --comment text. Warns (does not block) on mismatches.
_validate_artifacts() {
    local comment="$1"
    local changed_files
    changed_files=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || true)
    [[ -z "$changed_files" ]] && return 0

    local missing=()
    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        # Extract basename for matching (agents/COMMON_RULES.md -> COMMON_RULES.md)
        local basename="${file##*/}"
        if ! echo "$comment" | grep -qF "$basename" && ! echo "$comment" | grep -qF "$file"; then
            missing+=("$file")
        fi
    done <<< "$changed_files"

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo ""
        echo "WARNING: Файлы из git diff НЕ упомянуты в --comment (DoD Artifacts):"
        for f in "${missing[@]}"; do
            echo "  - $f"
        done
        echo "Рекомендация: добавь их в секцию 'Artifacts' комментария."
        echo ""
    fi
}

cmd_block() {
    local issue="${1:?ERROR: issue number required}"
    shift
    local reason=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --reason) reason="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    _remove_status_labels "$issue"
    gh issue edit "$issue" --repo "$REPO" --add-label "status:blocked"
    [[ -n "$reason" ]] && gh issue comment "$issue" --repo "$REPO" --body "BLOCKED: $reason"
    echo "Issue #${issue}: status:blocked"
}

cmd_list() {
    local agent="" sprint="" status=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent)  agent="$2"; shift 2 ;;
            --sprint) sprint="$2"; shift 2 ;;
            --status) status="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    local args=(--repo "$REPO" --state open --limit 50)
    [[ -n "$agent" ]]  && args+=(--label "agent:${agent}")
    [[ -n "$sprint" ]] && args+=(--label "sprint:${sprint}")
    [[ -n "$status" ]] && args+=(--label "status:${status}")

    gh issue list "${args[@]}" --json number,title,labels,state \
        --jq '.[] | "#\(.number)\t\(.state)\t\(.title)\t\([.labels[].name | select(contains(":"))] | join(", "))"'
}

cmd_my_tasks() {
    local agent=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent) agent="$2"; shift 2 ;;
            *) shift ;;
        esac
    done
    [[ -z "$agent" ]] && { echo "ERROR: --agent required"; exit 1; }

    gh issue list --repo "$REPO" --label "agent:${agent}" --state open --limit 20 \
        --json number,title,labels \
        --jq '.[] | "#\(.number): \(.title) [\([.labels[].name | select(startswith("status:") or startswith("priority:"))] | join(", "))]"'
}

cmd_sprint() {
    local sprint="${1:-}"
    if [[ -z "$sprint" ]]; then
        # Auto-detect current sprint (highest number with open issues)
        sprint=$(gh issue list --repo "$REPO" --state open --limit 100 \
            --json labels --jq '[.[].labels[].name | select(startswith("sprint:")) | ltrimstr("sprint:")] | map(tonumber) | max // empty' 2>/dev/null)
        [[ -z "$sprint" ]] && { echo "No active sprint found"; exit 0; }
    fi

    echo "=== Sprint $sprint ==="
    echo ""

    echo "--- In Progress ---"
    gh issue list --repo "$REPO" --label "sprint:$sprint" --label "status:in-progress" --state open \
        --json number,title,labels \
        --jq '.[] | "  #\(.number): \(.title) [\([.labels[].name | select(startswith("agent:"))] | join(", "))]"' 2>/dev/null || true

    echo ""
    echo "--- Planned ---"
    gh issue list --repo "$REPO" --label "sprint:$sprint" --label "status:planned" --state open \
        --json number,title,labels \
        --jq '.[] | "  #\(.number): \(.title) [\([.labels[].name | select(startswith("agent:"))] | join(", "))]"' 2>/dev/null || true

    echo ""
    echo "--- Blocked ---"
    gh issue list --repo "$REPO" --label "sprint:$sprint" --label "status:blocked" --state open \
        --json number,title,labels \
        --jq '.[] | "  #\(.number): \(.title) [\([.labels[].name | select(startswith("agent:"))] | join(", "))]"' 2>/dev/null || true

    echo ""
    echo "--- Done ---"
    gh issue list --repo "$REPO" --label "sprint:$sprint" --state closed --limit 20 \
        --json number,title,labels \
        --jq '.[] | "  #\(.number): \(.title) [\([.labels[].name | select(startswith("agent:"))] | join(", "))]"' 2>/dev/null || true

    echo ""
    local total open closed
    total=$(gh issue list --repo "$REPO" --label "sprint:$sprint" --state all --limit 100 --json number --jq 'length' 2>/dev/null || echo 0)
    closed=$(gh issue list --repo "$REPO" --label "sprint:$sprint" --state closed --limit 100 --json number --jq 'length' 2>/dev/null || echo 0)
    open=$((total - closed))
    echo "Progress: ${closed}/${total} done, ${open} remaining"
}

# Main
[[ $# -eq 0 ]] && _usage

CMD="$1"
shift

case "$CMD" in
    create)   cmd_create "$@" ;;
    start)    cmd_start "$@" ;;
    done)     cmd_done "$@" ;;
    block)    cmd_block "$@" ;;
    list)     cmd_list "$@" ;;
    my-tasks) cmd_my_tasks "$@" ;;
    sprint)   cmd_sprint "$@" ;;
    *)        _usage ;;
esac
