#!/usr/bin/env bash
# Sprint Completion Protocol — автоматическая проверка.
# Создаёт маркер .sprint-completion-done ТОЛЬКО если все проверяемые условия пройдены.
# Без маркера guard-sprint-close.sh не даст закрыть спринт.
#
# Usage: scripts/sprint-completion.sh --sprint N [--repo /path/to/profitability-service]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MARKER_FILE="$PROJECT_DIR/.sprint-completion-done"

# Parse args
SPRINT_NUM=""
REPO_PATH="/home/dev/projects/claude-agents/profitability-service"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sprint) SPRINT_NUM="$2"; shift 2 ;;
        --repo) REPO_PATH="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$SPRINT_NUM" ]; then
    echo "ERROR: --sprint N обязателен" >&2
    echo "Usage: scripts/sprint-completion.sh --sprint 43" >&2
    exit 1
fi

PASS=0
FAIL=0
WARN=0
RESULTS=""

check_pass() { PASS=$((PASS + 1)); RESULTS+="  [PASS] $1\n"; }
check_fail() { FAIL=$((FAIL + 1)); RESULTS+="  [FAIL] $1\n"; }
check_warn() { WARN=$((WARN + 1)); RESULTS+="  [WARN] $1\n"; }

echo "=== Sprint Completion Protocol — Sprint $SPRINT_NUM ==="
echo ""

# ============================================
# ПЕРВЫЙ ПРОХОД — ТЕХНИЧЕСКАЯ ПРОВЕРКА
# ============================================
echo "--- Первый проход: техническая проверка ---"
echo ""

# 1. Go build
echo "1. go build..."
if (cd "$REPO_PATH" && go build ./... 2>/dev/null); then
    check_pass "go build ./... — компиляция успешна"
else
    check_fail "go build ./... — ошибка компиляции"
fi

# 2. Go test
echo "2. go test..."
TEST_OUTPUT=$(cd "$REPO_PATH" && go test ./... -short -count=1 2>&1 || true)
TEST_FAILURES=$(echo "$TEST_OUTPUT" | grep -c "^FAIL" || true)
TEST_PASSED=$(echo "$TEST_OUTPUT" | grep -c "^ok" || true)
if [ "$TEST_FAILURES" -eq 0 ] && [ "$TEST_PASSED" -gt 0 ]; then
    check_pass "go test — $TEST_PASSED пакетов прошли, 0 failures"
else
    check_fail "go test — $TEST_FAILURES failures из $TEST_PASSED пакетов"
fi

# 3. CI green (last run on main)
echo "3. CI status..."
LAST_CI=$(cd "$REPO_PATH" && gh run list --branch main --limit 1 --json conclusion -q '.[0].conclusion' 2>/dev/null || echo "unknown")
if [ "$LAST_CI" = "success" ]; then
    check_pass "CI green (main)"
else
    check_fail "CI не green: $LAST_CI"
fi

# 4. Jira — все задачи спринта закрыты
echo "4. Jira tasks..."
# Load Jira PAT
source "$SCRIPT_DIR/load-secrets.sh" 2>/dev/null || true
JIRA_URL="${JIRA_BASE_URL:-https://jira.ekf.su}"
JIRA_PAT="${JIRA_PAT:-}"

if [ -n "$JIRA_PAT" ]; then
    OPEN_TASKS=$(curl -s -H "Authorization: Bearer $JIRA_PAT" \
        "$JIRA_URL/rest/api/2/search?jql=project=EKFLAB+AND+sprint=$SPRINT_NUM+AND+status!=10001+AND+status!=10158&maxResults=0" \
        2>/dev/null | jq -r '.total // 0' 2>/dev/null || echo "?")

    if [ "$OPEN_TASKS" = "0" ]; then
        check_pass "Jira: 0 открытых задач в спринте $SPRINT_NUM"
    elif [ "$OPEN_TASKS" = "?" ]; then
        check_warn "Jira: не удалось проверить (API error)"
    else
        check_fail "Jira: $OPEN_TASKS открытых задач в спринте $SPRINT_NUM"
    fi
else
    check_warn "Jira: JIRA_PAT не найден, проверка пропущена"
fi

# 5. SE review артефакт для текущего спринта
echo "5. SE review artifact..."
SE_FILES=$(find "$PROJECT_DIR/projects/PROJECT_SHPMNT_PROFIT/AGENT_9_SE_GO" \
    -name "se_review_sprint${SPRINT_NUM}*" 2>/dev/null | wc -l)
if [ "$SE_FILES" -gt 0 ]; then
    check_pass "SE review: $SE_FILES артефактов для sprint $SPRINT_NUM"
else
    check_warn "SE review: нет артефактов для sprint $SPRINT_NUM (если код не менялся — OK)"
fi

# 6. Memory updated (MEMORY.md modified today)
echo "6. Memory update..."
MEMORY_FILE="$HOME/.claude/projects/-home-dev-projects-claude-agents-fm-review-system/memory/MEMORY.md"
if [ -f "$MEMORY_FILE" ]; then
    MEMORY_MOD=$(stat -c %Y "$MEMORY_FILE" 2>/dev/null || echo "0")
    NOW=$(date +%s)
    DIFF=$(( (NOW - MEMORY_MOD) / 3600 ))
    if [ "$DIFF" -lt 24 ]; then
        check_pass "MEMORY.md обновлён ($DIFF часов назад)"
    else
        check_fail "MEMORY.md не обновлён ($DIFF часов назад)"
    fi
else
    check_fail "MEMORY.md не найден"
fi

# 7. Review findings resolved (SE, OpenAI, Qodo)
echo "7. Review findings check..."
# Check for SE review files — if they exist, look for unresolved HIGH/CRIT
SE_REVIEW_DIR="$PROJECT_DIR/projects/PROJECT_SHPMNT_PROFIT/AGENT_9_SE_GO"
OPENAI_REVIEW_DIR="$PROJECT_DIR/projects/PROJECT_SHPMNT_PROFIT/OPENAI_REVIEW"
FINDINGS_UNRESOLVED=0

# Check latest SE review for sprint
LATEST_SE=$(find "$SE_REVIEW_DIR" -name "se_review_sprint${SPRINT_NUM}*" -name "*.json" 2>/dev/null | sort | tail -1)
if [ -n "$LATEST_SE" ]; then
    SE_VERDICT=$(jq -r '.verdict // empty' "$LATEST_SE" 2>/dev/null || echo "")
    if [ "$SE_VERDICT" != "PASS" ] && [ "$SE_VERDICT" != "" ]; then
        SE_HIGH=$(jq '[.findings[]? | select(.severity == "HIGH" or .severity == "CRITICAL")] | length' "$LATEST_SE" 2>/dev/null || echo "0")
        if [ "$SE_HIGH" -gt 0 ]; then
            FINDINGS_UNRESOLVED=$((FINDINGS_UNRESOLVED + SE_HIGH))
        fi
    fi
fi

# Check latest OpenAI review
LATEST_OAI=$(find "$OPENAI_REVIEW_DIR" -name "openai_review_*.json" 2>/dev/null | sort | tail -1)
if [ -n "$LATEST_OAI" ]; then
    OAI_VERDICT=$(jq -r '.verdict // empty' "$LATEST_OAI" 2>/dev/null || echo "")
    if [ "$OAI_VERDICT" != "PASS" ] && [ "$OAI_VERDICT" != "" ]; then
        OAI_HIGH=$(jq '[.findings[]? | select(.severity == "HIGH" or .severity == "CRITICAL")] | length' "$LATEST_OAI" 2>/dev/null || echo "0")
        if [ "$OAI_HIGH" -gt 0 ]; then
            FINDINGS_UNRESOLVED=$((FINDINGS_UNRESOLVED + OAI_HIGH))
        fi
    fi
fi

if [ "$FINDINGS_UNRESOLVED" -gt 0 ]; then
    check_fail "Review findings: $FINDINGS_UNRESOLVED неисправленных HIGH/CRITICAL замечаний"
else
    check_pass "Review findings: нет неисправленных HIGH/CRITICAL"
fi

# 8. No uncommitted changes in profitability-service
echo "8. Clean working tree..."
DIRTY=$(cd "$REPO_PATH" && git status --porcelain 2>/dev/null | { grep -v "^??" || true; } | wc -l)
if [ "$DIRTY" -eq 0 ]; then
    check_pass "Рабочее дерево чистое (no uncommitted changes)"
else
    check_warn "Есть $DIRTY незакоммиченных изменений"
fi

echo ""

# ============================================
# РЕЗУЛЬТАТ
# ============================================
echo "=== Результат ==="
echo ""
echo -e "$RESULTS"
echo "PASS: $PASS | FAIL: $FAIL | WARN: $WARN"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "BLOCKED: $FAIL проверок не прошли. Исправьте и запустите заново." >&2
    echo "" >&2
    echo "Оставшиеся РУЧНЫЕ шаги (после исправления FAIL):" >&2
    echo "  - Моделирование: представить реального пользователя/разработчика" >&2
    echo "  - Cross-check: deliverables vs AC из issues" >&2
    echo "  - Бизнес-линза: ускоряет или замедляет продажи?" >&2
    echo "  - Обновить многоуровневую память (MCP, Graphiti, RAG)" >&2
    exit 1
fi

# All checks passed — create marker
touch "$MARKER_FILE"
echo "ALL CHECKS PASSED. Маркер создан: $MARKER_FILE"
echo ""
echo "РУЧНЫЕ шаги (выполнить ПЕРЕД sprint close):"
echo "  1. Моделирование на реальном проекте"
echo "  2. Cross-check deliverables vs AC"
echo "  3. Бизнес-линза"
echo "  4. Обновить MCP memory, Graphiti, Local RAG (если применимо)"
echo ""
echo "Теперь можно закрыть спринт:"
echo "  jira-tasks.sh sprint-close --sprint $SPRINT_NUM"
