#!/usr/bin/env bash
# jira-tasks.sh — управление задачами через Jira REST API
# Замена gh-tasks.sh. Используется оркестратором и агентами.
#
# Usage:
#   jira-tasks.sh create --title "..." --agent 1-architect --sprint 27 --body "..." [--priority high] [--type epic] [--parent EKFLAB-3]
#   jira-tasks.sh start    <EKFLAB-N>                    # Сделать -> В работе
#   jira-tasks.sh done     <EKFLAB-N> --comment "..."    # В работе -> Готово (comment REQUIRED)
#   jira-tasks.sh block    <EKFLAB-N> --reason "..."     # Add blocker comment
#   jira-tasks.sh list     [--agent X] [--sprint N] [--status S] [--product P]
#   jira-tasks.sh my-tasks --agent <name>                # Open tasks for agent
#   jira-tasks.sh sprint   [N]                           # Sprint dashboard
#   jira-tasks.sh children <EKFLAB-N>                    # List child tasks of an epic

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

JIRA_BASE="https://jira.ekf.su"
JIRA_PROJECT="EKFLAB"

# Custom field IDs (Jira Server)
SPRINT_FIELD="customfield_10104"
EPIC_NAME_FIELD="customfield_10102"
EPIC_LINK_FIELD="customfield_10100"

# Sprint IDs
declare -A SPRINT_IDS=(
    [27]=109 [28]=110 [29]=111 [30]=112 [31]=113
)

# Status transition IDs (Сделать -> В работе -> Готово)
# Will be discovered dynamically

# Priority mapping
declare -A PRIORITY_MAP=(
    [critical]="Highest" [high]="High" [medium]="Medium" [low]="Low"
)

# --- Auth ---
_get_pat() {
    # Priority 1: env var
    if [[ -n "${JIRA_PAT:-}" ]]; then
        echo "$JIRA_PAT"
        return
    fi
    # Priority 2: Infisical
    if [[ -f "${SCRIPT_DIR}/lib/secrets.sh" ]]; then
        # shellcheck disable=SC1091
        source "${SCRIPT_DIR}/lib/secrets.sh"
        if _infisical_universal_auth "$PROJECT_DIR" 2>/dev/null; then
            local pat
            pat=$(infisical secrets get JIRA_PAT \
                --projectId="${INFISICAL_PROJECT_ID}" --env=dev --plain 2>/dev/null || true)
            if [[ -n "$pat" ]]; then
                echo "$pat"
                return
            fi
        fi
    fi
    echo "ERROR: JIRA_PAT not found" >&2
    exit 1
}

_PAT=""
_pat() {
    if [[ -z "$_PAT" ]]; then
        _PAT=$(_get_pat)
    fi
    echo "$_PAT"
}

_jira_get() {
    curl -s -H "Authorization: Bearer $(_pat)" "$JIRA_BASE$1"
}

_jira_post() {
    curl -s -X POST -H "Authorization: Bearer $(_pat)" \
        -H "Content-Type: application/json" \
        "$JIRA_BASE$1" -d "$2"
}

_jira_put() {
    curl -s -o /dev/null -w "%{http_code}" -X PUT \
        -H "Authorization: Bearer $(_pat)" \
        -H "Content-Type: application/json" \
        "$JIRA_BASE$1" -d "$2"
}

# --- Transitions ---
_get_transition_id() {
    local issue_key="$1" target_status="$2"
    _jira_get "/rest/api/2/issue/${issue_key}/transitions" | python3 -c "
import sys,json
data = json.load(sys.stdin)
for t in data.get('transitions',[]):
    if t['to']['name'] == '${target_status}':
        print(t['id'])
        break
" 2>/dev/null
}

_transition_issue() {
    local issue_key="$1" target_status="$2"
    local tid
    tid=$(_get_transition_id "$issue_key" "$target_status")
    if [[ -z "$tid" ]]; then
        echo "ERROR: No transition to '${target_status}' for ${issue_key}" >&2
        return 1
    fi
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $(_pat)" \
        -H "Content-Type: application/json" \
        "$JIRA_BASE/rest/api/2/issue/${issue_key}/transitions" \
        -d "{\"transition\":{\"id\":\"${tid}\"}}")
    [[ "$http_code" == "204" ]] && return 0
    echo "ERROR: Transition failed (http=${http_code})" >&2
    return 1
}

# --- Commands ---
_usage() {
    echo "Usage: jira-tasks.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  create   --title '...' --agent <name> --sprint <N> --body '...' [--priority P] [--type T] [--parent EKFLAB-N]"
    echo "  start    <EKFLAB-N>"
    echo "  done     <EKFLAB-N> --comment '...'   (REQUIRED: DoD + результат)"
    echo "  block    <EKFLAB-N> --reason '...'"
    echo "  list     [--agent X] [--sprint N] [--status S] [--product P]"
    echo "  my-tasks --agent <name>"
    echo "  sprint   [N]"
    echo "  children <EKFLAB-N>                    (list child tasks of an epic)"
    exit 1
}

cmd_create() {
    local title="" agent="" sprint="" body="" priority="medium" issue_type="Задача" parent=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title) title="$2"; shift 2 ;;
            --agent) agent="$2"; shift 2 ;;
            --sprint) sprint="$2"; shift 2 ;;
            --body) body="$2"; shift 2 ;;
            --priority) priority="$2"; shift 2 ;;
            --type)
                case "$2" in
                    epic) issue_type="Epic" ;;
                    task|задача) issue_type="Задача" ;;
                    bug|ошибка) issue_type="Ошибка" ;;
                    story|история) issue_type="История" ;;
                    *) issue_type="$2" ;;
                esac
                shift 2 ;;
            --parent) parent="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    [[ -z "$title" ]] && { echo "ERROR: --title is required" >&2; exit 1; }
    [[ -z "$body" ]] && { echo "ERROR: --body is required (образ результата + AC)" >&2; exit 1; }

    # Build labels
    local labels="[\"product:profitability\""
    [[ -n "$agent" ]] && labels+=",\"agent:${agent}\""
    labels+="]"

    # Build fields
    local jira_priority="${PRIORITY_MAP[$priority]:-Medium}"
    local fields="{
        \"project\": {\"key\": \"${JIRA_PROJECT}\"},
        \"summary\": $(python3 -c "import json; print(json.dumps('$title'))"),
        \"issuetype\": {\"name\": \"${issue_type}\"},
        \"description\": $(python3 -c "import json; print(json.dumps('$body'))"),
        \"labels\": ${labels},
        \"priority\": {\"name\": \"${jira_priority}\"}
    "

    # Epic Name for Epic type
    if [[ "$issue_type" == "Epic" ]]; then
        fields+=",\"${EPIC_NAME_FIELD}\": $(python3 -c "import json; print(json.dumps('$title'))")"
    fi

    # Epic Link for child tasks
    if [[ -n "$parent" ]]; then
        fields+=",\"${EPIC_LINK_FIELD}\": \"${parent}\""
    fi

    # Sprint
    if [[ -n "$sprint" ]] && [[ -n "${SPRINT_IDS[$sprint]:-}" ]]; then
        fields+=",\"${SPRINT_FIELD}\": ${SPRINT_IDS[$sprint]}"
    fi

    fields+="}"

    local response
    response=$(_jira_post "/rest/api/2/issue" "{\"fields\": ${fields}}")

    local key
    key=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('key','ERROR'))" 2>/dev/null)

    if [[ "$key" == "ERROR" ]]; then
        echo "ERROR creating issue:" >&2
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response" >&2
        exit 1
    fi

    echo "$key"
    echo "Created: ${JIRA_BASE}/browse/${key}" >&2
}

cmd_start() {
    local issue_key="$1"
    [[ -z "$issue_key" ]] && { echo "ERROR: issue key required" >&2; exit 1; }

    # Add agent:in-progress label
    _jira_put "/rest/api/2/issue/${issue_key}" '{"update":{"labels":[{"add":"status:in-progress"}]}}'

    # Transition to В работе
    if _transition_issue "$issue_key" "В работе"; then
        echo "Started: ${issue_key} → В работе"
    else
        echo "WARNING: Could not transition ${issue_key} (may already be В работе)" >&2
    fi
}

cmd_done() {
    local issue_key="" comment=""

    issue_key="$1"; shift
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --comment) comment="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    [[ -z "$issue_key" ]] && { echo "ERROR: issue key required" >&2; exit 1; }
    [[ -z "$comment" ]] && { echo "ERROR: --comment is required (DoD checklist)" >&2; exit 1; }

    # Step 1: Add closing comment FIRST (before status change)
    _jira_post "/rest/api/2/issue/${issue_key}/comment" \
        "{\"body\": $(python3 -c "import json; print(json.dumps('$comment'))")}" > /dev/null

    # Step 2: Transition to Готово
    if _transition_issue "$issue_key" "Готово"; then
        echo "Done: ${issue_key} → Готово"
    else
        echo "ERROR: Could not close ${issue_key}" >&2
        exit 1
    fi

    # Step 3: Artifact cross-check
    local diff_files
    diff_files=$(git diff HEAD~1 --name-only 2>/dev/null || true)
    if [[ -n "$diff_files" ]]; then
        local missing=()
        while IFS= read -r f; do
            if ! echo "$comment" | grep -qF "$f"; then
                missing+=("$f")
            fi
        done <<< "$diff_files"
        if [[ ${#missing[@]} -gt 0 ]]; then
            echo "WARNING: Files in diff but NOT in comment:" >&2
            printf "  %s\n" "${missing[@]}" >&2
        fi
    fi
}

cmd_block() {
    local issue_key="" reason=""

    issue_key="$1"; shift
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --reason) reason="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    [[ -z "$issue_key" ]] && { echo "ERROR: issue key required" >&2; exit 1; }
    [[ -z "$reason" ]] && { echo "ERROR: --reason is required" >&2; exit 1; }

    # Add blocker comment
    _jira_post "/rest/api/2/issue/${issue_key}/comment" \
        "{\"body\": \"BLOCKED: ${reason}\"}" > /dev/null

    # Add blocked label
    _jira_put "/rest/api/2/issue/${issue_key}" '{"update":{"labels":[{"add":"status:blocked"}]}}'

    echo "Blocked: ${issue_key} — ${reason}"
}

cmd_list() {
    local agent="" sprint="" status="" product="profitability"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent) agent="$2"; shift 2 ;;
            --sprint) sprint="$2"; shift 2 ;;
            --status) status="$2"; shift 2 ;;
            --product) product="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    local jql="project = ${JIRA_PROJECT}"
    [[ -n "$product" ]] && jql+=" AND labels = \"product:${product}\""
    [[ -n "$agent" ]] && jql+=" AND labels = \"agent:${agent}\""
    [[ -n "$status" ]] && {
        case "$status" in
            planned|todo) jql+=" AND status = \"Сделать\"" ;;
            in-progress) jql+=" AND status = \"В работе\"" ;;
            done) jql+=" AND status = \"Готово\"" ;;
            *) jql+=" AND status = \"${status}\"" ;;
        esac
    }
    jql+=" ORDER BY key ASC"

    curl -s -H "Authorization: Bearer $(_pat)" \
        "${JIRA_BASE}/rest/api/2/search" \
        -G --data-urlencode "jql=${jql}" \
        --data-urlencode "maxResults=100" \
        --data-urlencode "fields=key,summary,status,issuetype,labels,priority" \
        | python3 -c "
import sys,json
data = json.load(sys.stdin)
issues = data.get('issues', [])
total = data.get('total', 0)
print(f'Total: {total}')
print(f'{\"Key\":>12} | {\"Type\":>8} | {\"Status\":>12} | {\"Priority\":>10} | Summary')
print('-' * 90)
for i in issues:
    f = i['fields']
    itype = f['issuetype']['name'][:8]
    status = f['status']['name'][:12]
    priority = f['priority']['name'][:10] if f.get('priority') else '-'
    print(f'{i[\"key\"]:>12} | {itype:>8} | {status:>12} | {priority:>10} | {f[\"summary\"][:45]}')
" 2>/dev/null
}

cmd_my_tasks() {
    local agent=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent) agent="$2"; shift 2 ;;
            *) shift ;;
        esac
    done
    [[ -z "$agent" ]] && { echo "ERROR: --agent required" >&2; exit 1; }

    cmd_list --agent "$agent" --status "in-progress"
    echo ""
    echo "=== Planned ==="
    cmd_list --agent "$agent" --status "todo"
}

cmd_sprint() {
    local sprint_num="${1:-}"

    if [[ -z "$sprint_num" ]]; then
        # Show all sprints summary
        for s in 27 28 29 30 31; do
            local sid="${SPRINT_IDS[$s]}"
            local count
            count=$(curl -s -H "Authorization: Bearer $(_pat)" \
                "${JIRA_BASE}/rest/agile/1.0/sprint/${sid}" \
                | python3 -c "
import sys,json
s = json.load(sys.stdin)
print(f'Sprint {s.get(\"name\",\"?\"):15s} | state={s.get(\"state\",\"?\"):8s} | goal={s.get(\"goal\",\"-\")[:50]}')
" 2>/dev/null)
            echo "  $count"
        done
        return
    fi

    # Show specific sprint
    local sid="${SPRINT_IDS[$sprint_num]:-}"
    [[ -z "$sid" ]] && { echo "ERROR: Unknown sprint ${sprint_num}" >&2; exit 1; }

    echo "=== Sprint ${sprint_num} (id=${sid}) ==="
    curl -s -H "Authorization: Bearer $(_pat)" \
        "${JIRA_BASE}/rest/agile/1.0/sprint/${sid}/issue" \
        -G --data-urlencode "maxResults=100" \
        --data-urlencode "fields=key,summary,status,issuetype" \
        | python3 -c "
import sys,json
data = json.load(sys.stdin)
issues = data.get('issues', [])
by_status = {}
for i in issues:
    s = i['fields']['status']['name']
    by_status.setdefault(s, []).append(i)
for status in ['Сделать', 'В работе', 'Готово']:
    items = by_status.get(status, [])
    print(f'\n{status} ({len(items)}):')
    for i in items:
        f = i['fields']
        itype = '📋' if f['issuetype']['name'] == 'Epic' else '  '
        print(f'  {itype} {i[\"key\"]:>12} | {f[\"summary\"][:60]}')
print(f'\nTotal: {len(issues)} issues')
" 2>/dev/null
}

cmd_children() {
    local epic_key="$1"
    [[ -z "$epic_key" ]] && { echo "ERROR: epic key required" >&2; exit 1; }

    curl -s -H "Authorization: Bearer $(_pat)" \
        "${JIRA_BASE}/rest/api/2/search" \
        -G --data-urlencode "jql=\"Ссылка на эпик\" = ${epic_key} ORDER BY key ASC" \
        --data-urlencode "maxResults=50" \
        --data-urlencode "fields=key,summary,status" \
        | python3 -c "
import sys,json
data = json.load(sys.stdin)
issues = data.get('issues', [])
print(f'Epic {\"${epic_key}\"}: {len(issues)} children')
done = sum(1 for i in issues if i['fields']['status']['name'] == 'Готово')
print(f'Progress: {done}/{len(issues)}')
print()
for i in issues:
    f = i['fields']
    check = '✅' if f['status']['name'] == 'Готово' else '⬜'
    print(f'  {check} {i[\"key\"]:>12} | {f[\"summary\"][:60]}')
" 2>/dev/null
}

# --- Main ---
[[ $# -eq 0 ]] && _usage

CMD="$1"; shift
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
