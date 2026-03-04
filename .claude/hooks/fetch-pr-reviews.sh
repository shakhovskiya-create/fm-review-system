#!/usr/bin/env bash
# Hook: PostToolUse -> Bash
# After `git push` to profitability-service: fetches PR review comments
# from bots (qodo-code-review, chatgpt-codex-connector, etc.) and outputs
# them so Claude can see and fix issues immediately.
#
# Non-blocking: exits 0 always (fetch failure should not block push)

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PROF_SERVICE="/home/dev/projects/claude-agents/profitability-service"

# Only process git push commands
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")
[ -z "$COMMAND" ] && exit 0

if ! echo "$COMMAND" | grep -qE '(^|&&|\|\||;)\s*git\s+push'; then
    exit 0
fi

# Only for profitability-service repo (check if command runs in that dir)
if ! echo "$COMMAND" | grep -q "profitability-service"; then
    # Also check CWD from tool_input or default
    CWD=$(echo "$INPUT" | jq -r '.tool_input.cwd // empty' 2>/dev/null || echo "")
    if [ -z "$CWD" ] || ! echo "$CWD" | grep -q "profitability-service"; then
        # Check if command starts with cd to profitability-service
        if ! echo "$COMMAND" | grep -q "profitability-service"; then
            exit 0
        fi
    fi
fi

# Check if push succeeded
STDOUT=$(echo "$INPUT" | jq -r '.stdout // empty' 2>/dev/null || echo "")
STDERR=$(echo "$INPUT" | jq -r '.stderr // empty' 2>/dev/null || echo "")
if ! echo "$STDERR$STDOUT" | grep -qE '(->|Everything up-to-date)'; then
    exit 0
fi

# Find open PRs for the current branch
BRANCH=$(git -C "$PROF_SERVICE" branch --show-current 2>/dev/null || echo "main")
PR_NUMBER=$(gh pr list --repo shakhovskiya-create/profitability-service --head "$BRANCH" --state all --json number --jq '.[0].number' 2>/dev/null || echo "")

if [ -z "$PR_NUMBER" ]; then
    # Try to get latest merged PR
    PR_NUMBER=$(gh pr list --repo shakhovskiya-create/profitability-service --state merged --json number --jq '.[0].number' 2>/dev/null || echo "")
fi

[ -z "$PR_NUMBER" ] && exit 0

# Dedup: track seen comment IDs so we don't re-show old reviews
SEEN_FILE="$PROF_SERVICE/.claude-pr-reviews-seen"
touch "$SEEN_FILE" 2>/dev/null || SEEN_FILE="/tmp/claude-pr-reviews-seen-${PR_NUMBER}"

# Fetch inline review comments from bots (with IDs for dedup)
BOT_COMMENTS=$(gh api "repos/shakhovskiya-create/profitability-service/pulls/${PR_NUMBER}/comments" \
    --jq '[.[] | select(.user.login | test("\\[bot\\]$")) | {id: .id, bot: .user.login, path: .path, line: .line, body: .body}]' 2>/dev/null || echo "[]")

# Fetch PR review summaries from bots
PR_REVIEWS=$(gh api "repos/shakhovskiya-create/profitability-service/pulls/${PR_NUMBER}/reviews" \
    --jq '[.[] | select(.user.login | test("\\[bot\\]$")) | {id: .id, bot: .user.login, state: .state, body: .body}]' 2>/dev/null || echo "[]")

# Fetch issue comments (some bots post there)
ISSUE_COMMENTS=$(gh api "repos/shakhovskiya-create/profitability-service/issues/${PR_NUMBER}/comments" \
    --jq '[.[] | select(.user.login | test("\\[bot\\]$")) | {id: .id, bot: .user.login, body: .body}]' 2>/dev/null || echo "[]")

# Filter out already-seen comments
filter_new() {
    local json="$1"
    local result="[]"
    local ids
    ids=$(echo "$json" | jq -r '.[].id' 2>/dev/null || echo "")
    [ -z "$ids" ] && echo "[]" && return
    local new_items="["
    local first=true
    while IFS= read -r id; do
        [ -z "$id" ] && continue
        if grep -qxF "$id" "$SEEN_FILE" 2>/dev/null; then
            continue
        fi
        if [ "$first" = true ]; then
            first=false
        else
            new_items+=","
        fi
        new_items+=$(echo "$json" | jq ".[] | select(.id == $id)" 2>/dev/null)
    done <<< "$ids"
    new_items+="]"
    echo "$new_items" | jq '.' 2>/dev/null || echo "[]"
}

NEW_INLINE=$(filter_new "$BOT_COMMENTS")
NEW_REVIEWS=$(filter_new "$PR_REVIEWS")
NEW_ISSUES=$(filter_new "$ISSUE_COMMENTS")

INLINE_COUNT=$(echo "$NEW_INLINE" | jq 'length' 2>/dev/null || echo 0)
REVIEW_COUNT=$(echo "$NEW_REVIEWS" | jq '[.[] | select(.body != "")] | length' 2>/dev/null || echo 0)
ISSUE_COUNT=$(echo "$NEW_ISSUES" | jq 'length' 2>/dev/null || echo 0)
TOTAL=$((INLINE_COUNT + REVIEW_COUNT + ISSUE_COUNT))

if [ "$TOTAL" -eq 0 ]; then
    exit 0
fi

# Mark all as seen
for json in "$NEW_INLINE" "$NEW_REVIEWS" "$NEW_ISSUES"; do
    echo "$json" | jq -r '.[].id' 2>/dev/null >> "$SEEN_FILE" || true
done

# Output for Claude to see
echo ""
echo "=== PR #${PR_NUMBER}: NEW Bot Review Comments (${TOTAL}) ==="
echo ""

if [ "$INLINE_COUNT" -gt 0 ]; then
    echo "--- Inline Comments (${INLINE_COUNT}) ---"
    echo "$NEW_INLINE" | jq -r '.[] | "[\(.bot)] \(.path):\(.line // "general")\n\(.body)\n---"' 2>/dev/null || true
    echo ""
fi

if [ "$REVIEW_COUNT" -gt 0 ]; then
    echo "--- Review Summaries ---"
    echo "$NEW_REVIEWS" | jq -r '.[] | select(.body != "") | "[\(.bot)] (\(.state))\n\(.body)\n---"' 2>/dev/null || true
    echo ""
fi

if [ "$ISSUE_COUNT" -gt 0 ]; then
    echo "--- Issue Comments ---"
    echo "$NEW_ISSUES" | jq -r '.[] | "[\(.bot)]\n\(.body)\n---"' 2>/dev/null || true
    echo ""
fi

echo "=== End Bot Reviews ==="
echo "ACTION: Review findings above. Fix CRITICAL/HIGH issues before proceeding."

exit 0
