#!/bin/bash
# gh-tasks.sh — управление задачами через GitHub Issues
# Используется оркестратором и агентами для persistent task tracking.
#
# Usage:
#   gh-tasks.sh create --title "..." --agent 1-architect --sprint 13 [--priority high] [--type infra] [--body "..."]
#   gh-tasks.sh start <issue_number>          # status:planned -> status:in-progress
#   gh-tasks.sh done <issue_number> [--comment "..."]   # close issue
#   gh-tasks.sh block <issue_number> --reason "..."      # status:blocked
#   gh-tasks.sh list [--agent X] [--sprint N] [--status S]
#   gh-tasks.sh my-tasks --agent X            # open tasks for agent
#   gh-tasks.sh sprint [N]                    # sprint dashboard

set -euo pipefail

REPO="shakhovskiya-create/fm-review-system"

_usage() {
    echo "Usage: gh-tasks.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  create   --title '...' --agent <name> --sprint <N> [--priority P] [--type T] [--body '...']"
    echo "  start    <issue_number>"
    echo "  done     <issue_number> [--comment '...']"
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

    local labels="agent:${agent},sprint:${sprint},priority:${priority},type:${type},status:planned"

    local args=(--repo "$REPO" --title "$title" --label "$labels")
    [[ -n "$body" ]] && args+=(--body "$body")

    gh issue create "${args[@]}"
}

cmd_start() {
    local issue="${1:?ERROR: issue number required}"
    _remove_status_labels "$issue"
    gh issue edit "$issue" --repo "$REPO" --add-label "status:in-progress"
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

    _remove_status_labels "$issue"
    [[ -n "$comment" ]] && gh issue comment "$issue" --repo "$REPO" --body "$comment"
    gh issue close "$issue" --repo "$REPO"
    echo "Issue #${issue}: closed"
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
