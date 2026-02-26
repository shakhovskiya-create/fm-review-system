#!/usr/bin/env bash
# gh-tasks.sh — управление задачами через GitHub Issues
# Используется оркестратором и агентами для persistent task tracking.
#
# Usage:
#   gh-tasks.sh create --title "..." --agent 1-architect --sprint 13 --body "..." [--priority high] [--type T] [--parent N]
#   gh-tasks.sh start    <issue_number>           # status:planned -> status:in-progress
#   gh-tasks.sh done     <issue_number> --comment "..."  # close issue (comment REQUIRED)
#   gh-tasks.sh block    <issue_number> --reason "..."   # status:blocked
#   gh-tasks.sh list     [--agent X] [--sprint N] [--status S]
#   gh-tasks.sh my-tasks --agent <name>           # open tasks for agent
#   gh-tasks.sh sprint   [N]                      # sprint dashboard
#   gh-tasks.sh children <epic_number>            # list child issues of an epic

set -euo pipefail

REPO="${GH_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "shakhovskiya-create/fm-review-system")}"
PROJECT_OWNER="${REPO%%/*}"
PROJECT_NUM=1

# Cache project metadata (avoids repeated API calls within one script run)
_PROJECT_ID=""
_STATUS_FIELD_ID=""

_get_project_id() {
    if [ -z "$_PROJECT_ID" ]; then
        _PROJECT_ID=$(gh project list --owner "$PROJECT_OWNER" --format json \
            --jq ".projects[] | select(.number == $PROJECT_NUM) | .id" 2>/dev/null || true)
    fi
    echo "$_PROJECT_ID"
}

_get_status_field_id() {
    if [ -z "$_STATUS_FIELD_ID" ]; then
        _STATUS_FIELD_ID=$(gh project field-list "$PROJECT_NUM" --owner "$PROJECT_OWNER" --format json \
            --jq '.fields[] | select(.name == "Status") | .id' 2>/dev/null || true)
    fi
    echo "$_STATUS_FIELD_ID"
}

# Синхронизация статуса в GitHub Project Kanban
# Maps: "Todo" = Planned, "In Progress", "Done"
_sync_project_status() {
    local issue_num="$1" target_status="$2"
    local project_id field_id option_id item_id

    project_id=$(_get_project_id)
    [ -z "$project_id" ] && return 0

    field_id=$(_get_status_field_id)
    [ -z "$field_id" ] && return 0

    # Find item by issue number (numeric comparison)
    item_id=$(gh project item-list "$PROJECT_NUM" --owner "$PROJECT_OWNER" --format json \
        --jq ".items[] | select(.content.number == ${issue_num}) | .id" 2>/dev/null || true)
    [ -z "$item_id" ] && return 0

    # Find option ID for target status
    option_id=$(gh project field-list "$PROJECT_NUM" --owner "$PROJECT_OWNER" --format json \
        --jq ".fields[] | select(.name == \"Status\") | .options[] | select(.name == \"${target_status}\") | .id" 2>/dev/null || true)
    [ -z "$option_id" ] && return 0

    gh project item-edit --project-id "$project_id" \
        --id "$item_id" --field-id "$field_id" --single-select-option-id "$option_id" 2>/dev/null || true
}

_usage() {
    echo "Usage: gh-tasks.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  create   --title '...' --agent <name> --sprint <N> --body '...' [--priority P] [--type T] [--parent N]"
    echo "  start    <issue_number>"
    echo "  done     <issue_number> --comment '...'   (REQUIRED: DoD + результат)"
    echo "  block    <issue_number> --reason '...'"
    echo "  list     [--agent X] [--sprint N] [--status S]"
    echo "  my-tasks --agent <name>"
    echo "  sprint   [N]"
    echo "  children <epic_number>                    (list child tasks of an epic)"
    exit 1
}

_remove_status_labels() {
    local issue="$1"
    for s in planned in-progress blocked; do
        gh issue edit "$issue" --repo "$REPO" --remove-label "status:$s" 2>/dev/null || true
    done
}

cmd_create() {
    local title="" agent="" sprint="" priority="medium" type="infra" body="" parent=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title)    title="$2"; shift 2 ;;
            --agent)    agent="$2"; shift 2 ;;
            --sprint)   sprint="$2"; shift 2 ;;
            --priority) priority="$2"; shift 2 ;;
            --type)     type="$2"; shift 2 ;;
            --body)     body="$2"; shift 2 ;;
            --parent)   parent="$2"; shift 2 ;;
            *) echo "Unknown option: $1"; exit 1 ;;
        esac
    done

    [[ -z "$title" ]] && { echo "ERROR: --title required"; exit 1; }
    [[ -z "$agent" ]] && { echo "ERROR: --agent required"; exit 1; }
    [[ -z "$sprint" ]] && { echo "ERROR: --sprint required"; exit 1; }
    [[ -z "$body" ]] && { echo "ERROR: --body required (образ результата + Acceptance Criteria)"; echo "Template: '## Образ результата\n...\n## Acceptance Criteria\n- [ ] AC1'"; exit 1; }

    # If parent specified, prepend "Part of #N" to body
    if [[ -n "$parent" ]]; then
        body="Part of #${parent}

${body}"
    fi

    local labels="agent:${agent},sprint:${sprint},priority:${priority},type:${type},status:planned"

    local args=(--repo "$REPO" --title "$title" --label "$labels")
    args+=(--body "$body")

    local url
    url=$(gh issue create "${args[@]}")
    local issue_num="${url##*/}"
    echo "$url"

    # Добавляем в Project board + ставим статус Todo
    gh project item-add "$PROJECT_NUM" --owner "$PROJECT_OWNER" --url "$url" 2>/dev/null || true
    _sync_project_status "$issue_num" "Todo"

    # If parent exists, add task-list reference to epic body
    if [[ -n "$parent" ]]; then
        _add_child_to_epic "$parent" "$issue_num" "$title"
    fi
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
    local comment="" force=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --comment) comment="$2"; shift 2 ;;
            --force)   force=true; shift ;;
            *) shift ;;
        esac
    done

    [[ -z "$comment" ]] && { echo "ERROR: --comment required (DoD checklist + результат)"; echo "Template: '## Результат\n...\n## DoD\n- [x] Tests pass\n- [x] AC met\n- [x] Artifacts: ...\n- [x] No hidden debt'"; exit 1; }

    # Pre-close check: uncommitted changes and unpushed commits
    if [[ "$force" != true ]]; then
        local dirty
        dirty=$(git status --porcelain 2>/dev/null | grep -v '^??' | head -5 || true)
        if [[ -n "$dirty" ]]; then
            echo "ERROR: Есть незакоммиченные изменения. Сначала закоммитьте."
            echo "$dirty"
            echo ""
            echo "Используйте --force для обхода (только для задач без кода)."
            exit 1
        fi

        local unpushed
        unpushed=$(git log @{u}..HEAD --oneline 2>/dev/null || true)
        if [[ -n "$unpushed" ]]; then
            echo "ERROR: Есть незапушенные коммиты. Сначала запушьте."
            echo "$unpushed"
            echo ""
            echo "Используйте --force для обхода (только для задач без кода)."
            exit 1
        fi
    fi

    # Cross-check: warn about changed files not mentioned in comment
    _validate_artifacts "$comment"

    # Epic check: if this issue has child tasks, all must be closed first
    local issue_labels
    issue_labels=$(gh issue view "$issue" --repo "$REPO" --json labels --jq '[.labels[].name] | join(",")' 2>/dev/null || true)
    if echo "$issue_labels" | grep -q "type:epic"; then
        if ! _check_epic_children "$issue"; then
            exit 1
        fi
    fi

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

# Add child issue reference to epic's body (task list)
_add_child_to_epic() {
    local epic="$1" child_num="$2" child_title="$3"
    local current_body
    current_body=$(gh issue view "$epic" --repo "$REPO" --json body --jq '.body' 2>/dev/null || true)
    [[ -z "$current_body" ]] && return 0

    # Append task list item
    local new_body="${current_body}
- [ ] #${child_num} ${child_title}"
    gh issue edit "$epic" --repo "$REPO" --body "$new_body" 2>/dev/null || true
}

# Check that all children of an epic are closed before allowing epic close
_check_epic_children() {
    local epic="$1"
    local body
    body=$(gh issue view "$epic" --repo "$REPO" --json body --jq '.body' 2>/dev/null || true)
    [[ -z "$body" ]] && return 0

    # Extract child issue numbers from "- [ ] #N" or "- [x] #N" patterns
    local child_nums
    child_nums=$(echo "$body" | grep -oP '#\K[0-9]+' | sort -u || true)
    [[ -z "$child_nums" ]] && return 0

    local open_children=()
    while IFS= read -r num; do
        [[ -z "$num" ]] && continue
        local state
        state=$(gh issue view "$num" --repo "$REPO" --json state --jq '.state' 2>/dev/null || true)
        if [[ "$state" == "OPEN" ]]; then
            local child_title
            child_title=$(gh issue view "$num" --repo "$REPO" --json title --jq '.title' 2>/dev/null || true)
            open_children+=("#${num}: ${child_title}")
        fi
    done <<< "$child_nums"

    if [[ ${#open_children[@]} -gt 0 ]]; then
        echo ""
        echo "ERROR: Нельзя закрыть epic #${epic} — есть незакрытые подзадачи:"
        for c in "${open_children[@]}"; do
            echo "  - $c"
        done
        echo ""
        echo "Сначала закройте подзадачи, потом epic."
        return 1
    fi
    return 0
}

cmd_children() {
    local epic="${1:?ERROR: epic issue number required}"
    local body
    body=$(gh issue view "$epic" --repo "$REPO" --json body,title --jq '.title + "\n" + .body' 2>/dev/null || true)
    [[ -z "$body" ]] && { echo "Issue #${epic} not found"; exit 1; }

    echo "=== Epic #${epic}: $(echo "$body" | head -1) ==="
    echo ""

    # Extract child issue numbers from body
    local child_nums
    child_nums=$(echo "$body" | grep -oP '(?<=#)\d+' | sort -un || true)
    [[ -z "$child_nums" ]] && { echo "No child issues found in epic body."; exit 0; }

    local total=0 done_count=0
    while IFS= read -r num; do
        [[ -z "$num" ]] && continue
        [[ "$num" == "$epic" ]] && continue  # skip self-references
        local info
        info=$(gh issue view "$num" --repo "$REPO" --json number,title,state,labels \
            --jq '"#\(.number) [\(.state)] \(.title) [\([.labels[].name | select(startswith("agent:") or startswith("status:"))] | join(", "))]"' 2>/dev/null || true)
        [[ -z "$info" ]] && continue
        echo "  $info"
        total=$((total + 1))
        if echo "$info" | grep -q "CLOSED"; then
            done_count=$((done_count + 1))
        fi
    done <<< "$child_nums"

    echo ""
    echo "Progress: ${done_count}/${total} done"
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
    _sync_project_status "$issue" "In Progress"  # blocked stays visible on board
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
    children) cmd_children "$@" ;;
    *)        _usage ;;
esac
