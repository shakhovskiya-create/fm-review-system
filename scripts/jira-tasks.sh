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
    [32]=122 [33]=123 [34]=124 [35]=125
    [36]=126 [37]=127 [38]=128 [39]=129
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

# --- Markdown to Jira Wiki ---
_md_to_wiki() {
    # Convert markdown body to Jira wiki markup
    # Handles: headers, checkboxes, bold, code, bullets
    python3 -c "
import sys, re
text = sys.argv[1]
# Headers: ## -> h2., ### -> h3., # -> h1.
text = re.sub(r'^### (.+)$', r'h3. \1', text, flags=re.MULTILINE)
text = re.sub(r'^## (.+)$', r'h2. \1', text, flags=re.MULTILINE)
text = re.sub(r'^# (.+)$', r'h1. \1', text, flags=re.MULTILINE)
# Checkboxes: - [ ] -> * ( ), - [x] -> * (x)
text = re.sub(r'^- \[x\] ', '* (x) ', text, flags=re.MULTILINE)
text = re.sub(r'^- \[ \] ', '* ( ) ', text, flags=re.MULTILINE)
# Bullets: - item -> * item (only simple dashes at start of line)
text = re.sub(r'^- ', '* ', text, flags=re.MULTILINE)
# Inline code: \`code\` -> {{code}}
text = re.sub(r'\`([^\`]+)\`', r'{{\1}}', text)
# Bold: **text** -> *text*
text = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', text)
print(text)
" "$1"
}

# --- Commands ---
_usage() {
    echo "Usage: jira-tasks.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  create   --title '...' --agent <name> --sprint <N> --body '...' [--priority P] [--type T] [--parent EKFLAB-N] [--component C] [--version V]"
    echo "  start    <EKFLAB-N>"
    echo "  done     <EKFLAB-N> --comment '...'   (REQUIRED: DoD + результат)"
    echo "  block    <EKFLAB-N> --reason '...'"
    echo "  list     [--agent X] [--sprint N] [--status S] [--product P]"
    echo "  my-tasks --agent <name>"
    echo "  sprint   [N]"
    echo "  children <EKFLAB-N>                    (list child tasks of an epic)"
    echo "  xray-register --test-plan EKFLAB-N --exec EKFLAB-N --tests 'EKFLAB-170,171' --reqs 'EKFLAB-38,39' --sprint N"
    echo "                                         (register tests: sprint, labels, plan, reqs, exec, status, close)"
    exit 1
}

cmd_create() {
    local title="" agent="" sprint="" body="" priority="medium" issue_type="Задача" parent=""
    local component="" fix_version=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title) title="$2"; shift 2 ;;
            --agent) agent="$2"; shift 2 ;;
            --sprint) sprint="$2"; shift 2 ;;
            --body) body="$2"; shift 2 ;;
            --priority) priority="$2"; shift 2 ;;
            --component) component="$2"; shift 2 ;;
            --version) fix_version="$2"; shift 2 ;;
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

    # --- Definition of Ready (DoR) validation ---
    local dor_warnings=0
    if [[ -z "$sprint" ]]; then
        echo "DoR WARNING: --sprint не указан (задача не попадет в спринт)" >&2
        dor_warnings=$((dor_warnings + 1))
    fi
    if ! echo "$body" | grep -qiE '(Проблема|проблем)'; then
        echo "DoR WARNING: --body не содержит секцию 'Проблема' (зачем делаем задачу?)" >&2
        dor_warnings=$((dor_warnings + 1))
    fi
    if ! echo "$body" | grep -qiE '(Решение|решени|Ожидаемый результат|результат)'; then
        echo "DoR WARNING: --body не содержит секцию 'Решение' или 'Ожидаемый результат'" >&2
        dor_warnings=$((dor_warnings + 1))
    fi
    if [[ -z "$component" ]]; then
        echo "DoR WARNING: --component не указан" >&2
        dor_warnings=$((dor_warnings + 1))
    fi
    if [[ -z "$fix_version" ]]; then
        echo "DoR WARNING: --version не указана (fixVersion)" >&2
        dor_warnings=$((dor_warnings + 1))
    fi
    if [[ "$dor_warnings" -gt 0 ]]; then
        echo "DoR: ${dor_warnings} предупреждений (задача создается, но рекомендуется заполнить все поля)" >&2
    fi

    # Convert markdown body to Jira wiki markup
    local wiki_body
    wiki_body=$(_md_to_wiki "$body")

    # Build labels
    local labels="[\"product:profitability\""
    [[ -n "$agent" ]] && labels+=",\"agent:${agent}\""
    labels+="]"

    # Build fields (all JSON via Python for safe encoding)
    local jira_priority="${PRIORITY_MAP[$priority]:-Medium}"
    local sprint_id=""
    [[ -n "$sprint" ]] && sprint_id="${SPRINT_IDS[$sprint]:-}"

    local payload
    payload=$(python3 -c "
import json, sys
fields = {
    'project': {'key': sys.argv[1]},
    'summary': sys.argv[2],
    'issuetype': {'name': sys.argv[3]},
    'description': sys.argv[4],
    'labels': json.loads(sys.argv[5]),
    'priority': {'name': sys.argv[6]}
}
epic_name_field = sys.argv[7]
epic_link_field = sys.argv[8]
sprint_field = sys.argv[9]
issue_type = sys.argv[3]
parent = sys.argv[10]
sprint_id = sys.argv[11]
component_name = sys.argv[12]
fix_version_name = sys.argv[13]
if issue_type == 'Epic':
    fields[epic_name_field] = sys.argv[2]  # epic name = title
if parent:
    fields[epic_link_field] = parent
if sprint_id:
    fields[sprint_field] = int(sprint_id)
if component_name:
    fields['components'] = [{'name': component_name}]
if fix_version_name:
    fields['fixVersions'] = [{'name': fix_version_name}]
print(json.dumps({'fields': fields}))
" "$JIRA_PROJECT" "$title" "$issue_type" "$wiki_body" "$labels" "$jira_priority" \
  "$EPIC_NAME_FIELD" "$EPIC_LINK_FIELD" "$SPRINT_FIELD" "${parent:-}" "${sprint_id:-}" \
  "${component:-}" "${fix_version:-}")

    local response
    response=$(_jira_post "/rest/api/2/issue" "$payload")

    local key
    key=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('key','ERROR'))" 2>/dev/null)

    if [[ "$key" == "ERROR" ]]; then
        echo "ERROR creating issue:" >&2
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response" >&2
        exit 1
    fi

    # Auto-set default Smart Checklist (DoD) — all items unchecked, Russian
    local default_checklist
    default_checklist=$(printf '%s\n' \
        '---' \
        '- Тесты проходят' \
        '- Регрессий нет' \
        '- Критерии приёмки выполнены' \
        '- Артефакты перечислены' \
        '- Документация обновлена (или N/A)' \
        '- Скрытого техдолга нет')
    local cl_payload
    cl_payload=$(python3 -c "import json,sys; print(json.dumps({'value': sys.argv[1]}))" "$default_checklist")
    curl -s -X PUT \
        -H "Authorization: Bearer ${JIRA_PAT}" \
        -H "Content-Type: application/json" \
        -d "$cl_payload" \
        "${JIRA_BASE}/rest/api/2/issue/${key}/properties/com.railsware.SmartChecklist.checklist?notifyUsers=false" > /dev/null 2>&1 || true

    echo "$key"
    echo "Created: ${JIRA_BASE}/browse/${key}" >&2
}

cmd_start() {
    local issue_key="$1"
    [[ -z "$issue_key" ]] && { echo "ERROR: issue key required" >&2; exit 1; }

    # Add status:in-progress label (removed by cmd_done)
    _jira_put "/rest/api/2/issue/${issue_key}?notifyUsers=false" '{"update":{"labels":[{"add":"status:in-progress"}]}}'

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
    [[ -z "$comment" ]] && { echo "ERROR: --comment is required (результат + было→стало)" >&2; exit 1; }

    # Step 0: Verify Smart Checklist — ALL items must be checked (+)
    local checklist_raw
    checklist_raw=$(_jira_get "/rest/api/2/issue/${issue_key}/properties/com.railsware.SmartChecklist.checklist" 2>/dev/null || true)
    if [[ -n "$checklist_raw" ]] && echo "$checklist_raw" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
        local checklist_status
        checklist_status=$(echo "$checklist_raw" | python3 -c "
import sys, json
data = json.load(sys.stdin)
value = data.get('value', '')
# Smart Checklist stores nested: {"value": {"value": "..."}} or {"value": "..."}
if isinstance(value, dict):
    value = value.get('value', '')
if not isinstance(value, str):
    value = ''
lines = [l.strip() for l in value.replace('\\\\n', '\\n').replace('\\n', '\n').split('\n') if l.strip()]
total = len(lines)
checked = sum(1 for l in lines if l.startswith('+'))
unchecked = [l for l in lines if l.startswith('-') or l.startswith('~')]
if unchecked:
    print('FAIL')
    for u in unchecked:
        print(f'  {u}')
elif total == 0:
    print('EMPTY')
else:
    print('OK')
" 2>/dev/null)

        case "$(echo "$checklist_status" | head -1)" in
            FAIL)
                echo "ERROR: Smart Checklist не полностью выполнен для ${issue_key}:" >&2
                echo "$checklist_status" | tail -n +2 >&2
                echo "" >&2
                echo "Закройте все пункты чеклиста перед закрытием задачи." >&2
                exit 1
                ;;
            EMPTY)
                echo "ERROR: Smart Checklist пуст для ${issue_key}." >&2
                echo "Заполните DoD-чеклист перед закрытием задачи." >&2
                exit 1
                ;;
            OK)
                ;; # All good
        esac
    else
        echo "ERROR: Smart Checklist не найден для ${issue_key}." >&2
        echo "Заполните DoD-чеклист перед закрытием задачи." >&2
        echo "API: PUT /rest/api/2/issue/${issue_key}/properties/com.railsware.SmartChecklist.checklist" >&2
        exit 1
    fi

    # Step 1: Add closing comment (результат, NOT DoD — DoD is in Smart Checklist)
    local comment_json
    comment_json=$(python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" <<< "$comment")
    _jira_post "/rest/api/2/issue/${issue_key}/comment?notifyUsers=false" \
        "{\"body\": $comment_json}" > /dev/null

    # Step 2: Transition to Готово
    if _transition_issue "$issue_key" "Готово"; then
        echo "Done: ${issue_key} → Готово"
    else
        echo "ERROR: Could not close ${issue_key}" >&2
        exit 1
    fi

    # Step 2b: Remove status:in-progress label (added by cmd_start)
    _jira_put "/rest/api/2/issue/${issue_key}?notifyUsers=false" '{"update":{"labels":[{"remove":"status:in-progress"}]}}' 2>/dev/null || true

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

cmd_xray_register() {
    # Full Xray workflow: sprint, labels, plan, requirements, execution, status, close
    local test_plan="" test_exec="" tests="" reqs="" sprint=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --test-plan) test_plan="$2"; shift 2 ;;
            --exec) test_exec="$2"; shift 2 ;;
            --tests) tests="$2"; shift 2 ;;
            --reqs) reqs="$2"; shift 2 ;;
            --sprint) sprint="$2"; shift 2 ;;
            *) shift ;;
        esac
    done

    [[ -z "$tests" ]] && { echo "ERROR: --tests required (comma-separated EKFLAB-N)" >&2; exit 1; }
    [[ -z "$sprint" ]] && { echo "ERROR: --sprint required" >&2; exit 1; }

    local sid="${SPRINT_IDS[$sprint]:-}"
    [[ -z "$sid" ]] && { echo "ERROR: Unknown sprint ${sprint}" >&2; exit 1; }

    # Parse test keys
    IFS=',' read -ra TEST_KEYS <<< "$tests"
    local all_xray_keys=("${TEST_KEYS[@]}")
    [[ -n "$test_plan" ]] && all_xray_keys+=("$test_plan")
    [[ -n "$test_exec" ]] && all_xray_keys+=("$test_exec")

    echo "=== Xray Register: ${#TEST_KEYS[@]} tests, sprint ${sprint} ==="

    # Step 1: Add all Xray issues to sprint
    local issues_json=""
    for key in "${all_xray_keys[@]}"; do
        [[ -n "$issues_json" ]] && issues_json+=","
        issues_json+="\"${key}\""
    done
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $(_pat)" \
        -H "Content-Type: application/json" \
        "$JIRA_BASE/rest/agile/1.0/sprint/${sid}/issue" \
        -d "{\"issues\":[${issues_json}]}")
    echo "  [1/7] Sprint ${sprint}: ${#all_xray_keys[@]} issues → HTTP ${http_code}"

    # Step 2: Add product:profitability label to all
    for key in "${all_xray_keys[@]}"; do
        _jira_put "/rest/api/2/issue/${key}?notifyUsers=false" \
            '{"update":{"labels":[{"add":"product:profitability"}]}}' > /dev/null
    done
    echo "  [2/7] Labels: product:profitability → ${#all_xray_keys[@]} issues"

    # Step 3: Set Test Type = Generic + update description (for test issues only)
    for key in "${TEST_KEYS[@]}"; do
        _jira_put "/rest/api/2/issue/${key}?notifyUsers=false" \
            '{"fields":{"customfield_11500":{"id":"11802"}}}' > /dev/null
    done
    echo "  [3/7] Test Type = Generic → ${#TEST_KEYS[@]} tests"

    # Step 4: Add tests to Test Plan
    if [[ -n "$test_plan" ]]; then
        local add_json=""
        for key in "${TEST_KEYS[@]}"; do
            [[ -n "$add_json" ]] && add_json+=","
            add_json+="\"${key}\""
        done
        http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
            -H "Authorization: Bearer $(_pat)" \
            -H "Content-Type: application/json" \
            "$JIRA_BASE/rest/raven/1.0/api/testplan/${test_plan}/test" \
            -d "{\"add\":[${add_json}]}")
        echo "  [4/7] Test Plan ${test_plan}: ${#TEST_KEYS[@]} tests → HTTP ${http_code}"
    else
        echo "  [4/7] Test Plan: skipped (no --test-plan)"
    fi

    # Step 5: Link to requirements (CORRECT DIRECTION: req=outward, test=inward)
    if [[ -n "$reqs" ]]; then
        IFS=',' read -ra REQ_KEYS <<< "$reqs"
        local link_count=0
        for req in "${REQ_KEYS[@]}"; do
            for test in "${TEST_KEYS[@]}"; do
                curl -s -o /dev/null -w "" -X POST \
                    -H "Authorization: Bearer $(_pat)" \
                    -H "Content-Type: application/json" \
                    "$JIRA_BASE/rest/api/2/issueLink" \
                    -d "{\"type\":{\"name\":\"Tests\"},\"outwardIssue\":{\"key\":\"${req}\"},\"inwardIssue\":{\"key\":\"${test}\"}}"
                link_count=$((link_count + 1))
            done
        done
        echo "  [5/7] Requirements: ${link_count} links (${#REQ_KEYS[@]} reqs × ${#TEST_KEYS[@]} tests)"
    else
        echo "  [5/7] Requirements: skipped (no --reqs)"
    fi

    # Step 6: Add tests to Test Execution + set PASS
    if [[ -n "$test_exec" ]]; then
        local add_json=""
        for key in "${TEST_KEYS[@]}"; do
            [[ -n "$add_json" ]] && add_json+=","
            add_json+="\"${key}\""
        done
        http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
            -H "Authorization: Bearer $(_pat)" \
            -H "Content-Type: application/json" \
            "$JIRA_BASE/rest/raven/1.0/api/testexec/${test_exec}/test" \
            -d "{\"add\":[${add_json}]}")
        echo "  [6/7] Test Execution ${test_exec}: ${#TEST_KEYS[@]} tests → HTTP ${http_code}"

        # Get testrun IDs and set PASS
        local testruns
        testruns=$(_jira_get "/rest/raven/1.0/api/testexec/${test_exec}/test")
        local pass_count=0
        for run_id in $(echo "$testruns" | python3 -c "
import sys,json
data = json.load(sys.stdin)
for t in data:
    print(t.get('id',''))
" 2>/dev/null); do
            [[ -z "$run_id" ]] && continue
            curl -s -o /dev/null -X PUT \
                -H "Authorization: Bearer $(_pat)" \
                "$JIRA_BASE/rest/raven/1.0/api/testrun/${run_id}/status?status=PASS"
            pass_count=$((pass_count + 1))
        done
        echo "  [6b/7] Test Results: ${pass_count} → PASS"
    else
        echo "  [6/7] Test Execution: skipped (no --exec)"
    fi

    # Step 7: Close all Xray issues
    local closed=0
    for key in "${all_xray_keys[@]}"; do
        if _transition_issue "$key" "Готово" 2>/dev/null; then
            closed=$((closed + 1))
        fi
        # Remove status:in-progress if present
        _jira_put "/rest/api/2/issue/${key}?notifyUsers=false" \
            '{"update":{"labels":[{"remove":"status:in-progress"}]}}' > /dev/null 2>&1 || true
    done
    echo "  [7/7] Closed: ${closed}/${#all_xray_keys[@]} issues → Готово"

    echo ""
    echo "Done: Xray workflow complete for ${#TEST_KEYS[@]} tests in sprint ${sprint}"
}

# --- Main ---
[[ $# -eq 0 ]] && _usage

CMD="$1"; shift
case "$CMD" in
    create)        cmd_create "$@" ;;
    start)         cmd_start "$@" ;;
    done)          cmd_done "$@" ;;
    block)         cmd_block "$@" ;;
    list)          cmd_list "$@" ;;
    my-tasks)      cmd_my_tasks "$@" ;;
    sprint)        cmd_sprint "$@" ;;
    children)      cmd_children "$@" ;;
    xray-register) cmd_xray_register "$@" ;;
    *)             _usage ;;
esac
